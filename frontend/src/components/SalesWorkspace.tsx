import { ProductSignals, ChangeExplanation, AnomalyExplanation } from './ProductSignals'
import { quantityUnit } from '../quantity'
import { SalesAssistantQuestions } from './SalesAssistantQuestions'
import { useEffect, useRef, useState } from 'react'
import { Alert, App, Button, Checkbox, Drawer, Dropdown, Input, InputNumber, Select, Segmented, Spin, Table } from 'antd'
import { DownloadOutlined, FileSearchOutlined, MessageOutlined, PlusOutlined, MoreOutlined, SendOutlined, StopOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { itemKindOptions, salesApi } from '../retail'
import type { SalesAction, SalesProduct, SalesReport, SavedRecord, SourceRecords } from '../retail'
import { SalesImportWizard } from './SalesImportWizard'
import { SalesChart } from './SalesChart'
import { SalesOverview } from './SalesOverview'
import { SalesReportExplanation } from './SalesReportExplanation'
import { ProductNote } from './ProductNote'
import { ProductEvidence } from './ProductEvidence'
import { SalesTypeReview } from './SalesTypeReview'
import { EmptyState, LoadingState } from './States'
import { useSalesReports } from './useSalesReports'
import { AutomaticAnalysisStatus } from './AutomaticAnalysisStatus'
import { ReportPicker, ReportHistory, HistoricalReportNotice } from './ReportPicker'

const number = (v: number | null | undefined) => v == null ? '—' : v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
const methods: Record<string, string> = { gradient_boosting: '历史销售参考', last_week: '上一周销量参考', four_week_mean: '过去四周平均参考', exponential_smoothing: '近期销量平滑参考', croston_sba: '间歇成交参考' }
const flagNames: Record<string, string> = { growth: '卖得更多', decline: '卖得更少', anomaly: '变化需核对', contribution: '销售额贡献较高' }

export default function SalesWorkspace({ projectId, productsMode = false }: { projectId: string; productsMode?: boolean }) {
  const selection = useSalesReports(projectId, productsMode ? 'products' : 'overview')
  const {versions, runs, current, loading, switching, reload, task} = selection
  const [history, setHistory] = useState(false)
  async function chooseReport(id: string) {
    setDetailId(null); setEvidence(false); setAi(false); setExporting(false); setTypeReview(null); setActionEdit(null)
    if (await selection.choose(id)) { setChartScope('current'); setHistory(false); setQuery(''); setSignal('all'); setCategory('all') }
  }
  const [error, setError] = useState(''), [importing, setImporting] = useState(false), [composing, setComposing] = useState(false)
  const [busy, setBusy] = useState(false), [detailId, setDetailId] = useState<string | null>(null), [evidence, setEvidence] = useState(false), [exporting, setExporting] = useState(false), [allExport, setAllExport] = useState(false)
  const [records, setRecords] = useState<Record<string, SavedRecord>>({}), [actionEdit, setActionEdit] = useState<string | null>(null), [note, setNote] = useState('')
  const [query, setQuery] = useState(''), [signal, setSignal] = useState('all'), [ai, setAi] = useState(false), [question, setQuestion] = useState(''), [answer, setAnswer] = useState(''), [aiBusy, setAiBusy] = useState(false)
  const [chartScope, setChartScope] = useState('current')
  const [answerError, setAnswerError] = useState(''), [answerSource, setAnswerSource] = useState(''), [answeredQuestion, setAnsweredQuestion] = useState('')
  const aiGeneration = useRef(0)
  const [recordRows, setRecordRows] = useState<SourceRecords | null>(null)
  const [category, setCategory] = useState('all')
  const [customerAction, setCustomerAction] = useState<{runId: string; action: SalesAction} | null>(null)
  const [inventory, setInventory] = useState({ available: 0, incoming: 0, reserve: 0, pack_size: 1, arrival_date: '', confirmed: false })
  const [inventorySet, setInventorySet] = useState(false)
  const [typeReview, setTypeReview] = useState<{focusId?: string} | null>(null)
  const [params] = useSearchParams(), navigate = useNavigate(), { message } = App.useApp()
  const [detailProduct, setDetailProduct] = useState<{runId: string; item: SalesProduct} | null>(null)
  const [relatedReport, setRelatedReport] = useState<{runId: string; report: SalesReport} | null>(null)
  const report = current?.result
  const unit = quantityUnit(report?.summary.unit)
  const product = detailProduct?.runId === current?.id && detailProduct?.item.id === detailId ? detailProduct.item : undefined
  const related = relatedReport && relatedReport.runId === current?.id ? relatedReport.report : report
  const root = `/projects/${projectId}`
  async function ensureProducts() {
    if (relatedReport && relatedReport.runId === current?.id) return relatedReport.report
    if (!current) throw new Error('月报尚未完成。')
    const run = await salesApi.workspace(projectId, current.id, 'products')
    if (!run.result) throw new Error('月报尚未完成。')
    setRelatedReport({runId: run.id, report: run.result})
    return run.result
  }
  const openTypeReview = (focusId?: string) => void perform(async () => { await ensureProducts(); setTypeReview({focusId}); setDetailId(null) })

  useEffect(() => { if (params.get('compose')) setComposing(true) }, [params])
  useEffect(() => {
    setDetailId(null); setEvidence(false); setAi(false); setExporting(false); setTypeReview(null); setActionEdit(null)
    setChartScope('current'); setQuery(''); setSignal('all'); setCategory('all')
  }, [current?.id])
  useEffect(() => {
    let active = true
    setRecords({})
    if (report) salesApi.records(projectId, current!.id).then(r => { if (active) setRecords(r.items) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [current?.id, report?.context.run_id, projectId])
  useEffect(() => { setRecordRows(null); setInventorySet(false); setInventory({ available: 0, incoming: 0, reserve: 0, pack_size: 1, arrival_date: '', confirmed: false }); setAnswer(''); setQuestion(''); setAnswerError(''); setAnswerSource(''); setAnsweredQuestion(''); ++aiGeneration.current; setAiBusy(false) }, [detailId, current?.id])

  useEffect(() => {
    if (!detailId || !current) return
    let active = true
    const runId = current.id
    salesApi.product(projectId, runId, detailId).then(item => {
      if (active) setDetailProduct({runId, item})
    }).catch(e => { if (active) { setError(e.message); setDetailId(null) } })
    return () => { active = false }
  }, [projectId, current?.id, detailId])

  async function askSales() {
    if (!current || !question.trim()) return
    const generation = ++aiGeneration.current, asked = question.trim()
    setAiBusy(true); setAnswer(''); setAnswerError(''); setAnswerSource(''); setAnsweredQuestion(asked)
    try {
      const response = await salesApi.ask(projectId, current.id, asked, detailId)
      if (generation !== aiGeneration.current) return
      setAnswer(response.answer); setAnswerSource(response.response_source ?? 'computed')
    } catch {
      if (generation === aiGeneration.current) setAnswerError('暂时没能读取回答，请重试。')
    } finally {
      if (generation === aiGeneration.current) setAiBusy(false)
    }
  }
  useEffect(() => () => { ++aiGeneration.current }, [])

  const perform = async (task: () => Promise<void>) => { setBusy(true); setError(''); try { await task() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  const exportFile = (url: string) => { const anchor = document.createElement('a'); anchor.href = url; anchor.click() }
  const filteringAttention = params.get('attention') === '1'
  const filtered = report?.products.filter(p => (!filteringAttention || p.flags.length) && (category === 'all' || p.category === category) && (signal === 'all' || p.flags.includes(signal)) && `${p.name} ${p.id}`.toLowerCase().includes(query.toLowerCase())) ?? []
  const columns = [
    { title: '商品', dataIndex: 'name', key: 'name', width:220, render: (_: string, p: SalesProduct) => <Button type="link" className="sales-item-name" onClick={() => setDetailId(p.id)}>{p.name}</Button> },
    { title: unit ? `销量（${unit}）` : '销量', dataIndex: 'quantity', width:95, sorter: (a: SalesProduct, b: SalesProduct) => a.quantity - b.quantity, render: number },
    ...(report?.products.some(p => p.amount !== null) ? [{ title: `销售额 (${report.summary.currency ?? ''})`, dataIndex: 'amount', width:130, render: number, sorter: (a: SalesProduct, b: SalesProduct) => (a.amount ?? -1) - (b.amount ?? -1) }] : []),
  ]
  const productColumns = [
    { ...columns[0], width: 160 },
    { ...columns[1], width: 70, align: 'right' as const },
    ...(report?.products.some(p => p.amount !== null) ? [{ ...columns[2], width: 115, align: 'right' as const }] : []),
    { title: '销售情况', key: 'situation', width: 210, render: (_: unknown, p: SalesProduct) => <ProductSignals product={p} /> },
  ]
  if (loading) return <LoadingState />

  return <div className="sales-workspace">
    <div className={`sales-toolbar ${productsMode ? '' : 'overview-toolbar'}`}>
      <h2>{productsMode ? '商品分析' : report ? `${report.month.slice(0, 4)} 年 ${Number(report.month.slice(5))} 月` : '销售总览'}</h2>
      <div>
        <ReportPicker runs={runs} current={current} disabled={!!switching} onChoose={id => void chooseReport(id)} />
        <Button type={productsMode ? 'default' : 'primary'} icon={<PlusOutlined />} onClick={() => setImporting(true)}>上传销售表</Button>
        {report && <Button type="text" icon={<DownloadOutlined />} onClick={() => setExporting(true)}>导出</Button>}
        <Dropdown trigger={['click']} menu={{ items: [
          ...(runs.length ? [{ key: 'history', label: '历史报告' }] : []),
          ...(versions.length ? [{ key: 'generate', label: '生成月报' }] : []),
          ...(report ? [{ key: 'evidence', label: '月报怎么算的' }] : []),
          ...(report ? [{ key: 'types', label: '确认记录类型' }] : []),
          { key: 'data', label: '数据记录' },
          { key: 'analysis', label: '补充分析' },
        ], onClick: ({ key }) => {
          if (key === 'history') setHistory(true)
          else if (key === 'generate') setComposing(true)
          else if (key === 'evidence') setEvidence(true)
          else if (key === 'types') openTypeReview()
          else navigate(`${root}/${key === 'data' ? 'data' : 'quality'}`)
        } }}><Button type="text" icon={<MoreOutlined />} aria-label="更多操作">更多</Button></Dropdown>
      </div>
    </div>
    {error && <Alert type="error" showIcon closable onClose={() => setError('')} title={error} />}
    {selection.error && <Alert type="error" showIcon title={selection.error} action={<Button onClick={() => void selection.retry()}>重试</Button>} />}
    <HistoricalReportNotice runs={runs} current={current} disabled={!!switching} onChoose={id => void chooseReport(id)} />
    {selection.taskNotice && <Alert type="warning" title={selection.taskNotice} />}
    {task && <div className="sales-processing"><Spin /><strong>{task.message || '正在生成报告，完成前仍可查看当前报告。'}</strong><Button icon={<StopOutlined />} onClick={() => void perform(async () => { await salesApi.cancel(projectId, task.id) })}>取消处理</Button></div>}
    {switching && <div className="report-switching" role="status"><Spin /><span>正在加载 {switching}</span></div>}
    {!current && !task && !selection.error && <EmptyState title="先看看这个月卖得怎么样" description="上传销售表，确认内容后查看销售分析。" action={<Button type="primary" icon={<PlusOutlined />} onClick={() => setImporting(true)}>上传销售表</Button>} />}
    {report && !switching && !productsMode && <AutomaticAnalysisStatus automatic={selection.automatic} />}
    {report && !switching && !productsMode && <SalesOverview key={current!.id}
      report={report} chartScope={chartScope} onChartScope={setChartScope} records={records}
      onProduct={setDetailId} onAllProducts={() => navigate(`${root}/products?run=${current!.id}`)} onAsk={() => setAi(true)}
      onActionOpen={action => {
        if (action.target?.kind === 'pairing') navigate(`${root}/pairings?${new URLSearchParams({run: current!.id, pairingSource: action.target.version_id!, pairingRun: action.target.run_id!, pairingItems: JSON.stringify(action.related_items ?? [])})}`)
        else if (action.target?.kind === 'customer') setCustomerAction({runId: current!.id, action})
        else setDetailId(action.item_id)
      }}
      onActionStatus={(action, status) => void perform(async () => {
        const old = records[`action:${action.id}`]
        const saved = await salesApi.action(projectId, current!.id, action.id, status, old?.value.note ?? '', old?.revision ?? 0)
        setRecords(rows => ({ ...rows, [`action:${action.id}`]: saved }))
      })}
      onActionNote={action => { setActionEdit(action.id); setNote(records[`action:${action.id}`]?.value.note ?? '') }}
    />}
    {report && !switching && productsMode && <section className="sales-band sales-product-list">
      <div className="sales-filter">
        <Segmented value={filteringAttention ? 'attention' : 'all'} options={[{ value: 'all', label: `全部商品 ${report.products.length}` }, { value: 'attention', label: `待关注 ${report.attention_ids.length}` }]} onChange={v => navigate(`${root}/products?run=${current?.id ?? ''}${v === 'attention' ? '&attention=1' : ''}`)} />
        <Input.Search aria-label="搜索商品" placeholder="商品名称或编号" value={query} onChange={e => setQuery(e.target.value)} style={{ maxWidth: 240 }} />
        <Select aria-label="筛选销售变化" value={signal} onChange={setSignal} options={[{ value: 'all', label: '所有变化' }, ...Object.entries(flagNames).map(([value, label]) => ({ value, label }))]} style={{ width: 140 }} />
        <Button onClick={() => openTypeReview()}>确认记录类型</Button>
        {report.products.some(p => p.category) && <Select aria-label="商品分类" value={category} onChange={setCategory} style={{ width: 150 }} options={[{ value: 'all', label: '全部分类' }, ...Array.from(new Set(report.products.map(p => p.category).filter((c): c is string => !!c))).sort().map(c => ({ value: c, label: c }))]} />}
      </div>
      <p className="sales-product-list-hint">点击商品名称查看趋势和原因。{unit && `销量单位：${unit}。`}{report.products.some(p => p.change !== null) && (report.products.some(p => p.has_daily ?? p.daily.length > 0) ? '变化幅度比较月底最后 7 天与此前 7 天。' : '变化幅度与上月比较。')}</p>
      <Table rowKey="id" size="small" dataSource={filtered} columns={productColumns} pagination={{ pageSize: 20, showSizeChanger: false, showTotal: total => `共 ${total} 件商品` }} scroll={{ x: 480 }} />
    </section>}
    {(importing || composing) && <SalesImportWizard projectId={projectId} versions={versions} existing={composing} initialSources={report?.parameters.sources.map(s => s.version_id)}
      onClose={() => { setImporting(false); setComposing(false); void reload() }}
      onDone={run => { setImporting(false); setComposing(false); setDetailId(null); setChartScope('current'); void reload(run.id) }} />}
    {typeReview && report && <SalesTypeReview key={`types:${current!.id}`} projectId={projectId} report={related!} focusId={typeReview.focusId}
      onClose={() => setTypeReview(null)} onDone={run => { setTypeReview(null); setChartScope('current'); void reload(run.id) }} />}
    <ReportHistory open={history} onClose={() => setHistory(false)} runs={runs} current={current} versions={versions} disabled={!!switching} onChoose={id => void chooseReport(id)} />
    <Drawer title={product?.name ?? report?.products.find(p => p.id === detailId)?.name ?? '商品详情'} open={!!detailId} width={690} onClose={() => setDetailId(null)}>
      {detailId && !product && <Spin />}
      {product && report && <div className="product-detail" key={`${current!.id}:${product.id}`}>
        <header className="product-detail-summary">
          <span className="product-detail-period">{report.month} · 商品销售</span>
          <h2>{product.focus?.label === '大批量订单带动' ? '大批量订单带动' : product.flags.includes('growth') ? '销量明显上升' : product.flags.includes('decline') ? '销量有所下降' : product.anomalies.length ? `发现 ${product.anomalies.length} 天销量异常` : '本月销售概况'}</h2>
          <ChangeExplanation product={product} />
          <AnomalyExplanation product={product} />
        </header>

        {product.focus && <section className="product-detail-forecast"><h3>为什么列为重点商品</h3><p><strong>{product.focus.label}</strong></p><p>{product.focus.reason}</p>{product.focus.note && <p className="product-detail-muted">{product.focus.note}</p>}</section>}

        <div className="product-type-confirmation"><span>记录类型：{itemKindOptions.find(v => v.value === product.item_type?.kind)?.label ?? '待确认'}</span><Button type="link" size="small" onClick={() => openTypeReview(product.id)}>确认或调整类型</Button></div>

        <div className="product-detail-metrics">
          <div><span>本月销量</span><strong>{number(product.quantity)}</strong><small>{unit}</small></div>
          <div><span>本月销售额</span><strong>{number(product.amount)}</strong><small>{report.summary.currency || report.summary.amount_label}</small></div>
        </div>

        {product.daily.length > 0 && <section className="product-detail-trend">
          <h3>每天卖得怎么样</h3>
          <SalesChart points={product.daily.map(p => ({ date: p.date, value: p.quantity }))} label={`${product.name} 每日销量${unit ? `（${unit}）` : ''}`} />
        </section>}

        <section className="product-detail-forecast">
          <h3>{['fee_service', 'accounting'].includes(product.item_type?.kind ?? '') ? '七天记录数量参考' : '七天销量预测'}</h3>
          {product.forecast ? <>
            <p className="product-detail-prediction"><strong>约 {number(product.forecast.quantity)}</strong><span>{unit}</span></p>
            <p className="product-detail-muted">{product.forecast.start} 至 {product.forecast.end} · {['fee_service', 'accounting'].includes(product.item_type?.kind ?? '') ? '用于了解记录变化，不适用实物备货' : '进货时还需结合库存'}</p>
            {product.forecast.range && <p>历史误差参考范围：{number(product.forecast.range.lower)} 至 {number(product.forecast.range.upper)} {unit}，不保证未来覆盖。</p>}
            <details className="product-detail-method">
              <summary>预测说明</summary>
              <p>参考方法：{methods[product.forecast.method]}。历史检验中，七天总销量平均相差约 {number(product.forecast.validation_mae)} {unit}。</p>
              {product.forecast.test_mae != null && <p>最近 {product.forecast.test_origins} 次{report.forecast.test_used_for_selection === false ? '独立检验' : '历史检查'}中，七天总量平均相差约 {number(product.forecast.test_mae)} {unit}。请结合近期误差使用预测。</p>}
              <p>{product.forecast.notice}</p>
            </details>
          </> : <>
            <p className="product-detail-muted">{product.forecast_unavailable?.message ?? '这份历史月报未记录具体的预测不可用原因。'}</p>
            <p className="product-detail-next">{product.forecast_unavailable?.next_step ?? '可在销售总览的“更多”中选择“生成月报”，使用原销售表重新分析后查看。'}</p>
          </>}
        </section>

        <div className="product-detail-tools">
          <ProductEvidence product={product} currency={report.summary.currency} />
          <details className="product-detail-disclosure">
            <summary><span>查看销售变化</span><small>{product.anomalies.length ? `销量异常：${product.anomalies.length} 天` : '变化说明'}</small></summary>
            <div className="product-detail-content">
              <ChangeExplanation product={product} />
              <AnomalyExplanation product={product} detailed />
              {!!product.anomaly_events?.length && <ul>{product.anomaly_events.map(event => <li key={event.start}>{event.start} 至 {event.end}：实际 {number(event.actual)} {unit}，历史参考合计 {number(event.reference)} {unit}。请核对下列日期。</li>)}</ul>}
              {product.anomalies.length > 0 && <>
                <p className="product-detail-muted">{product.anomaly_check?.reference_label?.includes('相同星期') ? '参考销量取此前最多12个相同星期几的中位数，至少需要6个；包含确认没有销售的日子。它用于识别异常，不代表近期每天都卖这么多。' : '参考销量用于识别变化，具体方法见月报计算说明。'}</p>
                <p className="product-detail-muted">点日期查看当天的销售记录。{unit && `销量单位：${unit}。`}</p>
                <Table rowKey="date" size="small" pagination={false} dataSource={product.anomalies} columns={[
                  { title: '日期', dataIndex: 'date', render: (day: string) => <Button type="link" loading={busy} onClick={() => void perform(async () => setRecordRows(await salesApi.itemRecords(projectId, current!.id, product.id, day)))}>{day}</Button> },
                  { title: '实际销量', dataIndex: 'actual', render: number },
                  { title: product.anomaly_check?.reference_label?.includes('相同星期') ? '历史同星期中位数' : '历史参考销量', dataIndex: 'reference', render: number },
                ]} />
              </>}
              {recordRows && <div className="sales-source-records">
                <h3>{recordRows.date} 的原始记录</h3>
                <p>共 {recordRows.count} 条，显示前 {recordRows.shown} 条（含排除记录）。</p>
                <Table rowKey={r => `${r.version_id}:${r.source_row_id}`} size="small" pagination={false} dataSource={recordRows.items} scroll={{ x: 480 }} columns={[
                  { title: '原始行号', dataIndex: 'source_row_id' },
                  { title: '数量', dataIndex: 'quantity' },
                  { title: '单价', dataIndex: 'unit_price' },
                  { title: '处理', dataIndex: 'reason', render: (v: string) => v === 'included' ? '纳入统计' : report.quality.reasons.find(r => r.code === v)?.label ?? v },
                ]} />
              </div>}
            </div>
          </details>

          {product.forecast && !['fee_service', 'accounting'].includes(product.item_type?.kind ?? '') && <details className="product-detail-disclosure">
            <summary><span>算一下备货量</span><small>填写库存后计算</small></summary>
            <div className="product-detail-content">
              <div className="sales-inventory"><label>预测起点的可售库存<InputNumber aria-label="可售库存" min={0} value={inventorySet ? inventory.available : null} onChange={v => { setInventorySet(v !== null); setInventory(r => ({ ...r, available: v ?? 0, confirmed: false })) }} /></label><label>七天内已下单、确定到货数量<InputNumber aria-label="确定到货数量" min={0} value={inventory.incoming} onChange={v => setInventory(r => ({ ...r, incoming: v ?? 0, confirmed: false }))} /></label>{inventory.incoming > 0 && <label>预计到货日<input aria-label="预计到货日" type="date" value={inventory.arrival_date} onChange={e => setInventory(r => ({ ...r, arrival_date: e.target.value, confirmed: false }))} /></label>}<label>想额外保留的备用量<InputNumber aria-label="备用量" min={0} value={inventory.reserve} onChange={v => setInventory(r => ({ ...r, reserve: v ?? 0, confirmed: false }))} /></label><label>每个包装含多少销售单位<InputNumber aria-label="包装单位" min={1} value={inventory.pack_size} onChange={v => setInventory(r => ({ ...r, pack_size: v ?? 1, confirmed: false }))} /></label></div>
          <Checkbox checked={inventory.confirmed} onChange={e => setInventory(r => ({ ...r, confirmed: e.target.checked }))}>我已确认这是可备货的实物商品，并核对 {product.forecast.start} 的可售库存、未到货数量（没有则为零）与备用量</Checkbox><Button className="sales-inventory-button" disabled={!inventory.confirmed || !inventorySet} loading={busy} onClick={() => void perform(async () => { const saved = await salesApi.inventory(projectId, current!.id, { ...inventory, physical_confirmed: inventory.confirmed, arrival_date: inventory.arrival_date || null, item_id: product.id, snapshot_date: product.forecast!.start }); setRecords(r => ({ ...r, [`inventory:${product.id}`]: saved })) })}>计算数量参考</Button>
          {records[`inventory:${product.id}`] && <Alert type="info" title={`七天补货参考：${number(records[`inventory:${product.id}`].value.suggested_quantity)} ${unit}`} description={records[`inventory:${product.id}`].value.notice} />}
            </div>
          </details>}

          <details className="product-detail-disclosure">
            <summary><span>记下核对结果</span><small>原因和备注</small></summary>
            <div className="product-detail-content">
              <ProductNote projectId={projectId} runId={current!.id} itemId={product.id} dates={product.anomalies.map(a => a.date)} />
            </div>
          </details>
        </div>
        <footer className="product-detail-footer">
          <Button type="text" icon={<MessageOutlined />} onClick={() => setAi(true)}>问问这件商品</Button>
          <Button type="text" icon={<FileSearchOutlined />} onClick={() => setEvidence(true)}>月报怎么算的</Button>
        </footer>
      </div>}
    </Drawer>
    <Drawer title="月报怎么算的" open={evidence} width={700} onClose={() => setEvidence(false)}>
      {report && <SalesReportExplanation report={report} onDownload={file => void exportFile(salesApi.download(projectId, current!.id, file))} />}
    </Drawer>
    <Drawer title="客户名单与回访依据" open={!!customerAction && customerAction.runId === current?.id} width={520} onClose={() => setCustomerAction(null)}>
      {customerAction && <div className="product-detail">
        <h3>{customerAction.action.title}</h3>
        <p>{customerAction.action.text}</p>
        {customerAction.action.details?.map(row => <p key={row.label}><strong>{row.label}：</strong>{row.value}</p>)}
        <Button icon={<DownloadOutlined />} onClick={() => exportFile(`/api/projects/${encodeURIComponent(projectId)}/sales/runs/${customerAction.runId}/action-customers?${new URLSearchParams({action_id: customerAction.action.id})}`)}>下载客户名单与依据</Button>
        <p className="product-detail-muted">按客户编号查找对应客户，先小范围尝试，再比较复购情况。</p>
      </div>}
    </Drawer>
    <Drawer title="导出月报" open={exporting} width={420} onClose={() => setExporting(false)}><Checkbox checked={allExport} onChange={e => setAllExport(e.target.checked)}>附上全部待关注商品</Checkbox><div className="sales-export-actions"><Button type="primary" icon={<DownloadOutlined />} onClick={() => current && exportFile(salesApi.report(projectId, current.id, allExport))}>下载月报</Button><Button icon={<DownloadOutlined />} onClick={() => current && exportFile(salesApi.download(projectId, current.id, 'sales_products.csv'))}>下载全部商品表</Button></div><p className="sales-caveat">月报可在浏览器中打印保存为 PDF。</p></Drawer>
    <Drawer title="销售助手" open={ai} width={470} onClose={() => { setAi(false); ++aiGeneration.current; setAiBusy(false) }}>
      <p>{product ? `正在查看：${product.name}` : '根据当前月报回答'}</p>
      <SalesAssistantQuestions product={product} disabled={aiBusy || !report} onChoose={setQuestion} />
      <Input.TextArea aria-label="向销售助手提问" disabled={aiBusy} value={question} onChange={e => setQuestion(e.target.value)} maxLength={500} autoSize={{ minRows: 3, maxRows: 6 }} placeholder={product ? '例如：这件商品本月卖得怎么样？' : '例如：本月销量怎么样？哪些商品卖得好？'} />
      <Button className="sales-ask" type="primary" icon={<SendOutlined />} loading={aiBusy} disabled={!question.trim() || !report} onClick={() => void askSales()}>提问</Button>
      {aiBusy && <p role="status">正在整理与你问题相关的销售结果…</p>}
      {answerError && <Alert type="error" title={answerError} action={<Button size="small" onClick={() => void askSales()}>重试</Button>} />}
      {answer && <div className="sales-ai-answer" aria-live="polite">
        <strong>{answeredQuestion}</strong>
        <p style={{ whiteSpace: 'pre-line' }}>{answer}</p>
        {answerSource === 'model_unavailable' && <small>语言整理服务暂不可用，以上直接展示已计算结果。</small>}
        {answerSource === 'model_busy' && <small>语言整理服务正在忙，以上直接展示已计算结果。</small>}
        <Button type="link" onClick={() => setEvidence(true)}>查看月报数据说明</Button>
      </div>}
    </Drawer>
    <Drawer title="记录处理情况" width={430} open={!!actionEdit} onClose={() => setActionEdit(null)}><Input.TextArea aria-label="处理备注" value={note} onChange={e => setNote(e.target.value)} maxLength={500} rows={4} placeholder="例如：当天缺货，已核对" /><Button className="sales-ask" type="primary" loading={busy} onClick={() => void perform(async () => { if (!actionEdit || !current) return; const old = records[`action:${actionEdit}`]; const saved = await salesApi.action(projectId, current.id, actionEdit, old?.value.status ?? 'pending', note, old?.revision ?? 0); setRecords(r => ({ ...r, [`action:${actionEdit}`]: saved })); setActionEdit(null); void message.success('已保存处理备注') })}>保存备注</Button></Drawer>
  </div>
}
