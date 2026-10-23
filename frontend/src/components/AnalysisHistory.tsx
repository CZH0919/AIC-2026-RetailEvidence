import { useId } from 'react'
import { Select } from 'antd'
import { stateLabel } from '../quality'
import type { QualityRun } from '../quality'

// These are saved analysis runs, not customer groups. Reuse the existing
// selection callback; opening history must never start or alter an analysis.
export function AnalysisHistory({ title, runs, selected, detail, onSelect }: {
  title: string; runs: QualityRun[]; selected: string; detail: QualityRun | null; onSelect: (id: string) => void
}) {
  const id = useId()
  const history = detail?.id === selected && !runs.some(run => run.id === selected) ? [detail, ...runs] : runs
  if (!history.length) return <p className="analysis-history-empty">还没有{title}记录。</p>
  const options = history.map((run, index) => {
    const saved = detail?.id === run.id ? detail : run
    const kind = saved.parameters?.analysis?.kind
    const mode = kind === 'rf' || kind === 'rfm' ? ` · ${kind.toUpperCase()}` : ''
    const date = new Date(run.created_at)
    const time = Number.isNaN(date.getTime()) ? '时间待核对' : date.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
    const label = `${index === 0 ? '最新记录' : `记录 ${index + 1}`} · ${time}${mode} · ${stateLabel[run.status] ?? '状态待确认'}`
    return { value: run.id, label, title: label }
  })
  return <div className="analysis-history">
    <label htmlFor={id}>历史结果（{history.length}条）</label>
    <Select id={id} aria-label={`${title}历史结果`} value={selected || undefined} options={options}
      placeholder="选择历史结果" onChange={onSelect} virtual={false}
      classNames={{ popup: { root: 'analysis-history-popup' } }} />
  </div>
}
