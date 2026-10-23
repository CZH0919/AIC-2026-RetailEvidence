import { useEffect, useState } from 'react'
import { Alert, App, Button, Drawer, Input, Select, Spin, Steps } from 'antd'
import { CloudUploadOutlined, DatabaseOutlined, FileTextOutlined } from '@ant-design/icons'
import { ApiError } from '../api'
import { dataApi, initialMapping, parseDefaults } from '../data'
import type { Draft, Mapping, ParseOptions, PublicDataset, VersionDetail } from '../data'
import { DataPreview } from './DataPreview'
import { MappingEditor } from './MappingEditor'

export function ImportEditor({ projectId, initial, onClose, onSaved }: { projectId: string; initial: Draft | null; onClose: () => void; onSaved: (v: VersionDetail) => void }) {
  const [draft, setDraft] = useState(initial)
  const [step, setStep] = useState(initial?.preview ? 2 : initial ? 1 : 0)
  const [options, setOptions] = useState<ParseOptions>(initial?.options ?? { ...parseDefaults, sheets: initial?.inspection.sheets.slice(0, 1) ?? [] })
  const [mapping, setMapping] = useState<Mapping | null>(initial?.preview ? initialMapping(initial) : null)
  const [catalog, setCatalog] = useState<PublicDataset[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const { message } = App.useApp()
  useEffect(() => { let active = true; dataApi.catalog().then(r => { if (active) setCatalog(r.items) }).catch(() => {}); return () => { active = false } }, [])
  const run = async (label: string, task: () => Promise<void>) => {
    setBusy(label); setError('')
    try { await task() } catch (e) { const text = e instanceof ApiError ? e.message : '操作未完成，请重试。'; setError(text); void message.error(text) } finally { setBusy('') }
  }
  const received = (d: Draft) => { setDraft(d); setOptions({ ...parseDefaults, sheets: d.inspection.sheets.slice(0, 1), shape: d.source_dataset === 'groceries' ? 'basket_long' : 'transactions' }); setStep(1) }
  const upload = (file: File) => {
    if (file.size > 100 * 1024 * 1024) { setError('文件超过 100 MiB，请缩小后重试。'); return }
    if (!/\.(csv|xlsx)$/i.test(file.name)) { setError('仅支持 CSV 和 XLSX 文件。'); return }
    void run('正在接收文件', async () => received(await dataApi.upload(projectId, file)))
  }
  const update = (patch: Partial<ParseOptions>) => setOptions({ ...options, ...patch })
  return <Drawer open title="导入数据" width={1080} onClose={onClose} closable={!busy} maskClosable={!busy} keyboard={!busy}
    footer={<div className="import-footer"><span>{busy || '每次导入都会生成独立数据版本'}</span><div>
      <Button disabled={!!busy} onClick={onClose}>暂时关闭</Button>
      {step === 2 && <Button disabled={!!busy} onClick={() => setStep(1)}>调整读取方式</Button>}
      {step === 1 && <Button type="primary" loading={!!busy} onClick={() => draft && void run('正在解析并生成预览', async () => { const next = await dataApi.preview(projectId, draft.id, options); setDraft(next); setMapping(initialMapping(next)); setStep(2) })}>生成预览</Button>}
      {step === 2 && <><Button disabled={!!busy} onClick={() => draft && mapping && void run('正在保存草稿', async () => { setDraft(await dataApi.saveDraft(projectId, draft, mapping)); void message.success('字段草稿已保存，可稍后继续') })}>保存草稿</Button>
        <Button type="primary" loading={!!busy} disabled={!mapping?.confirmed} onClick={() => draft && mapping && void run('正在保存数据版本', async () => onSaved(await dataApi.confirm(projectId, draft, mapping)))}>确认并创建版本</Button></>}
    </div></div>}>
    <Steps current={step} items={[{ title: '选择文件' }, { title: '读取设置' }, { title: '字段与口径' }]} />
    {error && <Alert className="import-alert" type="error" showIcon title="未能完成操作" description={error} />}
    {busy && <div className="processing-note" role="status"><Spin size="small" /><span>{busy}，较大的工作簿需要一些时间。</span></div>}
    <fieldset className="import-fieldset" disabled={!!busy}>
    {step === 0 && <div className="import-start"><div className="upload-zone"><CloudUploadOutlined /><h3>把交易数据带入工作台</h3><p>上传 CSV 或 XLSX，保留原始文件并建立可追溯的数据版本。</p><label className="file-picker">选择本地文件<input aria-label="选择本地数据文件" type="file" accept=".csv,.xlsx" disabled={!!busy} onChange={e => { const file = e.target.files?.[0]; if (file) upload(file); e.target.value = '' }} /></label><small>单文件不超过 100 MiB · 150 万行 · 200 列</small></div>
      {catalog.length > 0 && <><div className="public-heading"><h3>或从公开数据开始</h3><p>使用已有数据集，体验完整导入流程。</p></div><div className="public-datasets">{catalog.map(item => <article key={item.id}><DatabaseOutlined /><h4>{item.title}</h4><p>{item.id === 'groceries' ? '真实购物篮 · 适合商品组合分析' : '零售交易明细 · 包含订单、客户与时间'}</p><div><a href={item.source_url} target="_blank" rel="noreferrer">来源与许可</a><Button disabled={!!busy} onClick={() => void run('正在准备公开数据', async () => received(await dataApi.publicImport(projectId, item.id)))}>使用此数据</Button></div></article>)}</div></>}
    </div>}
    {step === 1 && draft && <div className="parse-panel"><div className="file-summary"><FileTextOutlined /><div><strong>{draft.filename}</strong><span>{(draft.bytes / 1024 / 1024).toFixed(2)} MiB</span></div></div><h3>明确文件如何被读取</h3><p>选择正确的格式后生成预览。原始文件始终保留。</p><div className="mapping-grid">
      {draft.suffix === '.csv' ? <><label className="data-field"><span>文件编码</span><Select aria-label="文件编码" value={options.encoding} options={[{ value: 'utf-8-sig', label: 'UTF-8（含 BOM）' }, { value: 'gb18030', label: 'GB18030 / GBK' }, { value: 'cp1252', label: 'Windows-1252' }]} onChange={v => update({ encoding: v })} /></label>
        <label className="data-field"><span>列分隔符</span><Select aria-label="列分隔符" value={options.delimiter} options={[[',', '逗号'], [';', '分号'], ['\t', '制表符'], ['|', '竖线']].map(([value, label]) => ({ value, label }))} onChange={v => update({ delimiter: v })} /></label></> : <label className="data-field full"><span>选择工作表</span><Select aria-label="选择工作表" mode="multiple" value={options.sheets} options={draft.inspection.sheets.map(value => ({ value, label: value }))} onChange={v => update({ sheets: v })} /><small>只有表头名称与顺序完全相同的工作表可以合并。不同来源行仍可追溯。</small></label>}
      <label className="data-field full"><span>每行表示什么</span><Select aria-label="每行表示什么" value={options.shape} options={[{ value: 'transactions', label: '一行一条商品交易明细' }, { value: 'basket_long', label: '购物篮长表：篮子标识 + 商品' }, { value: 'basket_list', label: '每行一个购物篮，某列存放商品列表' }]} onChange={v => update({ shape: v })} /></label>
      {options.shape === 'basket_list' && <><label className="data-field"><span>商品列表所在列的表头</span><Input aria-label="商品列表表头" value={options.basket_column ?? ''} onChange={e => update({ basket_column: e.target.value })} /></label><label className="data-field"><span>商品分隔符</span><Select aria-label="商品分隔符" value={options.item_separator} options={['|', ';', ','].map(value => ({ value, label: value }))} onChange={v => update({ item_separator: v })} /></label><Alert className="full" type="info" showIcon title="以原始行建立购物篮" description="仅把选定列拆成购物篮与商品，不生成客户、时间或金额。原始文件中的其他列仍保留在来源文件中。" /></>}
    </div></div>}
    {step === 2 && draft?.preview && mapping && <><div className="import-file-label"><FileTextOutlined />{draft.filename}<span>{draft.preview.row_count.toLocaleString()} 行</span></div><DataPreview preview={draft.preview} /><MappingEditor preview={draft.preview} value={mapping} onChange={setMapping} /></>}
    </fieldset>
  </Drawer>
}
