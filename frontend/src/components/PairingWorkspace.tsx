import { useEffect, useState } from 'react'
import { Alert, Button, Input, Select } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { dataApi } from '../data'
import type { Version, VersionDetail } from '../data'
import { associationDefaults, cleanDefaults, finished, qualityApi, scopeDefaults } from '../quality'
import type { AssociationReport, QualityReport, QualityRun } from '../quality'
import { EmptyState, ErrorState, LoadingState } from './States'
import { SalesImportWizard } from './SalesImportWizard'

const count = (value: number) => value.toLocaleString('zh-CN')
const percent = (value: number) => `${(value * 100).toFixed(1)}%`
const items = (value: string) => value.split(' | ').filter(Boolean)

export default function PairingWorkspace({ projectId }: { projectId: string }) {
  const [versions, setVersions] = useState<Version[]>([])
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const [params, setParams] = useSearchParams()
  const [uploading, setUploading] = useState(false)
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    dataApi.versions(projectId).then(data => { if (active) setVersions(data.items) })
      .catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [projectId, retry])
  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={() => setRetry(v => v + 1)} />
  const version = versions.find(v => v.id === params.get('pairingSource')) ?? versions[0]
  return <div className="pairing-workspace">
    <header className="pairing-header"><div><h2>搭配建议</h2><p>看看哪些商品经常一起买，帮助安排摆放和组合销售。</p></div>
      {version && <label className="pairing-source">使用的表格<Select aria-label="搭配分析数据" value={version.id} options={versions.map(v => ({ value: v.id, label: v.filename }))} onChange={id => { const next = new URLSearchParams(params); next.set('pairingSource', id); setParams(next) }} /></label>}
    </header>
    {version ? <PairingAnalysis key={`${projectId}:${version.id}`} projectId={projectId} version={version} onUpload={() => setUploading(true)} /> : <EmptyState title="先上传订单明细" description="表格需要记录每笔订单里买了哪些商品。" action={<Button type="primary" onClick={() => setUploading(true)}>上传订单明细</Button>} />}
    {uploading && <SalesImportWizard projectId={projectId} versions={versions} onClose={() => { setUploading(false); setRetry(v => v + 1) }} onDone={run => {
      setUploading(false); setRetry(v => v + 1)
      const id = run.result?.sources.at(-1)?.version_id
      if (id) { const next = new URLSearchParams(params); next.set('pairingSource', id); setParams(next) }
    }} />}
  </div>
}

