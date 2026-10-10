import { useEffect, useState } from 'react'
import { Alert, App, Button, Select, Table, Tag } from 'antd'
import { CheckCircleOutlined, ExclamationCircleOutlined, InfoCircleOutlined, PlayCircleOutlined } from '@ant-design/icons'
import type { QualityReport as Report } from '../quality'
import type { AssociationReport, ClusterReport, QualityRun } from '../quality'
import { associationDefaults, clusterDefaults, finished, qualityApi, stateLabel, viewLabels } from '../quality'

const names: Record<string, string> = {
  source_row_id: '来源记录', order_id: '订单 / 篮子', item_id: '商品标识', customer_id: '客户标识',
  event_time: '交易时间（UTC）', currency: '币种', amount: '金额', amount_source: '金额来源', source_rows: '原始明细数', selected_rows: '保留明细数',
  effective_source_rows: '去重后明细数', partial_order: '部分订单',
  primary_reason: '基础处理', rf_reason: 'RF 处理', rfm_reason: 'RFM 处理', amount_reason: '金额处理', association_reason: '购物篮处理', issues: '问题标签',
}
const moneySources: Record<string, string> = { selected_lines: '筛选后的可靠行金额', order_amount_once: '订单总额，每单计一次', line_amount: '行金额', quantity_unit_price: '数量 × 单价', none: '不使用金额' }

