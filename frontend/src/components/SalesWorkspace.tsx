import { useEffect, useState } from 'react'
import { Alert, App, Button, Checkbox, Drawer, Input, InputNumber, Select, Segmented, Spin, Table, Tag } from 'antd'
import { DownloadOutlined, FileSearchOutlined, MessageOutlined, PlusOutlined, RightOutlined, SendOutlined, StopOutlined } from '@ant-design/icons'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { dataApi } from '../data'
import type { Version } from '../data'
import { salesApi } from '../retail'
import type { SalesParameters, SalesProduct, SalesRun, SavedRecord, SourceInfo, SourceRecords } from '../retail'
import { finished } from '../quality'
import { ImportEditor } from './ImportEditor'
import { SalesChart } from './SalesChart'
import { ProductNote } from './ProductNote'
import { EmptyState, LoadingState } from './States'

const number = (v: number | null | undefined) => v == null ? '—' : v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
const methods: Record<string, string> = { gradient_boosting: '历史销售模型', last_week: '上一周销量参考', four_week_mean: '过去四周平均参考' }
const flagNames: Record<string, string> = { growth: '卖得更多', decline: '卖得更少', anomaly: '变化需核对' }

export default function SalesWorkspace({ projectId, productsMode = false }: { projectId: string; productsMode?: boolean }) {
  const [versions, setVersions] = useState<Version[]>([]), [runs, setRuns] = useState<SalesRun[]>([])
  const [current, setCurrent] = useState<SalesRun | null>(null), [loading, setLoading] = useState(true)
  const [error, setError] = useState(''), [importing, setImporting] = useState(false), [composing, setComposing] = useState(false)
  const [sources, setSources] = useState<string[]>([]), [sourceInfo, setSourceInfo] = useState<SourceInfo[]>([])
  const [month, setMonth] = useState(''), [start, setStart] = useState(''), [end, setEnd] = useState('')
  const [complete, setComplete] = useState(false), [merge, setMerge] = useState('append'), [duplicates, setDuplicates] = useState('keep'), [closed, setClosed] = useState('')
  const [checking, setChecking] = useState<SalesRun | null>(null), [checkedParams, setCheckedParams] = useState<SalesParameters | null>(null)
  const [busy, setBusy] = useState(false), [detailId, setDetailId] = useState<string | null>(null), [evidence, setEvidence] = useState(false), [exporting, setExporting] = useState(false), [allExport, setAllExport] = useState(false)
  const [records, setRecords] = useState<Record<string, SavedRecord>>({}), [actionEdit, setActionEdit] = useState<string | null>(null), [note, setNote] = useState('')
  const [query, setQuery] = useState(''), [signal, setSignal] = useState('all'), [ai, setAi] = useState(false), [question, setQuestion] = useState(''), [answer, setAnswer] = useState(''), [aiBusy, setAiBusy] = useState(false)
  const [chartScope, setChartScope] = useState('current')
  const [recordRows, setRecordRows] = useState<SourceRecords | null>(null)
  const [category, setCategory] = useState('all')
  const [inventory, setInventory] = useState({ available: 0, incoming: 0, reserve: 0, pack_size: 1, arrival_date: '', confirmed: false })
  const [inventorySet, setInventorySet] = useState(false)
  const [params] = useSearchParams(), navigate = useNavigate(), { message } = App.useApp()
  const report = current?.result, product = report?.products.find(p => p.id === detailId)
  const root = `/projects/${projectId}`

  async function reload(preferred?: string) {
    const [v, r] = await Promise.all([dataApi.versions(projectId), salesApi.list(projectId)])
    setVersions(v.items); setRuns(r.items.filter(row => !row.parameters?.sales.check_only))
    if (preferred) setCurrent(await salesApi.run(projectId, preferred))
    else if (!current && r.items.length) {
      for (const row of r.items) {
        const full = await salesApi.run(projectId, row.id)
        if (!full.parameters?.sales.check_only) { setCurrent(full); break }
      }
    }
    if (!sources.length && v.items.length) setSources([v.items[0].id])
  }
  useEffect(() => {
    let active = true
    reload(params.get('run') ?? undefined).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    if (params.get('compose')) setComposing(true)
    return () => { active = false }
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!composing || !sources.length) return
    let active = true
    setSourceInfo([]); setChecking(null); setCheckedParams(null)
    Promise.all(sources.map(id => salesApi.source(projectId, id))).then(rows => {
      if (!active) return
      setSourceInfo(rows)
      const starts = rows.map(r => r.start).filter((r): r is string => !!r).sort()
      const ends = rows.map(r => r.end).filter((r): r is string => !!r).sort()
      setStart(starts[0] ?? ''); setEnd(ends.at(-1) ?? '')
      setMonth(rows.at(-1)?.suggested_month ?? '')
      setComplete(false)
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [sources, composing, projectId])
  useEffect(() => {
    if (!current || finished.has(current.status)) return
    const timer = window.setInterval(() => salesApi.run(projectId, current.id).then(r => {
      setCurrent(r); if (finished.has(r.status)) void reload(r.id)
    }).catch(e => setError(e.message)), 1800)
    return () => clearInterval(timer)
  }, [current?.id, current?.status, projectId])
  useEffect(() => {
    if (!checking || finished.has(checking.status)) return
    const timer = window.setInterval(() => salesApi.run(projectId, checking.id).then(setChecking).catch(e => setError(e.message)), 1800)
    return () => clearInterval(timer)
  }, [checking?.id, checking?.status, projectId])
  useEffect(() => { if (report) salesApi.records(projectId, current!.id).then(r => setRecords(r.items)).catch(e => setError(e.message)); else setRecords({}) }, [current?.id, report?.context.run_id, projectId])
  useEffect(() => { setRecordRows(null); setInventorySet(false); setInventory({ available: 0, incoming: 0, reserve: 0, pack_size: 1, arrival_date: '', confirmed: false }); setAnswer('') }, [detailId, current?.id])

  const perform = async (task: () => Promise<void>) => { setBusy(true); setError(''); try { await task() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  const showAll = () => navigate(`${root}/products?attention=1&run=${current?.id ?? ''}`)
  const exportFile = (url: string) => { const anchor = document.createElement('a'); anchor.href = url; anchor.click() }
  const chartAmount = report?.summary.amount !== null && report?.chart.some(p => p.amount !== null)
  const chart = chartScope === 'previous' && report?.previous_chart?.length ? report.previous_chart : report?.chart ?? []
  const filteringAttention = params.get('attention') === '1'
  const filtered = report?.products.filter(p => (!filteringAttention || p.flags.length) && (category === 'all' || p.category === category) && (signal === 'all' || p.flags.includes(signal)) && `${p.name} ${p.id}`.toLowerCase().includes(query.toLowerCase())) ?? []
  const highlights = report?.highlights.map(id => report.products.find(p => p.id === id)!).filter(Boolean) ?? []
  const columns = [
    { title: '商品', dataIndex: 'name', key: 'name', width:220, render: (_: string, p: SalesProduct) => <Button type="link" className="sales-item-name" onClick={() => setDetailId(p.id)}>{p.name}</Button> },
    { title: '销量', dataIndex: 'quantity', width:95, sorter: (a: SalesProduct, b: SalesProduct) => a.quantity - b.quantity, render: number },
    ...(report?.products.some(p => p.amount !== null) ? [{ title: `销售额 (${report.summary.currency ?? ''})`, dataIndex: 'amount', width:130, render: number, sorter: (a: SalesProduct, b: SalesProduct) => (a.amount ?? -1) - (b.amount ?? -1) }] : []),
    { title: '销售变化', dataIndex: 'change', width:100, render: (v: number | null) => v === null ? '—' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(0)}%` },
    { title: '值得留意', key: 'flags', render: (_: unknown, p: SalesProduct) => <>{p.flags.map(f => <Tag key={f} color={f === 'growth' ? 'cyan' : 'orange'}>{flagNames[f]}</Tag>)}<p className="sales-row-reason">{p.reason}</p></> },
  ]
  const check = () => void perform(async () => {
    const data: SalesParameters = { sources: sourceInfo.map(s => ({ version_id: s.version_id, mapping_revision: s.mapping_revision })), month,
      complete_coverage: complete, coverage_start: complete ? start || null : null, coverage_end: complete ? end || null : null,
      merge_mode: merge, duplicates, closed_dates: closed.split(',').map(d => d.trim()).filter(Boolean) }
    const run = await salesApi.create(projectId, { ...data, check_only: true }); setChecking(run); setCheckedParams(data)
  })
  if (loading) return <LoadingState />

  return <div className="sales-workspace">
    <div className="sales-toolbar"><h2>{productsMode ? '商品明细' : '本月月报'}</h2><div>
      {runs.length > 0 && <Select aria-label="选择历史月报" value={current?.id} placeholder="历史月报" style={{ width: 205 }} options={runs.map(r => ({ value: r.id, label: `${r.parameters?.sales.month ?? ''} · ${r.created_at.slice(0, 10)}` }))} onChange={id => void perform(async () => setCurrent(await salesApi.run(projectId, id)))} />}
      <Button icon={<PlusOutlined />} onClick={() => setImporting(true)}>上传新数据</Button>
      {versions.length > 0 && <Button onClick={() => { setChecking(null); setComposing(true) }}>生成月报</Button>}
      {report && <Button icon={<DownloadOutlined />} onClick={() => setExporting(true)}>导出月报</Button>}
    </div></div>
    {error && <Alert type="error" showIcon closable onClose={() => setError('')} title={error} />}
    {!current && <EmptyState title="先看看这个月卖得怎么样" description="上传营业表，确认字段后生成销售月报。" action={<Button type="primary" icon={<PlusOutlined />} onClick={() => setImporting(true)}>上传营业表</Button>} />}
    {current && !finished.has(current.status) && <div className="sales-processing"><Spin /><strong>{current.message}</strong><Button icon={<StopOutlined />} onClick={() => void perform(async () => { await salesApi.cancel(projectId, current.id) })}>取消处理</Button></div>}
    {current && finished.has(current.status) && !report && <Alert type="warning" title={current.message} action={<Button onClick={() => setComposing(true)}>调整后重试</Button>} />}
    {report && !productsMode && <>
      <section className="sales-band"><div className="sales-section-heading"><h3>{report.month} · 本月卖得怎么样</h3><Button type="text" icon={<FileSearchOutlined />} onClick={() => setEvidence(true)}>查看依据</Button></div>
        <div className="sales-metrics">
          <div><span>{report.summary.amount !== null ? report.summary.amount_label : '本月销量'}</span><strong>{number(report.summary.amount ?? report.summary.quantity)}<small>{report.summary.amount !== null ? report.summary.currency : report.summary.unit}</small></strong></div>
          <div><span>{report.summary.orders ? '订单数' : '有销售记录的商品'}</span><strong>{number(report.summary.orders ?? report.summary.products)}</strong></div>
          <div><span>{report.summary.average_order !== null ? '平均每单金额' : '值得留意的商品'}</span><strong>{number(report.summary.average_order ?? report.summary.attention_total)}</strong></div>
        </div>
        <p className="sales-summary">本月记录了 {report.summary.products} 种商品的销售，其中 {report.summary.attention_total} 种值得留意。
          {report.summary.previous ? ` 上月销量为 ${number(report.summary.previous.quantity)} ${report.summary.unit}，本月为 ${number(report.summary.quantity)} ${report.summary.unit}。` : ' 没有确认完整的上月记录，暂不做月度对比。'}</p>
        {!report.summary.complete_month && <p className="sales-caveat">本月记录完整性尚未确认，空缺日期不按零销量计算。</p>}
        {!!report.previous_chart?.length && <Segmented aria-label="比较月份" value={chartScope} onChange={setChartScope} options={[{ value: 'current', label: '本月' }, { value: 'previous', label: '上月' }]} />}
        {chart.length ? <SalesChart points={chart.map(p => ({ date: p.date, value: chartAmount ? p.amount : p.quantity }))} label={`${chart[0].date.slice(0,7)} 每日${chartAmount ? '销售额' : '销量'}`} /> : <p className="sales-caveat">这份表是月汇总，没有每日销售曲线。</p>}
      </section>
      <section className="sales-band"><div className="sales-section-heading"><h3>这几件商品值得留意</h3><Button type="link" icon={<RightOutlined />} onClick={showAll}>查看全部 {report.summary.attention_total} 件</Button></div>
        {highlights.length ? <div className="sales-scroll"><Table size="small" rowKey="id" dataSource={highlights} columns={columns.filter(c => c.key !== 'flags')} pagination={false} scroll={{ x: 650 }} /><div className="sales-focus-reasons">{highlights.map(p => <p key={p.id}><strong>{p.name}</strong><span>{p.reason}</span></p>)}</div></div> : <p className="sales-caveat">当前没有足够依据标出特别关注的商品，可以查看全部销售明细。</p>}
      </section>
      <section className="sales-band"><div className="sales-section-heading"><h3>下个月先做这些</h3><span>{report.actions.length} 件事</span></div>
        {report.actions.map((a, i) => <article className="sales-action" key={a.id}><span className="sales-action-index">{i + 1}</span><div><h4>{a.title}</h4><p>{a.text}</p><small>{a.reason} · {a.review}</small><div className="sales-action-tools"><Button type="link" onClick={() => setDetailId(a.item_id)}>查看商品和依据</Button><Select aria-label={`处理状态 ${a.title}`} value={records[`action:${a.id}`]?.value.status ?? 'pending'} style={{ width: 105 }} options={[{ value: 'pending', label: '待处理' }, { value: 'done', label: '已处理' }, { value: 'declined', label: '暂不采用' }]} onChange={status => void perform(async () => { const old = records[`action:${a.id}`]; const saved = await salesApi.action(projectId, current!.id, a.id, status, old?.value.note ?? '', old?.revision ?? 0); setRecords(r => ({ ...r, [`action:${a.id}`]: saved })) })} /><Button size="small" onClick={() => { setActionEdit(a.id); setNote(records[`action:${a.id}`]?.value.note ?? '') }}>备注</Button></div>{records[`action:${a.id}`]?.value.note && <p className="sales-note">{records[`action:${a.id}`].value.note}</p>}</div></article>)}
        {!report.actions.length && <p className="sales-caveat">暂时没有足够依据提出特别行动，继续记录销售情况。</p>}
      </section>
      <div className="sales-bottom"><Button icon={<MessageOutlined />} onClick={() => setAi(true)}>问问销售助手</Button><Link to={`${root}/quality`}>更多分析</Link></div>
    </>}
    {report && productsMode && <section className="sales-band">
      <div className="sales-filter">
        <Segmented value={filteringAttention ? 'attention' : 'all'} options={[{ value: 'all', label: `全部商品 ${report.products.length}` }, { value: 'attention', label: `待关注 ${report.attention_ids.length}` }]} onChange={v => navigate(`${root}/products?run=${current?.id ?? ''}${v === 'attention' ? '&attention=1' : ''}`)} />
        <Input.Search aria-label="搜索商品" placeholder="商品名称或编号" value={query} onChange={e => setQuery(e.target.value)} style={{ maxWidth: 240 }} />
        <Select aria-label="筛选销售变化" value={signal} onChange={setSignal} options={[{ value: 'all', label: '所有变化' }, ...Object.entries(flagNames).map(([value, label]) => ({ value, label }))]} style={{ width: 140 }} />
        {report.products.some(p => p.category) && <Select aria-label="商品分类" value={category} onChange={setCategory} style={{ width: 150 }} options={[{ value: 'all', label: '全部分类' }, ...Array.from(new Set(report.products.map(p => p.category).filter((c): c is string => !!c))).sort().map(c => ({ value: c, label: c }))]} />}
      </div>
      <Table rowKey="id" size="small" dataSource={filtered} columns={columns} pagination={{ pageSize: 20, showSizeChanger: true, showTotal: total => `共 ${total} 件商品` }} scroll={{ x: 720 }} />
    </section>}
    {importing && <ImportEditor projectId={projectId} initial={null} onClose={() => { setImporting(false); void reload() }} onSaved={v => { setImporting(false); setSources([v.id]); void reload(); setComposing(true) }} />}
    <Drawer title="确认数据，生成月报" open={composing} width={720} onClose={() => setComposing(false)} footer={<div className="sales-drawer-footer"><Button disabled={busy || !sourceInfo.length || !month || (!!checking && !finished.has(checking.status))} loading={busy} icon={<FileSearchOutlined />} onClick={check}>检查数据</Button><Button type="primary" disabled={!checking?.result || !checkedParams || !checking.result.summary.products} loading={busy} onClick={() => void perform(async () => { if (!checkedParams) return; const r = await salesApi.create(projectId, { ...checkedParams, check_only: false }); setCurrent(r); setComposing(false); navigate(root); void reload(r.id) })}>确认并生成月报</Button></div>}>
      {error && <Alert type="error" title={error} showIcon />}
      <div className="sales-settings"><label>使用哪些数据<Select mode="multiple" aria-label="月报数据版本" value={sources} onChange={setSources} options={versions.map(v => ({ value: v.id, label: `${v.filename} · V${v.number}` }))} /></label>
        <label>分析月份<input type="month" aria-label="分析月份" value={month} onChange={e => { setMonth(e.target.value); setChecking(null) }} /></label>
        {sourceInfo.map(s => <p key={s.version_id}>{versions.find(v => v.id === s.version_id)?.filename}：{s.start ?? '日期未知'} 至 {s.end ?? '日期未知'}</p>)}
        {sources.length > 0 && !sourceInfo.length && <Spin />}
        <Checkbox checked={complete} onChange={e => { setComplete(e.target.checked); setChecking(null) }}>我确认以下日期内的销售记录完整，未记录销售的商品日可按零销量计算</Checkbox>
        {complete && <div className="sales-date-pair"><label>完整记录起点<input aria-label="完整记录起点" type="date" value={start} onChange={e => { setStart(e.target.value); setChecking(null) }} /></label><label>完整记录终点<input aria-label="完整记录终点" type="date" value={end} onChange={e => { setEnd(e.target.value); setChecking(null) }} /></label></div>}
        <label>已知停业日期<Input aria-label="已知停业日期" placeholder="例如 2026-10-01，多天用逗号隔开" value={closed} onChange={e => { setClosed(e.target.value); setChecking(null) }} /></label>
        {sources.length > 1 && <label>重叠日期怎么处理<Select value={merge} onChange={v => { setMerge(v); setChecking(null) }} options={[{ value: 'append', label: '仅追加不重叠日期' }, { value: 'replace_overlap', label: '用较新版本覆盖整个重叠日期范围' }]} /></label>}
        <label>完全重复候选<Select value={duplicates} onChange={v => { setDuplicates(v); setChecking(null) }} options={[{ value: 'keep', label: '先保留，核对后再决定' }, { value: 'drop_exact', label: '确认删除完全重复记录' }]} /></label>
        {checking && !finished.has(checking.status) && <div className="sales-processing"><Spin /><span>{checking.message}</span><Button onClick={() => void salesApi.cancel(projectId, checking.id)}>取消</Button></div>}
        {checking && finished.has(checking.status) && !checking.result && <Alert title={checking.message} type="warning" />}
        {checking?.result && <div className="sales-quality-preview"><h3>数据检查结果</h3><p>共 {checking.result.quality.input_rows.toLocaleString()} 行，纳入 {checking.result.quality.included_rows.toLocaleString()} 行，排除 {checking.result.quality.excluded_rows.toLocaleString()} 行。</p>{checking.result.quality.reasons.map(r => <p key={r.code}>{r.label}：{r.count.toLocaleString()} 行</p>)}<p>重复候选：{checking.result.quality.duplicate_candidates.toLocaleString()} 行。</p><p>本月 {checking.result.summary.products} 件商品，可进行销售复盘；预测和异常检测会在生成时检查历史条件。</p><Button onClick={() => exportFile(salesApi.download(projectId, checking.id, 'sales_row_audit.csv'))}>下载排除明细</Button><p>{checking.result.notices.join(' ')}</p></div>}
      </div>
    </Drawer>
    <Drawer title={product?.name ?? '商品详情'} open={!!product} width={690} onClose={() => setDetailId(null)}>
      {product && report && <><div className="sales-detail-metrics"><span>本月售出 <strong>{number(product.quantity)} {report.summary.unit}</strong></span><span>销售额 <strong>{number(product.amount)} {report.summary.currency}</strong></span></div>{product.daily.length > 0 && <SalesChart points={product.daily.map(p => ({ date: p.date, value: p.quantity }))} label={`${product.name} 每日销量`} />}<p>{product.reason || '当前没有需特别关注的变化。'}</p>
        {product.anomalies.length > 0 && <><h3>这些日期值得核对</h3><Table rowKey="date" size="small" pagination={false} dataSource={product.anomalies} columns={[{ title: '日期', dataIndex: 'date', render: (day: string) => <Button type="link" loading={busy} onClick={() => void perform(async () => setRecordRows(await salesApi.itemRecords(projectId, current!.id, product.id, day)))}>{day}</Button> }, { title: '实际销量', dataIndex: 'actual', render: number }, { title: '历史中位数', dataIndex: 'reference', render: number }]} /></>}
        {recordRows && <div className="sales-source-records"><h3>{recordRows.date} 的原始记录</h3><p>共 {recordRows.count} 条，显示前 {recordRows.shown} 条（含排除记录）。</p><Table rowKey={r => `${r.version_id}:${r.source_row_id}`} size="small" pagination={false} dataSource={recordRows.items} scroll={{ x: 480 }} columns={[{ title: '原始行号', dataIndex: 'source_row_id' }, { title: '数量', dataIndex: 'quantity' }, { title: '单价', dataIndex: 'unit_price' }, { title: '处理', dataIndex: 'reason', render: (v: string) => v === 'included' ? '纳入统计' : report.quality.reasons.find(r => r.code === v)?.label ?? v }]} /></div>}
        <div className="sales-detail-section"><h3>接下来七天</h3>{product.forecast ? <><strong className="sales-forecast-value">约 {number(product.forecast.quantity)} {report.summary.unit}</strong><p>{product.forecast.start} 至 {product.forecast.end} · {methods[product.forecast.method]}</p><p>历史验证中，七天总量平均差约 {number(product.forecast.validation_mae)} {report.summary.unit}。{product.forecast.notice}</p>
          <h3>算一下七天备货参考</h3><div className="sales-inventory"><label>预测起点的可售库存<InputNumber aria-label="可售库存" min={0} value={inventorySet ? inventory.available : null} onChange={v => { setInventorySet(v !== null); setInventory(r => ({ ...r, available: v ?? 0, confirmed: false })) }} /></label><label>七天内已下单、确定到货数量<InputNumber aria-label="确定到货数量" min={0} value={inventory.incoming} onChange={v => setInventory(r => ({ ...r, incoming: v ?? 0, confirmed: false }))} /></label>{inventory.incoming > 0 && <label>预计到货日<input aria-label="预计到货日" type="date" value={inventory.arrival_date} onChange={e => setInventory(r => ({ ...r, arrival_date: e.target.value, confirmed: false }))} /></label>}<label>想额外保留的备用量<InputNumber aria-label="备用量" min={0} value={inventory.reserve} onChange={v => setInventory(r => ({ ...r, reserve: v ?? 0, confirmed: false }))} /></label><label>每个包装含多少销售单位<InputNumber aria-label="包装单位" min={1} value={inventory.pack_size} onChange={v => setInventory(r => ({ ...r, pack_size: v ?? 1, confirmed: false }))} /></label></div>
          <Checkbox checked={inventory.confirmed} onChange={e => setInventory(r => ({ ...r, confirmed: e.target.checked }))}>我已确认 {product.forecast.start} 的可售库存、未到货数量（没有则为零）与备用量</Checkbox><Button className="sales-inventory-button" disabled={!inventory.confirmed || !inventorySet} loading={busy} onClick={() => void perform(async () => { const saved = await salesApi.inventory(projectId, current!.id, { ...inventory, arrival_date: inventory.arrival_date || null, item_id: product.id, snapshot_date: product.forecast!.start }); setRecords(r => ({ ...r, [`inventory:${product.id}`]: saved })) })}>计算数量参考</Button>
          {records[`inventory:${product.id}`] && <Alert type="info" title={`七天补货参考：${number(records[`inventory:${product.id}`].value.suggested_quantity)} ${report.summary.unit}`} description={records[`inventory:${product.id}`].value.notice} />}
        </> : <p>{report.forecast.reason || '这款商品的历史成交或回测效果不足，暂不发布预测，也不计算补货数量。'}</p>}</div>
        <ProductNote key={`${current!.id}:${product.id}`} projectId={projectId} runId={current!.id} itemId={product.id} dates={product.anomalies.map(a => a.date)} />
        <div className="sales-bottom"><Button icon={<MessageOutlined />} onClick={() => setAi(true)}>问问这件商品</Button><Button icon={<FileSearchOutlined />} onClick={() => setEvidence(true)}>查看计算依据</Button></div>
      </>}
    </Drawer>
    <Drawer title="这份月报的依据" open={evidence} width={700} onClose={() => setEvidence(false)}>{report && <div className="sales-evidence"><h3>使用的数据</h3>{report.sources.map(s => <p key={s.version_id}>{s.filename} · 字段版本 {s.mapping_revision}</p>)}<p>{report.notices.join(' ')}</p><h3>数据检查</h3><p>纳入 {number(report.quality.included_rows)} 行，排除 {number(report.quality.excluded_rows)} 行。</p>{report.quality.reasons.map(r => <p key={r.code}>{r.label}：{number(r.count)}</p>)}<h3>预测与简单方法对照</h3><p>{report.forecast.reason || `本次采用：${methods[report.forecast.selected_method ?? ''] ?? '历史方法'}。可发布 ${report.forecast.published_items ?? 0} 件商品的预测。`}</p><Table size="small" rowKey={r => r.method + r.split} pagination={false} dataSource={report.forecast.metrics} columns={[{ title: '方法', dataIndex: 'method', render: (v: string) => methods[v] }, { title: '区间', dataIndex: 'split', render: (v: string) => v === 'test' ? '独立测试' : '验证' }, { title: '平均绝对误差', dataIndex: 'mae', render: number }, { title: '汇总相对误差', dataIndex: 'wape', render: (v: number | null) => v === null ? '—' : `${(v * 100).toFixed(1)}%` }]} /><h3>异常检测</h3><p>{report.anomaly.reason || report.anomaly.warning}</p><div className="sales-evidence-downloads">{['sales_row_audit.csv', 'sales_backtests.csv', 'sales_report.json', 'manifest.json'].map(file => <Button key={file} icon={<DownloadOutlined />} onClick={() => exportFile(salesApi.download(projectId, current!.id, file))}>{({ 'sales_row_audit.csv': '逐行处理记录', 'sales_backtests.csv': '预测回测记录', 'sales_report.json': '完整计算结果', 'manifest.json': '版本与参数' } as Record<string, string>)[file]}</Button>)}</div></div>}</Drawer>
    <Drawer title="导出月报" open={exporting} width={420} onClose={() => setExporting(false)}><Checkbox checked={allExport} onChange={e => setAllExport(e.target.checked)}>附上全部待关注商品</Checkbox><div className="sales-export-actions"><Button type="primary" icon={<DownloadOutlined />} onClick={() => current && exportFile(salesApi.report(projectId, current.id, allExport))}>下载月报</Button><Button icon={<DownloadOutlined />} onClick={() => current && exportFile(salesApi.download(projectId, current.id, 'sales_products.csv'))}>下载全部商品表</Button></div><p className="sales-caveat">月报可在浏览器中打印保存为 PDF。</p></Drawer>
    <Drawer title="销售助手" open={ai} width={470} onClose={() => setAi(false)}><p>{product ? `正在查看：${product.name}` : '根据当前月报回答'}</p><Input.TextArea aria-label="向销售助手提问" value={question} onChange={e => setQuestion(e.target.value)} maxLength={500} autoSize={{ minRows: 3, maxRows: 6 }} placeholder="为什么建议我留意这件商品？" /><Button className="sales-ask" type="primary" icon={<SendOutlined />} loading={aiBusy} disabled={!question.trim() || !report} onClick={async () => { setAiBusy(true); try { const r = await salesApi.ask(projectId, current!.id, question, detailId); setAnswer(r.answer) } catch (e) { setAnswer((e as Error).message) } finally { setAiBusy(false) } }}>提问</Button>{answer && <div className="sales-ai-answer"><p>{answer}</p><Button type="link" onClick={() => setEvidence(true)}>核对本次月报依据</Button></div>}</Drawer>
    <Drawer title="记录处理情况" width={430} open={!!actionEdit} onClose={() => setActionEdit(null)}><Input.TextArea aria-label="处理备注" value={note} onChange={e => setNote(e.target.value)} maxLength={500} rows={4} placeholder="例如：当天缺货，已核对" /><Button className="sales-ask" type="primary" loading={busy} onClick={() => void perform(async () => { if (!actionEdit || !current) return; const old = records[`action:${actionEdit}`]; const saved = await salesApi.action(projectId, current.id, actionEdit, old?.value.status ?? 'pending', note, old?.revision ?? 0); setRecords(r => ({ ...r, [`action:${actionEdit}`]: saved })); setActionEdit(null); void message.success('已保存处理备注') })}>保存备注</Button></Drawer>
  </div>
}
