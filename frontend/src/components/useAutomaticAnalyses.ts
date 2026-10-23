import { useEffect, useRef, useState } from 'react'
import { salesApi } from '../retail'
import type { AutomaticAnalyses } from '../retail'

export function useAutomaticAnalyses(projectId: string, runId: string | undefined, onResults: (id: string) => Promise<void>) {
  const callback = useRef(onResults); callback.current = onResults
  const [value, setValue] = useState<{runId: string; data: AutomaticAnalyses} | null>(null)
  const [error, setError] = useState(''), [attempt, setAttempt] = useState(0)
  const retryRequested = useRef(false)
  useEffect(() => {
    if (!runId) return
    let active = true, timer: number | undefined, published = ''
    const retry = retryRequested.current; retryRequested.current = false
    setError('')
    async function load(start: boolean) {
      try {
        const next = start ? await salesApi.startAutomatic(projectId, runId!, retry) : await salesApi.automatic(projectId, runId!)
        if (!active) return
        setValue({runId: runId!, data: next}); setError('')
        const ready = Object.values(next.steps).filter(s => s?.status === 'ready').map(s => s!.run_id).sort().join('|')
        if (ready && ready !== published) {
          await callback.current(runId!)
          published = ready
        }
        if (active && next.status !== 'complete') timer = window.setTimeout(() => void load(false), 2500)
      } catch {
        if (active) {
          setError('暂时无法读取自动分析进度，正在重试。')
          timer = window.setTimeout(() => void load(start), 5000)
        }
      }
    }
    void load(true)
    return () => { active = false; window.clearTimeout(timer) }
  }, [projectId, runId, attempt])
  return {data: value && value.runId === runId ? value.data : null, error,
    retry: () => { retryRequested.current = true; setAttempt(n => n + 1) }}
}