export function QualityReport({ report, projectId, runId }: { report: Report; projectId: string; runId: string }) {
  const [view, setView] = useState('row_audit')
  const [preview, setPreview] = useState<{ items: Record<string, unknown>[]; total: number } | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true
    setPreview(null); setError('')
    qualityApi.rows(projectId, runId, view).then(value => { if (active) setPreview(value) })
      .catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [projectId, runId, view, retry])
  const s = report.summary
  const overview = [
    ['原始记录', report.raw_rows, '完整保留来源'],
    ['有效正向记录', report.views.common.included_rows, '范围与基础规则通过'],
    ['有效客户', s.rf_customers, `${s.rf_orders.toLocaleString()} 个有效订单`],
    ['完整购物篮', s.complete_baskets, `${s.unique_items.toLocaleString()} 类商品`],
  ]
  const rowText = (key: string, value: unknown) => {
    if (value === null || value === undefined) return '—'
    if (key === 'issues' && Array.isArray(value)) return value.map(v => report.reason_labels[String(v)] ?? String(v)).join('；') || '无'
    if (key.endsWith('_reason')) return report.reason_labels[String(value)] ?? String(value)
    if (key === 'amount_source') return moneySources[String(value)] ?? String(value)
    if (typeof value === 'boolean') return value ? '是' : '否'
    return String(value)
  }
  const capabilities = [
    ['rf', '客户行为分群 · RF', '根据最近购买时间与购买频次，判断客户行为是否适合分组。'],
    ['rfm', '客户行为分群 · RFM', '在可靠的时间与频次之外，纳入已核验的购买金额。'],
    ['association', '商品共购分析', '使用成员完整的购物篮，探索商品同时出现的关系。'],
  ]
  return <div className="quality-report">
    <div className="quality-metrics">{overview.map(([label, count, help]) => <article key={label}><span>{label}</span><strong>{Number(count).toLocaleString()}</strong><small>{help}</small></article>)}</div>
    <div className="quality-section-title"><div><h3>这份数据适合做什么</h3><p>输入条件通过后，仍需在实际分析时检验结果质量。</p></div><span>字段版本 M{report.context.mapping_revision}</span></div>
    <div className="capability-grid">{capabilities.map(([key, title, description]) => {
      const cap = report.capabilities[key]
      return <article key={key} className={`capability-card ${cap.allowed ? 'ready' : 'restricted'}`}>
        <div className="capability-top">{cap.allowed ? <CheckCircleOutlined /> : <InfoCircleOutlined />}<Tag color={cap.allowed ? 'cyan' : 'default'}>{cap.allowed ? cap.state === 'limited' ? '部分数据可用' : '输入条件满足' : cap.state === 'resource_limited' ? '请缩小范围' : '当前不适用'}</Tag></div>
        <h4>{title}</h4><p>{description}</p>
        {cap.reasons.length ? <ul>{cap.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul> : <div className="capability-foot">{key === 'rf' ? `${s.rf_customers} 个客户 · ${s.rf_orders} 个订单` : key === 'rfm' ? `${s.rfm_customers} 个金额完整客户 · ${s.rfm_orders} 个订单` : `${s.complete_baskets} 个完整购物篮 · ${s.singleton_baskets} 个单商品篮`}</div>}
      </article>
    })}</div>
    <ClusterPanel report={report} projectId={projectId} qualityRunId={runId} />
    <AssociationPanel report={report} projectId={projectId} qualityRunId={runId} />
    <div className="quality-section-title"><div><h3>每条记录都有去向</h3><p>每一行在每个视图中仅归入一个主要原因，各视图的纳入与排除之和均等于原始行数。</p></div></div>
    <div className="quality-ledger">{Object.entries(report.views).map(([key, counts]) => <div className="ledger-row" key={key}>
      <div className="ledger-label"><strong>{viewLabels[key]}</strong><span>纳入 {counts.included_rows.toLocaleString()} · 排除 {counts.excluded_rows.toLocaleString()}</span></div>
      <div className="ledger-bar" role="img" aria-label={`${viewLabels[key]}纳入${counts.included_rows}行，排除${counts.excluded_rows}行`}><i style={{ width: `${report.raw_rows ? counts.included_rows / report.raw_rows * 100 : 0}%` }} /></div>
      <div className="reason-chips">{Object.entries(counts.primary_reasons).filter(([reason]) => reason !== 'included').map(([reason, count]) => <span key={reason}>{report.reason_labels[reason] ?? reason}<b>{count.toLocaleString()}</b></span>)}</div>
    </div>)}</div>
    <div className="quality-notes"><ExclamationCircleOutlined /><div><strong>理解分析范围</strong><ul>{report.warnings.map(text => <li key={text}>{text}</li>)}</ul>
      <p>时间范围：{report.scope.date_start ?? '不限起点'} 至 {report.scope.date_end ?? '不限终点'}；币种：{report.scope.currency ?? (s.currencies.join('、') || '未指定')}。有效金额为正向购买金额，未净扣退货。</p>
      <p>国家 / 地区：{report.scope.countries.join('、') || '全部'}；商品范围：{report.scope.item_ids.join('、') || '全部'}。</p>
      <p>本次策略：{report.policy.duplicates === 'keep' ? '保留完全重复候选' : '移除完全重复记录'}；{report.policy.monetary_subset === 'complete_customers' ? '明确选择金额完整客户评估 RFM' : '金额不完整时优先使用 RF'}；{report.policy.accept_selected_amount_source ? '已确认采用选定金额来源' : '金额来源冲突时等待确认'}。</p>
    </div></div>
    <div className="quality-section-title"><div><h3>查看来源与有效视图</h3><p>明细用于核对处理依据，当前预览前 20 条。</p></div>
      <Select aria-label="选择质量数据视图" value={view} onChange={setView} options={[
        { value: 'row_audit', label: '来源与排除原因' }, { value: 'rf_orders', label: 'RF 有效订单' },
        { value: 'rfm_orders', label: '金额完整客户订单' }, { value: 'amount_orders', label: '唯一订单金额' }, { value: 'basket_items', label: '完整购物篮商品' },
      ]} />
    </div>
    {error ? <Alert type="error" title={error} action={<Button onClick={() => setRetry(v => v + 1)}>重试</Button>} /> : <Table loading={!preview} size="small" pagination={false} scroll={{ x: 'max-content', y: 350 }}
      dataSource={(preview?.items ?? []).map((row, index) => ({ ...row, _key: index }))} rowKey="_key"
      columns={Object.keys(preview?.items[0] ?? {}).map(key => ({ key, dataIndex: key, title: names[key] ?? key, width: key.endsWith('_reason') || key === 'issues' ? 220 : 170,
        render: (value: unknown) => <span className="quality-cell">{rowText(key, value)}</span> }))} locale={{ emptyText: '当前视图没有符合条件的记录' }} />}
    {preview && <p className="field-help">本视图共 {preview.total.toLocaleString()} 条记录。完整来源行关联随本次结果保存。</p>}
  </div>
}

