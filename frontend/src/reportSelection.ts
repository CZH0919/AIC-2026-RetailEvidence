import type { SalesRun } from './retail'

export const reportReady = (r: SalesRun) => ['succeeded', 'completed_with_warnings', 'not_applicable'].includes(r.status) && (r.has_result === true || !!r.result)
export const reportMonth = (r: SalesRun) => r.result?.month ?? r.parameters?.sales.month ?? ''
export const monthLabel = (month: string) => /^\d{4}-\d{2}$/.test(month) ? `${month.slice(0, 4)} 年 ${Number(month.slice(5))} 月` : '月份未记录'
export function monthlyReports(runs: SalesRun[]) {
  const groups = new Map<string, SalesRun[]>()
  for (const run of runs.filter(reportReady)) {
    const month = reportMonth(run)
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) continue
    groups.set(month, [...(groups.get(month) ?? []), run])
  }
  return [...groups].sort(([a], [b]) => b.localeCompare(a)).map(([month, reports]) => ({
    month, reports: reports.sort((a, b) => (b.finished_at ?? b.created_at).localeCompare(a.finished_at ?? a.created_at) || b.created_at.localeCompare(a.created_at) || b.id.localeCompare(a.id)),
  }))
}
export function reportQuery(search: string, runId: string) {
  const next = new URLSearchParams(search)
  next.set('run', runId)
  for (const key of ['pairingSource', 'pairingRun', 'pairingItems', 'compose']) next.delete(key)
  return next
}
