import { Checkbox, DatePicker, Input } from 'antd'
import dayjs from 'dayjs'
import { coverageReadiness } from '../coverageReadiness'

export function CoverageConfirmation({month, kinds, complete, start, end, missing, closed, onComplete, onStart, onEnd, onMissing, onClosed}: {
  month: string; kinds: string[]; complete: boolean; start: string; end: string; missing: string; closed: string
  onComplete: (value: boolean) => void; onStart: (value: string) => void; onEnd: (value: string) => void; onMissing: (value: string) => void; onClosed: (value: string) => void
}) {
  const readiness = coverageReadiness({month, kinds, complete, start, end, missing})
  return <section className="sales-coverage" aria-label="记录完整性与可用分析">
    <div className="sales-coverage-heading"><h3>记录范围与可用分析</h3><span>{complete ? '已选择确认，请核对日期' : '尚未确认完整'}</span></div>
    <Checkbox checked={complete} onChange={e => onComplete(e.target.checked)}>我已核对指定日期范围内的销售记录，没有漏传（单独列出的缺失日除外）</Checkbox>
    {complete && <>
      <div className="sales-upload-grid"><label className="sales-upload-field"><span>完整记录开始日</span><DatePicker aria-label="完整记录开始日" format="YYYY-MM-DD" placeholder="选择开始日期" value={start ? dayjs(start) : null} onChange={value => onStart(value?.format('YYYY-MM-DD') ?? '')} /></label><label className="sales-upload-field"><span>完整记录截止日</span><DatePicker aria-label="完整记录截止日" format="YYYY-MM-DD" placeholder="选择截止日期" value={end ? dayjs(end) : null} onChange={value => onEnd(value?.format('YYYY-MM-DD') ?? '')} /></label></div>
      <p className="sales-upload-muted">请填写实际覆盖范围，包含没有成交的日期。第一笔和最后一笔销售的日期不一定是记录边界。</p>
      <div className="sales-upload-grid"><label className="sales-upload-field"><span>记录缺失日期（可选）</span><Input aria-label="记录缺失日期" placeholder="例如 2026-10-03，多天用英文逗号隔开" value={missing} onChange={e => onMissing(e.target.value)} /><small>漏传或无法确认的日期保留未知，不算作零销量。</small></label>
        <label className="sales-upload-field"><span>停业日期（可选）</span><Input aria-label="上传流程停业日期" placeholder="例如 2026-10-01，多天用英文逗号隔开" value={closed} onChange={e => onClosed(e.target.value)} /><small>只填写已确认停业且没有成交的日期。</small></label></div>
    </>}
    <div className="sales-coverage-capabilities" aria-live="polite"><p>{readiness.summary}</p>
      <dl><div><dt>未来七天销量</dt><dd>{readiness.forecast}</dd></div><div><dt>每日销量异常</dt><dd>{readiness.anomaly}</dd></div></dl>
      <small>系统将结合每件商品的有效成交记录、历史长度与检验误差，确定可用的预测。</small>
    </div>
  </section>
}