function isClusterReport(value: QualityRun['result']): value is ClusterReport {
  return Boolean(value && 'analysis' in value && 'clusters' in value)
}

function isAssociationReport(value: QualityRun['result']): value is AssociationReport {
  return Boolean(value && 'top_rules' in value && 'evaluations' in value)
}

function ClusterPanel({ report, projectId, qualityRunId }: { report: Report; projectId: string; qualityRunId: string }) {
  const [runs, setRuns] = useState<QualityRun[]>([])
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<QualityRun | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const { message } = App.useApp()
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const refresh = async () => {
      try {
        const list = await qualityApi.analysisRuns(projectId, report.context.data_version_id)
        const scoped = list.items.filter(run => run.quality_run_id === qualityRunId)
        const current = selected ? await qualityApi.run(projectId, selected) : null
        if (!active) return
        setRuns(scoped); setError('')
        if (current) setDetail(current)
        else if (scoped.length && !selected) setSelected(scoped[0].id)
      } catch (e) { if (active) setError(e instanceof Error ? e.message : '暂时无法读取分群记录。') }
      if (active) timer = setTimeout(refresh, 1800)
    }
    void refresh()
    return () => { active = false; clearTimeout(timer) }
  }, [projectId, report.context.data_version_id, qualityRunId, selected, reload])
  const submit = async (kind: 'rf' | 'rfm') => {
    setBusy(kind); setError('')
    try {
      const run = await qualityApi.cluster(projectId, qualityRunId, clusterDefaults(kind), crypto.randomUUID())
      setSelected(run.id); setDetail(run); setReload(value => value + 1)
      void message.success(`${kind.toUpperCase()} 分群已提交`)
    } catch (e) {
      const text = e instanceof Error ? e.message : '分群提交失败，请重试。'
      setError(text); void message.error(text)
    } finally { setBusy('') }
  }
  const active = detail && !finished.has(detail.status)
  const result = isClusterReport(detail?.result) ? detail.result : null
  return <section className="analysis-panel">
    <div className="quality-section-title"><div><h3>客户分群</h3><p>使用通过质量检查的订单视图，生成可复核的 RF/RFM 群体画像。</p></div>
      <div className="analysis-actions">
        <Button icon={<PlayCircleOutlined />} disabled={!report.capabilities.rf.allowed} loading={busy === 'rf'} onClick={() => void submit('rf')}>运行 RF</Button>
        <Button icon={<PlayCircleOutlined />} disabled={!report.capabilities.rfm.allowed} loading={busy === 'rfm'} onClick={() => void submit('rfm')}>运行 RFM</Button>
      </div>
    </div>
    {error && <Alert className="import-alert" type="error" showIcon title={error} />}
    <div className="quality-run-strip compact">{runs.length ? runs.map(run => <button key={run.id} className={`run-chip ${run.id === selected ? 'selected' : ''}`} onClick={() => { setSelected(run.id); setDetail(null) }}><span>{stateLabel[run.status] ?? run.status}</span><small>{run.parameters?.analysis?.kind?.toUpperCase() ?? '分群'}</small></button>) : <p>还没有客户分群记录。</p>}</div>
    {detail && <div className="cluster-result">
      <div className="quality-result-header"><div><Tag color={result?.summary.publishable ? 'cyan' : active ? 'blue' : 'default'}>{stateLabel[detail.status] ?? detail.status}</Tag><span>{detail.message}</span></div>
        {active && <Button danger onClick={async () => { try { setDetail(await qualityApi.cancel(projectId, detail.id)); void message.info('取消请求已提交') } catch (e) { void message.error(e instanceof Error ? e.message : '未能取消，请重试。') } }}>取消</Button>}</div>
      {result && <><div className="quality-metrics cluster-metrics">
        <article><span>分析模式</span><strong>{result.analysis.mode}</strong><small>参考点 {new Date(result.analysis.reference_time).toLocaleDateString('zh-CN')}</small></article>
        <article><span>有效客户</span><strong>{result.summary.customers.toLocaleString()}</strong><small>{result.summary.unique_feature_vectors.toLocaleString()} 种特征组合</small></article>
        <article><span>选择 K</span><strong>{result.summary.selected_k ?? '—'}</strong><small>{result.summary.publishable ? '可发布画像' : '不建议发布'}</small></article>
      </div>
      {!result.summary.publishable && <Alert type="warning" showIcon title="本次结果不建议作为正式分群结论" description={result.summary.reasons.join(' ')} />}
      <Table size="small" pagination={false} dataSource={result.clusters.map(row => ({ ...row, key: row.cluster }))} columns={[
        { title: '群体', dataIndex: 'cluster', render: value => `G${Number(value) + 1}` },
        { title: '客户数', dataIndex: 'customers', render: value => Number(value).toLocaleString() },
        { title: '占比', dataIndex: 'share', render: value => `${(Number(value) * 100).toFixed(1)}%` },
        { title: 'R 中位数', dataIndex: 'recency_median' },
        { title: 'F 中位数', dataIndex: 'frequency_median' },
        { title: 'M 中位数', dataIndex: 'monetary_median', render: value => value === null ? '—' : Number(value).toLocaleString() },
      ]} locale={{ emptyText: '本次没有形成可展示的群体' }} />
      <Table className="candidate-table" size="small" pagination={false} dataSource={result.candidates.map(row => ({ ...row, key: row.k }))} columns={[
        { title: 'K', dataIndex: 'k' },
        { title: '最小群体', dataIndex: 'min_cluster_size' },
        { title: '轮廓系数', dataIndex: 'silhouette', render: value => value === null ? '—' : Number(value).toFixed(3) },
        { title: 'ARI 中位数', dataIndex: 'ari_median', render: value => value === null ? '—' : Number(value).toFixed(3) },
        { title: '判定', dataIndex: 'publishable', render: value => <Tag color={value ? 'cyan' : 'default'}>{value ? '通过' : '诊断保留'}</Tag> },
      ]} /></>}
    </div>}
  </section>
}

