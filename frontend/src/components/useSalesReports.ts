import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { dataApi } from '../data'
import type { Version } from '../data'
import { salesApi } from '../retail'
import type { SalesRun } from '../retail'
import { finished } from '../quality'
import { useAutomaticAnalyses } from './useAutomaticAnalyses'
import { monthlyReports, reportMonth, reportQuery, reportReady, monthLabel } from '../reportSelection'

export function useSalesReports(projectId: string, view: 'overview' | 'products') {
  const [params, setParams] = useSearchParams()
  const paramsRef = useRef(params); paramsRef.current = params
  const [versions, setVersions] = useState<Version[]>([]), [runs, setRuns] = useState<SalesRun[]>([])
  const [current, setCurrent] = useState<SalesRun | null>(null), currentRef = useRef<SalesRun | null>(null)
  const [loading, setLoading] = useState(true), [switching, setSwitching] = useState('')
  const [error, setError] = useState(''), [retryId, setRetryId] = useState<string | null>(null)
  const [task, setTask] = useState<SalesRun | null>(null), [taskNotice, setTaskNotice] = useState('')
  const followTask = useRef(true)
  const generation = useRef(0), requested = params.get('run')
  const groups = monthlyReports(runs)
  function commit(run: SalesRun | null, replace: boolean, preserveQuery = false) {
    currentRef.current = run; setCurrent(run)
    if (run && paramsRef.current.get('run') !== run.id) {
      const next = preserveQuery ? new URLSearchParams(paramsRef.current) : reportQuery(paramsRef.current.toString(), run.id)
      next.set('run', run.id); paramsRef.current = next; setParams(next, {replace})
    }
  }
  async function reload(preferred?: string) {
    const ticket = ++generation.current
    setError(''); setRetryId(null)
    try {
      const [v, list] = await Promise.all([dataApi.versions(projectId), salesApi.list(projectId)])
      if (ticket !== generation.current) return
      const available = monthlyReports(list.items)
      let wanted = list.items.find(r => r.id === (preferred ?? paramsRef.current.get('run') ?? currentRef.current?.id))
      if (wanted && !reportReady(wanted)) {
        if (!finished.has(wanted.status)) { followTask.current = true; setTask(wanted); setTaskNotice('') }
        else { setTask(null); setTaskNotice(`这次报告未生成成功：${wanted.message}`) }
        wanted = list.items.find(r => r.id === currentRef.current?.id && reportReady(r)) ?? available.find(g => g.month === reportMonth(wanted!))?.reports[0] ?? available[0]?.reports[0]
      }
      if (!wanted) wanted = available[0]?.reports[0]
      if (!wanted) {
        const pending = list.items.find(r => !finished.has(r.status))
        if (pending) setTask(pending)
      }
      const next = wanted ? await salesApi.workspace(projectId, wanted.id, view) : null
      if (ticket !== generation.current) return
      if (wanted && !next?.result) throw new Error('这份报告暂时无法读取，请重试。')
      setVersions(v.items); setRuns(list.items); commit(next, true, true)
    } catch (e) {
      if (ticket === generation.current) setError((e as Error).message)
    } finally {
      if (ticket === generation.current) { setLoading(false); setSwitching('') }
    }
  }
  async function choose(id: string, replace = false) {
    followTask.current = false
    const ticket = ++generation.current
    const row = runs.find(r => r.id === id)
    setSwitching(monthLabel(row ? reportMonth(row) : '') + '报告'); setError(''); setRetryId(null)
    try {
      const next = await salesApi.workspace(projectId, id, view)
      if (ticket !== generation.current) return false
      if (!next.result || !reportReady(next)) throw new Error('这份报告尚未生成成功。')
      commit(next, replace)
      return true
    } catch {
      if (ticket === generation.current) {
        setError('报告加载失败，仍保留原来的报告。'); setRetryId(id)
        if (currentRef.current && paramsRef.current.get('run') !== currentRef.current.id) {
          const back = reportQuery(paramsRef.current.toString(), currentRef.current.id)
          paramsRef.current = back; setParams(back, {replace: true})
        }
      }
      return false
    } finally { if (ticket === generation.current) setSwitching('') }
  }
  useEffect(() => {
    setLoading(true); currentRef.current = null; setCurrent(null); setTask(null)
    void reload()
    return () => { ++generation.current }
  }, [projectId, view]) // The view must finish loading before it becomes the active report.
  useEffect(() => {
    if (!loading && requested && requested !== currentRef.current?.id && requested !== task?.id) void choose(requested, true)
  }, [requested, loading])
  useEffect(() => {
    if (!task || finished.has(task.status)) return
    let active = true, polling = false
    const timer = window.setInterval(async () => {
      if (polling) return
      polling = true
      try {
        const next = await salesApi.workspace(projectId, task.id, view)
        if (!active) return
        setTask(next)
        if (finished.has(next.status)) {
          setTask(null)
          if (next.result) { setTaskNotice(''); void reload(followTask.current ? next.id : currentRef.current?.id) }
          else setTaskNotice(`这次报告未生成成功：${next.message}`)
        }
      } catch { if (active) setTaskNotice('暂时无法读取生成进度，将继续重试。') }
      finally { polling = false }
    }, 1800)
    return () => { active = false; window.clearInterval(timer) }
  }, [projectId, task?.id, view])
  const automatic = useAutomaticAnalyses(projectId, current?.id, async id => {
    const ticket = generation.current
    const next = await salesApi.workspace(projectId, id, view)
    if (ticket === generation.current && currentRef.current?.id === id) commit(next, true, true)
  })
  return {automatic, versions, runs, current, groups, loading, switching, error, task, taskNotice,
    choose, reload, retry: () => retryId ? choose(retryId) : reload(), clearError: () => setError('')}
}
