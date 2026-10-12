import { useEffect, useState } from 'react'
import { Alert, App, Button, Checkbox, Drawer, Dropdown, Input, InputNumber, Select, Segmented, Spin, Table } from 'antd'
import { DownloadOutlined, FileSearchOutlined, MessageOutlined, PlusOutlined, MoreOutlined, SendOutlined, StopOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { dataApi } from '../data'
import type { Version } from '../data'
import { salesApi } from '../retail'
import type { SalesProduct, SalesRun, SavedRecord, SourceRecords } from '../retail'
import { finished } from '../quality'
import { SalesImportWizard } from './SalesImportWizard'
import { SalesChart } from './SalesChart'
import { SalesOverview } from './SalesOverview'
import { SalesReportExplanation } from './SalesReportExplanation'
import { ProductNote } from './ProductNote'
import { ProductEvidence } from './ProductEvidence'
import { EmptyState, LoadingState } from './States'

const number = (v: number | null | undefined) => v == null ? '—' : v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
const methods: Record<string, string> = { gradient_boosting: '历史销售参考', last_week: '上一周销量参考', four_week_mean: '过去四周平均参考', exponential_smoothing: '近期销量平滑参考', croston_sba: '间歇成交参考' }
const flagNames: Record<string, string> = { growth: '卖得更多', decline: '卖得更少', anomaly: '变化需核对', contribution: '销售额贡献较高' }

export default function SalesWorkspace({ projectId, productsMode = false }: { projectId: string; productsMode?: boolean }) {
  const [versions, setVersions] = useState<Version[]>([]), [runs, setRuns] = useState<SalesRun[]>([])
  const [current, setCurrent] = useState<SalesRun | null>(null), [loading, setLoading] = useState(true)
  const [error, setError] = useState(''), [importing, setImporting] = useState(false), [composing, setComposing] = useState(false)
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
  }
  useEffect(() => {
    let active = true
    reload(params.get('run') ?? undefined).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    if (params.get('compose')) setComposing(true)
    return () => { active = false }
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!current || finished.has(current.status)) return
    const timer = window.setInterval(() => salesApi.run(projectId, current.id).then(r => {
      setCurrent(r); if (finished.has(r.status)) void reload(r.id)
    }).catch(e => setError(e.message)), 1800)
    return () => clearInterval(timer)
  }, [current?.id, current?.status, projectId])
  useEffect(() => { if (report) salesApi.records(projectId, current!.id).then(r => setRecords(r.items)).catch(e => setError(e.message)); else setRecords({}) }, [current?.id, report?.context.run_id, projectId])
  useEffect(() => { setRecordRows(null); setInventorySet(false); setInventory({ available: 0, incoming: 0, reserve: 0, pack_size: 1, arrival_date: '', confirmed: false }); setAnswer('') }, [detailId, current?.id])

  const perform = async (task: () => Promise<void>) => { setBusy(true); setError(''); try { await task() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  const exportFile = (url: string) => { const anchor = document.createElement('a'); anchor.href = url; anchor.click() }
  const filteringAttention = params.get('attention') === '1'
  const filtered = report?.products.filter(p => (!filteringAttention || p.flags.length) && (category === 'all' || p.category === category) && (signal === 'all' || p.flags.includes(signal)) && `${p.name} ${p.id}`.toLowerCase().includes(query.toLowerCase())) ?? []
  const columns = [
    { title: '商品', dataIndex: 'name', key: 'name', width:220, render: (_: string, p: SalesProduct) => <Button type="link" className="sales-item-name" onClick={() => setDetailId(p.id)}>{p.name}</Button> },
    { title: '销量', dataIndex: 'quantity', width:95, sorter: (a: SalesProduct, b: SalesProduct) => a.quantity - b.quantity, render: number },
    ...(report?.products.some(p => p.amount !== null) ? [{ title: `销售额 (${report.summary.currency ?? ''})`, dataIndex: 'amount', width:130, render: number, sorter: (a: SalesProduct, b: SalesProduct) => (a.amount ?? -1) - (b.amount ?? -1) }] : []),
  ]
  const productColumns = [
    { ...columns[0], width: 160 },
    { ...columns[1], width: 70, align: 'right' as const },
    ...(report?.products.some(p => p.amount !== null) ? [{ ...columns[2], width: 115, align: 'right' as const }] : []),
    { title: '销售情况', key: 'situation', width: 135, render: (_: unknown, p: SalesProduct) => <div className="sales-product-signals">
      {p.change !== null && <span className={`sales-product-change ${p.flags.includes('growth') ? 'is-growth' : p.flags.includes('decline') ? 'is-decline' : ''}`}>
        {p.change > 0 ? '↑' : p.change < 0 ? '↓' : ''} {Math.abs(p.change * 100).toFixed(0)}% {p.change > 0 ? '增加' : p.change < 0 ? '减少' : '变化'}
      </span>}
      {p.anomalies.length > 0 && <span className="sales-product-alert">销量异常：{p.anomalies.length} 天</span>}
      {p.profile?.labels.slice(0, 2).map(label => <span className="sales-product-neutral" key={label}>{label}</span>)}
      {p.change === null && !p.anomalies.length && <span className="sales-product-neutral">暂无重点提醒</span>}
    </div> },
  ]
  if (loading) return <LoadingState />

  return <div className="sales-workspace">
    <div className={`sales-toolbar ${productsMode ? '' : 'overview-toolbar'}`}>
      <h2>{productsMode ? '商品分析' : report ? `${report.month.slice(0, 4)} 年 ${Number(report.month.slice(5))} 月` : '销售总览'}</h2>
      <div>
        {runs.length > 0 && <Select aria-label="选择历史月报" value={current?.id} placeholder="历史月报" style={{ width: 185 }} options={runs.map(r => ({ value: r.id, label: `${r.parameters?.sales.month ?? ''} · ${r.created_at.slice(0, 10)}` }))} onChange={id => void perform(async () => {
          setChartScope('current'); setDetailId(null); setCurrent(await salesApi.run(projectId, id))
          navigate(`${root}${productsMode ? '/products' : ''}?run=${id}${productsMode && filteringAttention ? '&attention=1' : ''}`)
        })} />}
        <Button type={productsMode ? 'default' : 'primary'} icon={<PlusOutlined />} onClick={() => setImporting(true)}>上传销售表</Button>
        {report && <Button type="text" icon={<DownloadOutlined />} onClick={() => setExporting(true)}>导出</Button>}
        <Dropdown trigger={['click']} menu={{ items: [
          ...(versions.length ? [{ key: 'generate', label: '生成月报' }] : []),
          ...(report ? [{ key: 'evidence', label: '月报怎么算的' }] : []),
          { key: 'data', label: '数据记录' },
          { key: 'analysis', label: '补充分析' },
        ], onClick: ({ key }) => {
          if (key === 'generate') setComposing(true)
          else if (key === 'evidence') setEvidence(true)
          else navigate(`${root}/${key === 'data' ? 'data' : 'quality'}`)
        } }}><Button type="text" icon={<MoreOutlined />} aria-label="更多操作">更多</Button></Dropdown>
      </div>
    </div>
    {error && <Alert type="error" showIcon closable onClose={() => setError('')} title={error} />}
    {!current && <EmptyState title="先看看这个月卖得怎么样" description="上传销售表，确认内容后查看销售分析。" action={<Button type="primary" icon={<PlusOutlined />} onClick={() => setImporting(true)}>上传销售表</Button>} />}
    {current && !finished.has(current.status) && <div className="sales-processing"><Spin /><strong>{current.message}</strong><Button icon={<StopOutlined />} onClick={() => void perform(async () => { await salesApi.cancel(projectId, current.id) })}>取消处理</Button></div>}
    {current && finished.has(current.status) && !report && <Alert type="warning" title={current.message} action={<Button onClick={() => setComposing(true)}>调整后重试</Button>} />}
    {report && !productsMode && <SalesOverview key={current!.id}
      report={report} chartScope={chartScope} onChartScope={setChartScope} records={records}
      onProduct={setDetailId} onAllProducts={() => navigate(`${root}/products?run=${current!.id}`)} onAsk={() => setAi(true)}
      onActionStatus={(action, status) => void perform(async () => {
        const old = records[`action:${action.id}`]
        const saved = await salesApi.action(projectId, current!.id, action.id, status, old?.value.note ?? '', old?.revision ?? 0)
        setRecords(rows => ({ ...rows, [`action:${action.id}`]: saved }))
      })}
      onActionNote={action => { setActionEdit(action.id); setNote(records[`action:${action.id}`]?.value.note ?? '') }}
    />}
    {report && productsMode && <section className="sales-band sales-product-list">
      <div className="sales-filter">
        <Segmented value={filteringAttention ? 'attention' : 'all'} options={[{ value: 'all', label: `全部商品 ${report.products.length}` }, { value: 'attention', label: `待关注 ${report.attention_ids.length}` }]} onChange={v => navigate(`${root}/products?run=${current?.id ?? ''}${v === 'attention' ? '&attention=1' : ''}`)} />
        <Input.Search aria-label="搜索商品" placeholder="商品名称或编号" value={query} onChange={e => setQuery(e.target.value)} style={{ maxWidth: 240 }} />
        <Select aria-label="筛选销售变化" value={signal} onChange={setSignal} options={[{ value: 'all', label: '所有变化' }, ...Object.entries(flagNames).map(([value, label]) => ({ value, label }))]} style={{ width: 140 }} />
        {report.products.some(p => p.category) && <Select aria-label="商品分类" value={category} onChange={setCategory} style={{ width: 150 }} options={[{ value: 'all', label: '全部分类' }, ...Array.from(new Set(report.products.map(p => p.category).filter((c): c is string => !!c))).sort().map(c => ({ value: c, label: c }))]} />}
      </div>
      <p className="sales-product-list-hint">点击商品名称查看趋势和原因。销量单位：{report.summary.unit}。{report.products.some(p => p.change !== null) && (report.products.some(p => p.daily.length) ? '变化幅度比较月底最后 7 天与此前 7 天。' : '变化幅度与上月比较。')}</p>
      <Table rowKey="id" size="small" dataSource={filtered} columns={productColumns} pagination={{ pageSize: 20, showSizeChanger: false, showTotal: total => `共 ${total} 件商品` }} scroll={{ x: 480 }} />
    </section>}
    {(importing || composing) && <SalesImportWizard projectId={projectId} versions={versions} existing={composing} initialSources={report?.parameters.sources.map(s => s.version_id)}
      onClose={() => { setImporting(false); setComposing(false); void reload() }}
      onDone={run => { setCurrent(run); setImporting(false); setComposing(false); setDetailId(null); setChartScope('current'); navigate(`${root}?run=${run.id}`); void reload(run.id) }} />}
    <Drawer title={product?.name ?? '商品详情'} open={!!product} width={690} onClose={() => setDetailId(null)}>
      {product && report && <div className="product-detail" key={`${current!.id}:${product.id}`}>
        <header className="product-detail-summary">
          <span className="product-detail-period">{report.month} · 商品销售</span>
          <h2>{product.flags.includes('growth') ? '销量明显上升' : product.flags.includes('decline') ? '销量有所下降' : product.anomalies.length ? `发现 ${product.anomalies.length} 天销量异常` : '本月销售概况'}</h2>
          {(product.flags.includes('growth') || product.flags.includes('decline')) && <p>{product.daily.length ? '比较月底最后 7 天与此前 7 天' : '与上月比较'}{product.anomalies.length > 0 && ` · 销量异常：${product.anomalies.length} 天`}</p>}
        </header>

        <div className="product-detail-metrics">
          <div><span>本月销量</span><strong>{number(product.quantity)}</strong><small>{report.summary.unit}</small></div>
          <div><span>本月销售额</span><strong>{number(product.amount)}</strong><small>{report.summary.currency || report.summary.amount_label}</small></div>
        </div>

        {product.daily.length > 0 && <section className="product-detail-trend">
          <h3>每天卖得怎么样</h3>
          <SalesChart points={product.daily.map(p => ({ date: p.date, value: p.quantity }))} label={`${product.name} 每日销量`} />
        </section>}

        <section className="product-detail-forecast">
          <h3>{['fee_service', 'accounting'].includes(product.item_type?.kind ?? '') ? '七天记录数量参考' : '七天销量预测'}</h3>
          {product.forecast ? <>
            <p className="product-detail-prediction"><strong>约 {number(product.forecast.quantity)}</strong><span>{report.summary.unit}</span></p>
            <p className="product-detail-muted">{product.forecast.start} 至 {product.forecast.end} · {['fee_service', 'accounting'].includes(product.item_type?.kind ?? '') ? '用于了解记录变化，不适用实物备货' : '进货时还需结合库存'}</p>
            {product.forecast.range && <p>历史误差参考范围：{number(product.forecast.range.lower)} 至 {number(product.forecast.range.upper)} {report.summary.unit}，不保证未来覆盖。</p>}
            <details className="product-detail-method">
              <summary>预测说明</summary>
              <p>参考方法：{methods[product.forecast.method]}。历史检验中，七天总销量平均相差约 {number(product.forecast.validation_mae)} {report.summary.unit}。</p>
              {product.forecast.test_mae != null && <p>最近 {product.forecast.test_origins} 次独立检查中，七天总量平均相差约 {number(product.forecast.test_mae)} {report.summary.unit}。请结合近期误差使用预测。</p>}
              <p>{product.forecast.notice}</p>
            </details>
          </> : <>
            <p className="product-detail-muted">这款商品暂时没有可用预测。</p>
            <details className="product-detail-method"><summary>查看原因</summary><p>{product.forecast_reason || report.forecast.reason || '这款商品的历史成交或检验效果不足，暂不发布预测。'}</p></details>
          </>}
        </section>

        <div className="product-detail-tools">
          <ProductEvidence product={product} currency={report.summary.currency} />
          <details className="product-detail-disclosure">
            <summary><span>查看销售变化</span><small>{product.anomalies.length ? `销量异常：${product.anomalies.length} 天` : '变化说明'}</small></summary>
            <div className="product-detail-content">
              <p>{product.reason || '当前没有需特别关注的变化。'}</p>
              {!!product.anomaly_events?.length && <ul>{product.anomaly_events.map(event => <li key={event.start}>{event.start} 至 {event.end}：实际 {number(event.actual)} {report.summary.unit}，此前相同星期参考 {number(event.reference)} {report.summary.unit}。请核对下列日期。</li>)}</ul>}
              {product.anomalies.length > 0 && <>
                <p className="product-detail-muted">点日期查看当天的销售记录。数量单位：{report.summary.unit}。</p>
                <Table rowKey="date" size="small" pagination={false} dataSource={product.anomalies} columns={[
                  { title: '日期', dataIndex: 'date', render: (day: string) => <Button type="link" loading={busy} onClick={() => void perform(async () => setRecordRows(await salesApi.itemRecords(projectId, current!.id, product.id, day)))}>{day}</Button> },
                  { title: '实际销量', dataIndex: 'actual', render: number },
                  { title: product.profile ? '同星期参考' : '历史中位数', dataIndex: 'reference', render: number },
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
          {records[`inventory:${product.id}`] && <Alert type="info" title={`七天补货参考：${number(records[`inventory:${product.id}`].value.suggested_quantity)} ${report.summary.unit}`} description={records[`inventory:${product.id}`].value.notice} />}
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
    <Drawer title="导出月报" open={exporting} width={420} onClose={() => setExporting(false)}><Checkbox checked={allExport} onChange={e => setAllExport(e.target.checked)}>附上全部待关注商品</Checkbox><div className="sales-export-actions"><Button type="primary" icon={<DownloadOutlined />} onClick={() => current && exportFile(salesApi.report(projectId, current.id, allExport))}>下载月报</Button><Button icon={<DownloadOutlined />} onClick={() => current && exportFile(salesApi.download(projectId, current.id, 'sales_products.csv'))}>下载全部商品表</Button></div><p className="sales-caveat">月报可在浏览器中打印保存为 PDF。</p></Drawer>
    <Drawer title="销售助手" open={ai} width={470} onClose={() => setAi(false)}><p>{product ? `正在查看：${product.name}` : '根据当前月报回答'}</p><Input.TextArea aria-label="向销售助手提问" value={question} onChange={e => setQuestion(e.target.value)} maxLength={500} autoSize={{ minRows: 3, maxRows: 6 }} placeholder="为什么建议我留意这件商品？" /><Button className="sales-ask" type="primary" icon={<SendOutlined />} loading={aiBusy} disabled={!question.trim() || !report} onClick={async () => { setAiBusy(true); try { const r = await salesApi.ask(projectId, current!.id, question, detailId); setAnswer(r.answer) } catch (e) { setAnswer((e as Error).message) } finally { setAiBusy(false) } }}>提问</Button>{answer && <div className="sales-ai-answer"><p style={{ whiteSpace: 'pre-line' }}>{answer}</p><Button type="link" onClick={() => setEvidence(true)}>查看月报怎么算的</Button></div>}</Drawer>
    <Drawer title="记录处理情况" width={430} open={!!actionEdit} onClose={() => setActionEdit(null)}><Input.TextArea aria-label="处理备注" value={note} onChange={e => setNote(e.target.value)} maxLength={500} rows={4} placeholder="例如：当天缺货，已核对" /><Button className="sales-ask" type="primary" loading={busy} onClick={() => void perform(async () => { if (!actionEdit || !current) return; const old = records[`action:${actionEdit}`]; const saved = await salesApi.action(projectId, current.id, actionEdit, old?.value.status ?? 'pending', note, old?.revision ?? 0); setRecords(r => ({ ...r, [`action:${actionEdit}`]: saved })); setActionEdit(null); void message.success('已保存处理备注') })}>保存备注</Button></Drawer>
  </div>
}