function AssociationPanel({ report, projectId, qualityRunId }: { report: Report; projectId: string; qualityRunId: string }) {
  const [runs, setRuns] = useState<QualityRun[]>([])
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<QualityRun | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const { message } = App.useApp()
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const refresh = async () => {
      try {
        const list = await qualityApi.analysisRuns(projectId, report.context.data_version_id, 'association')
        const scoped = list.items.filter(run => run.quality_run_id === qualityRunId)
        const current = selected ? await qualityApi.run(projectId, selected) : null
        if (!active) return
        setRuns(scoped); setError('')
        if (current) setDetail(current)
        else if (scoped.length && !selected) setSelected(scoped[0].id)
      } catch (e) { if (active) setError(e instanceof Error ? e.message : '暂时无法读取共购记录。') }
      if (active) timer = setTimeout(refresh, 1800)
    }
    void refresh()
    return () => { active = false; clearTimeout(timer) }
  }, [projectId, report.context.data_version_id, qualityRunId, selected, reload])
  const submit = async () => {
    setBusy(true); setError('')
    try {
      const run = await qualityApi.associate(projectId, qualityRunId, associationDefaults(), crypto.randomUUID())
      setSelected(run.id); setDetail(run)
      setReload(value => value + 1)
      void message.success('商品共购分析已提交')
    } catch (e) {
      const text = e instanceof Error ? e.message : '共购分析提交失败，请重试。'
      setError(text); void message.error(text)
    } finally { setBusy(false) }
  }
  const active = detail && !finished.has(detail.status)
  const result = isAssociationReport(detail?.result) ? detail.result : null
  const percent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`
  return <section className="analysis-panel">
    <div className="quality-section-title"><div><h3>商品共购</h3><p>从完整购物篮中挖掘规则，并用固定留出篮评测 Top-5 补全。</p></div>
      <div className="analysis-actions"><Button icon={<PlayCircleOutlined />} disabled={!report.capabilities.association.allowed} loading={busy} onClick={() => void submit()}>运行共购</Button></div>
    </div>
    {error && <Alert className="import-alert" type="error" showIcon title={error} />}
    <div className="quality-run-strip compact">{runs.length ? runs.map(run => <button key={run.id} className={`run-chip ${run.id === selected ? 'selected' : ''}`} onClick={() => { setSelected(run.id); setDetail(null) }}><span>{stateLabel[run.status] ?? run.status}</span><small>关联规则</small></button>) : <p>还没有商品共购记录。</p>}</div>
    {detail && <div className="cluster-result">
      <div className="quality-result-header"><div><Tag color={result?.summary.publishable ? 'cyan' : active ? 'blue' : 'default'}>{stateLabel[detail.status] ?? detail.status}</Tag><span>{detail.message}</span></div>
        {active && <Button danger onClick={async () => { try { setDetail(await qualityApi.cancel(projectId, detail.id)); void message.info('取消请求已提交') } catch (e) { void message.error(e instanceof Error ? e.message : '未能取消，请重试。') } }}>取消</Button>}</div>
      {result && <><div className="quality-metrics cluster-metrics">
        <article><span>完整购物篮</span><strong>{result.summary.baskets.toLocaleString()}</strong><small>{result.summary.items.toLocaleString()} 类训练商品</small></article>
        <article><span>规则数量</span><strong>{result.summary.rules.toLocaleString()}</strong><small>{result.summary.itemsets.toLocaleString()} 个频繁项集</small></article>
        <article><span>测试篮</span><strong>{result.summary.test_baskets.toLocaleString()}</strong><small>{result.summary.publishable ? '可查看规则' : '保留诊断'}</small></article>
      </div>
      {!result.summary.publishable && <Alert type="warning" showIcon title="本次结果不建议作为正式共购结论" description={result.summary.reasons.join(' ')} />}
      <Table size="small" pagination={{ pageSize: 8 }} dataSource={result.top_rules.map((row, index) => ({ ...row, key: index }))} columns={[
        { title: '前件', dataIndex: 'antecedents' },
        { title: '后件', dataIndex: 'consequents' },
        { title: '共同次数', dataIndex: 'n_ab' },
        { title: '支持度', dataIndex: 'support', render: (value: number) => percent(value) },
        { title: '置信度', dataIndex: 'confidence', render: (value: number) => percent(value) },
        { title: 'Lift', dataIndex: 'lift', render: (value: number) => value.toFixed(2) },
      ]} locale={{ emptyText: '当前阈值下没有形成规则' }} scroll={{ x: 'max-content' }} />
      <Table className="candidate-table" size="small" pagination={false} dataSource={result.evaluations.map(row => ({ ...row, key: row.split }))} columns={[
        { title: '集合', dataIndex: 'split', render: (value: string) => value === 'test' ? '测试集' : '验证集' },
        { title: '评测篮', dataIndex: 'baskets' },
        { title: '规则 Hit@5', dataIndex: 'hit_rate_at_5', render: (value: number | null) => percent(value) },
        { title: '规则覆盖率', dataIndex: 'recommendation_coverage', render: (value: number | null) => percent(value) },
        { title: '热门 Hit@5', dataIndex: 'popularity_hit_rate_at_5', render: (value: number | null) => percent(value) },
      ]} /></>}
    </div>}
  </section>
}
