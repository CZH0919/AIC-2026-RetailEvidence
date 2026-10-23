import { useEffect, useState } from 'react'
import { Alert, Button, Dropdown, Input, Spin } from 'antd'
import { MoreOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import type { Version } from '../data'
import type { AssociationReport, QualityReport, QualityRun } from '../quality'
import { EmptyState, LoadingState } from './States'
import { SalesImportWizard } from './SalesImportWizard'
import { salesApi } from '../retail'
import type { SalesRun } from '../retail'
import type { useAutomaticAnalyses } from './useAutomaticAnalyses'
import { useSalesReports } from './useSalesReports'
import { ReportPicker, ReportHistory, HistoricalReportNotice } from './ReportPicker'
import { monthLabel } from '../reportSelection'

const count = (value: number) => value.toLocaleString('zh-CN')
const percent = (value: number) => `${(value * 100).toFixed(1)}%`
const items = (value: string) => value.split(' | ').filter(Boolean)

export default function PairingWorkspace({ projectId }: { projectId: string }) {
  const selection = useSalesReports(projectId, 'overview')
  const {versions, runs, current, loading, switching} = selection
  const [params] = useSearchParams()
  const [uploading, setUploading] = useState(false), [history, setHistory] = useState(false)
  if (loading) return <LoadingState />
  const sources = versions.filter(v => current?.result?.sources.some(s => s.version_id === v.id))
  const version = sources.find(v => v.id === params.get('pairingSource')) ?? sources.at(-1)
  const choose = async (id: string) => { if (await selection.choose(id)) setHistory(false) }
  return <div className="pairing-workspace">
    <header className="pairing-header"><div><h2>搭配建议</h2><p>看看所选月份哪些商品经常一起买。</p></div>
      <div className="report-pairing-toolbar"><ReportPicker runs={runs} current={current} disabled={!!switching} onChoose={id => void choose(id)} />
      <Dropdown trigger={['click']} menu={{items: [{key: 'history', label: '历史报告'}], onClick: () => setHistory(true)}}><Button type="text" icon={<MoreOutlined />} aria-label="更多操作">更多</Button></Dropdown></div>
    </header>
    {selection.error && <Alert type="error" title={selection.error} action={<Button onClick={() => void selection.retry()}>重试</Button>} />}
    <HistoricalReportNotice runs={runs} current={current} disabled={!!switching} onChoose={id => void choose(id)} />
    {switching ? <div className="report-switching" role="status"><Spin /><span>正在加载 {switching}</span></div> : current?.result && version ? <>
      <div className="pairing-context"><span>销售月份：{monthLabel(current.result.month)}</span>
      {sources.length > 1 && <span>使用月报中的 {sources.length} 份销售表</span>}</div>
      <PairingAnalysis key={`${projectId}:${current.id}:${version.id}:${params.get('pairingRun') ?? ''}`} salesRun={current} projectId={projectId} version={version} automatic={selection.automatic} onUpload={() => setUploading(true)} />
    </> : !selection.error && <EmptyState title="先生成销售月报" description="上传销售表后，再查看对应月份的搭配建议。" action={<Button type="primary" onClick={() => setUploading(true)}>上传销售表</Button>} />}
    <ReportHistory open={history} onClose={() => setHistory(false)} runs={runs} current={current} versions={versions} disabled={!!switching} onChoose={id => void choose(id)} />
    {uploading && <SalesImportWizard projectId={projectId} versions={versions} onClose={() => { setUploading(false); void selection.reload() }} onDone={run => { setUploading(false); void selection.reload(run.id) }} />}
  </div>
}

function PairingAnalysis({ projectId, version, onUpload, salesRun, automatic }: { salesRun: SalesRun; projectId: string; version: Version; onUpload: () => void; automatic: ReturnType<typeof useAutomaticAnalyses> }) {
  const [current, setCurrent] = useState<QualityRun | null>(null), [basis, setBasis] = useState<QualityReport | null>(null)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const step = automatic.data?.steps.association
  useEffect(() => {
    let active = true
    setError('')
    salesApi.pairings(projectId, salesRun.id, version.id, null).then(result => {
      if (active) { setCurrent(result.current); setBasis(result.basis) }
    }).catch(() => { if (active) setError('暂时无法读取搭配结果，请重试。') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [projectId, salesRun.id, version.id, step?.status, step?.run_id, retry])
  const month = salesRun.result!.month
  const end = new Date(Number(month.slice(0, 4)), Number(month.slice(5)), 0).getDate()
  const report = current?.result as AssociationReport | null
  const running = !step || !['ready', 'no_result', 'skipped', 'failed'].includes(step.status)
  if (loading) return <LoadingState />
  return <>
    <div className="pairing-context"><span>使用订单：{month}-01 至 {month}-{end}</span></div>
    {(error || automatic.error) && <Alert type="error" showIcon message={error || automatic.error} action={<Button size="small" onClick={() => setRetry(n => n + 1)}>重试</Button>} />}
    {running ? <div role="status" className="pairing-status"><Spin /><h3>{step?.status === 'running' ? '正在查找常见商品搭配' : '正在自动整理订单'}</h3><p>完成后会自动显示结果，无需另外点击分析。</p></div>
      : step?.status === 'skipped' ? <EmptyState compact title="当前数据暂不能分析搭配" description={step.message} action={<Button type="primary" onClick={onUpload}>上传订单明细</Button>} />
      : step?.status === 'failed' ? <EmptyState compact title="搭配分析未完成" description={step.message} action={<Button onClick={automatic.retry}>重试分析</Button>} />
      : report?.summary.publishable && report.top_rules.some(rule => rule.lift > 1) ? <PairingResults key={current!.id} report={report} />
      : <EmptyState compact title="暂时没找到常见搭配" description="这批订单中，暂时没发现明显的共同购买规律。" />}
    {!!report && !running && step?.status !== 'skipped' && <details className="pairing-method"><summary>分析方法与详细结果</summary>
      <p>使用 FP-growth 查找同一订单中出现的商品组合，再按共同购买次数、购买比例和关联强度筛选。</p>
      <p>本次有 {count(report.summary.baskets)} 笔订单，其中 {count(report.summary.train_baskets)} 笔用于发现搭配，其余用于检查结果。页面中的比例来自发现搭配的订单。</p>
      <p>共同购买至少 {report.analysis.min_count} 次，支持度至少 {percent(report.analysis.min_support)}，置信度至少 {percent(report.analysis.min_confidence)}。默认先看5组。</p>
      {report.evaluation_notice && <p>{report.evaluation_notice}</p>}
      {!!basis?.scope.date_start && <p>只使用 {basis.scope.date_start} 至 {basis.scope.date_end} 的订单。</p>}
    </details>}
  </>
}

function PairingResults({ report }: { report: AssociationReport }) {
  const [params] = useSearchParams()
  let focused: string[] = []
  try { const value: unknown = JSON.parse(params.get('pairingItems') ?? '[]'); if (Array.isArray(value) && value.every(v => typeof v === 'string')) focused = value } catch { /* optional link context */ }
  const [all, setAll] = useState(false), [query, setQuery] = useState('')
  const seen = new Set<string>()
  const rules = report.top_rules.filter(rule => {
    const key = [...items(rule.antecedents), ...items(rule.consequents)].sort().join('\u0000')
    if (seen.has(key) || rule.lift <= 1) return false
    seen.add(key); return true
  })
  if (focused.length) rules.sort((a, b) => {
    const matches = (r: typeof a) => [...items(r.antecedents), ...items(r.consequents)].sort().join('\u0000') === [...focused].sort().join('\u0000')
    return Number(matches(b)) - Number(matches(a))
  })
  const filtered = rules.filter(r => `${r.antecedents} ${r.consequents}`.toLowerCase().includes(query.toLowerCase().trim()))
  const visible = all ? filtered : rules.slice(0, 5)
  return <section className="pairing-results">
    <div className="pairing-intro"><h3>这些商品经常一起买</h3><p>可作为相邻摆放或组合展示的候选；历史搭配不能保证销售收益。</p><p>以下次数与比例来自 {count(report.summary.train_baskets)} 笔历史订单。</p></div>
    {all && <Input.Search aria-label="搜索搭配商品" placeholder="搜索商品名称" allowClear value={query} onChange={e => setQuery(e.target.value)} className="pairing-search" />}
    <ol className="pairing-list">{visible.map((rule, index) => <li key={`${rule.antecedents}:${rule.consequents}`}>
      <span className="pairing-number" aria-hidden="true">{index + 1}</span>
      <article><h4 className="pairing-items">{[...items(rule.antecedents), ...items(rule.consequents)].map((item, i) => <span key={item}>{i > 0 && <b aria-hidden="true">＋</b>}<span className="pairing-item">{item}</span></span>)}</h4>
        <p>买了「{items(rule.antecedents).join('」和「')}」的 {count(rule.n_a)} 笔订单中，<strong>{count(rule.n_ab)} 笔</strong>也买了「{items(rule.consequents).join('」和「')}」。</p>
        <div className="pairing-proportion"><span>一起购买的比例 <strong>{percent(rule.confidence)}</strong></span><div className="pairing-bar" aria-hidden="true"><span style={{ width: `${Math.min(100, rule.confidence * 100)}%` }} /></div></div>
        <details className="pairing-rule-details"><summary>为什么推荐这组商品</summary><p>共分析 {count(rule.denominator)} 笔订单，有 {count(rule.n_ab)} 笔同时买了这组商品，占 {percent(rule.support)}。</p><p>买了「{items(rule.antecedents).join('」和「')}」的订单，购买「{items(rule.consequents).join('」和「')}」的比例，是全部订单中购买后者比例的 {rule.lift.toFixed(2)} 倍。</p>{rule.validation_n_ab !== undefined && <p>另一批 {count(rule.validation_denominator ?? 0)} 笔订单中，观察到 {count(rule.validation_n_ab)} 次共同购买，关联方向保持一致。</p>}{rule.confidence_lower !== undefined && <p>考虑订单样本量后，购买比例的历史参考范围约为 {percent(rule.confidence_lower)} 至 {percent(rule.confidence_upper ?? 1)}。它仅辅助判断这组记录，不保证未来表现。</p>}</details>
      </article>
    </li>)}</ol>
    {!visible.length && <p className="pairing-muted">没有找到匹配的商品搭配。</p>}
    {rules.length > 5 && <Button className="pairing-toggle" onClick={() => { setAll(v => !v); setQuery('') }}>{all ? '收起，先看 5 组' : `查看更多搭配（${rules.length} 组）`}</Button>}
    {!rules.length && <p className="pairing-muted">现有结果中，没有比随机共同购买更明显的商品组合。</p>}
  </section>
}