function PairingAnalysis({ projectId, version, onUpload }: { projectId: string; version: Version; onUpload: () => void }) {
  const [source, setSource] = useState<VersionDetail | null>(null)
  const [current, setCurrent] = useState<QualityRun | null>(null), [prepared, setPrepared] = useState<QualityRun | null>(null)
  const [basis, setBasis] = useState<QualityReport | null>(null)
  const [task, setTask] = useState<{ phase: 'prepare' | 'analyze'; run: QualityRun; key: string } | null>(null)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0), [busy, setBusy] = useState(false), [pollRetry, setPollRetry] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    async function load() {
      const [detail, analyses, checks] = await Promise.all([dataApi.version(projectId, version.id), qualityApi.analysisRuns(projectId, version.id, 'association'), qualityApi.runs(projectId, version.id)])
      const check = checks.items.find(r => ['succeeded', 'completed_with_warnings', 'not_applicable'].includes(r.status))
      const [run, ready] = await Promise.all([analyses.items[0] ? qualityApi.run(projectId, analyses.items[0].id) : null, check ? qualityApi.run(projectId, check.id) : null])
      const parent = run?.quality_run_id && run.quality_run_id !== ready?.id ? await qualityApi.run(projectId, run.quality_run_id) : ready
      if (active) {
        setSource(detail); setCurrent(run); setPrepared(ready); setBasis(parent?.result as QualityReport | null)
        if (run && !finished.has(run.status)) setTask({ phase: 'analyze', run, key: crypto.randomUUID() })
      }
    }
    load().catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [projectId, version.id, retry])
  useEffect(() => {
    if (!task) return
    let active = true, polling = false
    const timer = window.setInterval(async () => {
      if (polling) return
      polling = true
      try {
        const run = await qualityApi.run(projectId, task.run.id)
        if (!active) return
        if (task.phase === 'analyze') {
          setCurrent(run)
          if (finished.has(run.status)) setTask(null)
        } else if (finished.has(run.status)) {
          const report = run.result as QualityReport | null
          setPrepared(run); setBasis(report)
          if (report?.capabilities?.association?.allowed && report.context.mapping_revision === source?.mapping.revision) {
            const analysis = await qualityApi.associate(projectId, run.id, associationDefaults(), task.key)
            if (active) { setCurrent(analysis); setTask({ ...task, phase: 'analyze', run: analysis }) }
          } else {
            setTask(null)
            if (!report) setError(`订单整理未完成：${run.message}`)
          }
        }
      } catch (e) { if (active) { setError((e as Error).message); window.clearInterval(timer) } }
      finally { polling = false }
    }, 1800)
    return () => { active = false; window.clearInterval(timer) }
  }, [projectId, task?.run.id, task?.phase, source?.mapping.revision, pollRetry])
  const mapping = source?.mapping.config
  const summaryTable = mapping?.record_kind === 'monthly_summary' || mapping?.record_kind === 'daily_summary'
  const missingOrders = mapping?.order_boundary === 'unavailable' || (!mapping?.columns.order_id && mapping?.order_boundary !== 'row_basket')
  const unsupported = summaryTable ? '这份表只有商品的汇总销量，没有每笔订单的商品明细，无法判断哪些商品经常一起买。'
    : missingOrders ? '这份表没有标明哪些商品属于同一笔订单，无法分析商品搭配。'
    : !mapping?.columns.item_id ? '还没有指定商品名称或编号所在列，无法分析商品搭配。' : ''
  const readyReport = prepared?.result as QualityReport | null
  const matching = readyReport?.context.mapping_revision === source?.mapping.revision
  const blocked = !!readyReport && matching && !readyReport.capabilities.association?.allowed
  const blockedReason = readyReport && blocked ? readyReport.summary.complete_baskets < 200
    ? `能用于分析的订单只有 ${count(readyReport.summary.complete_baskets)} 笔，至少需要 200 笔。可以上传更多订单明细。`
    : readyReport.summary.unique_items < 2 ? '订单里至少需要两种商品，才能分析搭配。'
    : readyReport.capabilities.association.reasons.join('；').replace('购物篮或商品规模超出分析范围，请缩小业务筛选范围。', '订单或商品较多，请分成较小的表格后分析。') : ''
  const report = current?.result as AssociationReport | null
  const stale = !!report && report.context.mapping_revision !== source?.mapping.revision
  const running = !!task
  async function analyze() {
    if (!source || unsupported || blocked || busy || running) return
    setBusy(true); setError('')
    const key = crypto.randomUUID()
    try {
      if (prepared && readyReport?.capabilities.association?.allowed && matching) {
        const run = await qualityApi.associate(projectId, prepared.id, associationDefaults(), key)
        setCurrent(run); setBasis(readyReport); setTask({ phase: 'analyze', run, key })
      } else {
        const policy = await qualityApi.policy(projectId, version.id, source.mapping.revision, cleanDefaults)
        const run = await qualityApi.submit(projectId, version.id, policy.id, scopeDefaults, crypto.randomUUID())
        setTask({ phase: 'prepare', run, key })
      }
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  if (loading) return <LoadingState />
  if (!source) return <ErrorState message={error || '暂时无法读取这份表格。'} onRetry={() => setRetry(v => v + 1)} />
  const scope = basis?.scope
  const range = scope?.date_start || scope?.date_end ? `${scope.date_start ?? '最早记录'} 至 ${scope.date_end ?? '最新记录'}` : '所选文件中的全部订单'
  return <>
    {!unsupported && <div className="pairing-context"><span>使用订单：{range}{!!scope?.countries.length && ` · ${scope.countries.join('、')}`}{!!scope?.item_ids.length && ` · ${scope.item_ids.length} 款指定商品`}</span>
      {!blocked && <Button size="small" loading={busy} disabled={running} onClick={() => void analyze()}>{current ? '重新分析' : '分析搭配'}</Button>}
    </div>}
    {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={() => { setError(''); task ? setPollRetry(v => v + 1) : setRetry(v => v + 1) }}>重试</Button>} />}
    {unsupported || blocked ? <EmptyState compact title="这份表暂时不能分析搭配" description={unsupported || blockedReason} action={<div><div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}><Button type="primary" onClick={onUpload}>上传订单明细</Button><Button href={`/projects/${projectId}`}>返回销售总览</Button></div><p>订单明细需要包含订单编号和商品名称；同一笔订单的商品使用相同的订单编号。</p></div>} />
      : running ? <div role="status" className="pairing-status"><h3>{task.phase === 'prepare' ? '正在整理订单' : '正在查找常见商品搭配'}</h3><p>请稍候，完成后会自动显示结果。</p></div>
      : stale ? <EmptyState compact title="表格内容已调整" description="点击“重新分析”，更新搭配建议。" />
      : report?.summary.publishable && report.top_rules.some(rule => rule.lift > 1) ? <PairingResults key={current!.id} report={report} />
      : <EmptyState compact title={report ? '暂时没找到常见搭配' : current ? '搭配分析未完成' : '查看哪些商品经常一起买'} description={report ? '这批订单中，暂时没发现明显的共同购买规律。' : current ? current.message : '点击“分析搭配”，程序会整理订单并查找经常一起购买的商品。'} />}
    {!!report && !stale && !running && !unsupported && <details className="pairing-method"><summary>分析方法与详细结果</summary>
      <p>使用 FP-growth 查找同一订单中出现的商品组合，再按共同购买次数、购买比例和关联强度筛选。</p>
      <p>本次有 {count(report.summary.baskets)} 笔订单，其中 {count(report.summary.train_baskets)} 笔用于发现搭配，其余用于检查结果。页面中的比例来自发现搭配的订单。</p>
      <p>筛选条件：共同购买至少 {report.analysis.min_count} 次，支持度至少 {percent(report.analysis.min_support)}，置信度至少 {percent(report.analysis.min_confidence)}。{report.evaluation_notice ? '先核对完整结果中的共同次数、热门影响和另一批订单中的表现，再展示有依据的组合。' : '从已有结果的前 50 条中展示关联强度大于 1 的组合。'}默认先看 5 组。</p>
      {report.evaluation_notice && <p>{report.evaluation_notice}</p>}
      {report.evaluations.filter(e => e.split === 'test').map(e => <p key={e.split}>测试订单中的推荐命中率：{e.hit_rate_at_5 === null ? '无结果' : percent(e.hit_rate_at_5)}；只推荐热门商品时的命中率：{e.popularity_hit_rate_at_5 === null ? '无结果' : percent(e.popularity_hit_rate_at_5)}。</p>)}
      {!!report.summary.reasons.length && <p>{report.summary.reasons.join('；')}</p>}
      <p>分析时间：{new Date(current!.finished_at ?? current!.created_at).toLocaleString('zh-CN')}。</p>
    </details>}
  </>
}

function PairingResults({ report }: { report: AssociationReport }) {
  const [all, setAll] = useState(false), [query, setQuery] = useState('')
  const seen = new Set<string>()
  const rules = report.top_rules.filter(rule => {
    const key = [...items(rule.antecedents), ...items(rule.consequents)].sort().join('\u0000')
    if (seen.has(key) || rule.lift <= 1) return false
    seen.add(key); return true
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
