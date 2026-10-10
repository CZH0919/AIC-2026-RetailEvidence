import { useEffect, useState } from 'react'
import { Alert, App, Button, Drawer, Select, Tag } from 'antd'
import { DatabaseOutlined, EditOutlined, HistoryOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { dataApi } from '../data'
import type { Draft, Mapping, MappingVersion, Version, VersionDetail } from '../data'
import { formatDate } from '../pages/ProjectLibrary'
import { DataPreview } from './DataPreview'
import { ImportEditor } from './ImportEditor'
import { fields, MappingEditor } from './MappingEditor'
import { EmptyState, ErrorState, LoadingState } from './States'

function Semantics({ mapping }: { mapping: Mapping }) {
  const amount: Record<string, string> = { none: '不使用金额', line_amount: '行金额', order_amount: '订单总额，每单计一次', quantity_unit_price: '数量 × 单价' }
  const boundary: Record<string, string> = { order_id: '相同标识为同一订单', basket_id: '相同标识为同一购物篮', row_basket: '原始每行一个购物篮', unavailable: '边界未知' }
  const status: Record<string, string> = { unspecified: '含义待核验', all_forward: '确认全部正向', uci_cancel_prefix: '订单 C 前缀表示取消', status_column: '按已确认状态列区分' }
  return <dl className="semantic-summary"><div><dt>金额口径</dt><dd>{amount[mapping.amount_mode]}</dd></div><div><dt>币种</dt><dd>{mapping.currency_constant ?? (mapping.columns.currency ? '保留原币种列' : '未指定')}</dd></div><div><dt>订单边界</dt><dd>{boundary[mapping.order_boundary]}</dd></div><div><dt>取消 / 退货</dt><dd>{status[mapping.status_rule]}</dd></div>
    {mapping.columns.event_time && <div><dt>时间口径</dt><dd>{mapping.time_format === 'iso8601' ? 'ISO / Excel 日期' : mapping.time_format} · {mapping.timezone}</dd></div>}{mapping.columns.quantity && <div><dt>数量单位</dt><dd>{mapping.quantity_unit}</dd></div>}
  </dl>
}

export function DataWorkspace({ projectId }: { projectId: string }) {
  const navigate = useNavigate()
  const [versions, setVersions] = useState<Version[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<VersionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [importing, setImporting] = useState<{ draft: Draft | null } | null>(null)
  const [editing, setEditing] = useState<Mapping | null>(null)
  const [busy, setBusy] = useState(false)
  const [editError, setEditError] = useState('')
  const [history, setHistory] = useState<MappingVersion[] | null>(null)
  const { message, modal } = App.useApp()
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    Promise.all([dataApi.versions(projectId), dataApi.drafts(projectId)]).then(([v, d]) => {
      if (active) { setVersions(v.items); setDrafts(d.items); setSelected(old => v.items.some(x => x.id === old) ? old : v.items[0]?.id ?? '') }
    }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [projectId, reload])
  useEffect(() => {
    let active = true
    setDetail(null)
    if (selected) dataApi.version(projectId, selected).then(v => { if (active) setDetail(v) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [projectId, selected, reload])
  const failure = (e: unknown) => e instanceof ApiError ? e.message : '操作未能完成，请重试。'
  return <div className="data-workspace">
    <div className="data-heading"><h2>营业数据记录</h2><div><Button onClick={() => navigate(`/projects/${projectId}?compose=1`)}>生成月报</Button><Button type="primary" icon={<PlusOutlined />} onClick={() => setImporting({ draft: null })}>上传新数据</Button></div></div>
    {drafts.length > 0 && <div className="drafts-strip"><strong>继续未完成的导入</strong>{drafts.map(d => <div key={d.id}><span title={d.filename}>{d.filename}</span><Button size="small" onClick={() => setImporting({ draft: d })}>继续</Button><Button size="small" type="text" onClick={() => modal.confirm({ title: '放弃这份导入草稿？', content: '已保存的数据版本不受影响。', okText: '放弃草稿', cancelText: '保留', onOk: async () => { try { await dataApi.discard(projectId, d.id); setReload(x => x + 1) } catch (e) { void message.error(failure(e)); throw e } } })}>放弃</Button></div>)}</div>}
    {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={() => setReload(x => x + 1)} /> : versions.length === 0 ? <div className="workspace-panel data-empty"><div className="data-empty-mark"><DatabaseOutlined /></div><EmptyState compact title="为这个项目添加第一份数据" description="支持交易明细、购物篮和公开数据集。先查看内容，再确认字段，无需提前调整列名。" action={<Button type="primary" onClick={() => setImporting({ draft: null })}>选择数据来源</Button>} /><div className="data-principles"><span>01 保留原始文件</span><span>02 确认业务含义</span><span>03 独立保存版本</span></div></div>
      : <section className="workspace-panel version-panel"><div className="version-toolbar"><label><span>数据版本</span><Select aria-label="切换数据版本" value={selected} options={versions.map(v => ({ value: v.id, label: `V${v.number} · ${v.filename}` }))} onChange={setSelected} /></label><Tag color="cyan">{versions.length} 个版本</Tag></div>
        {!detail ? <LoadingState /> : <><div className="version-overview"><div><span className="eyebrow">VERSION {String(detail.number).padStart(2, '0')}</span><h3>{detail.filename}</h3><p>创建于 {formatDate(detail.created_at)} · 字段版本 M{detail.mapping.revision}</p></div><div className="dataset-metrics"><div><strong>{detail.row_count.toLocaleString()}</strong><span>数据行</span></div><div><strong>{detail.preview.columns.length}</strong><span>原始字段</span></div><div><strong>{(detail.bytes / 1024 / 1024).toFixed(2)}</strong><span>MiB</span></div></div></div>
          <div className="version-content"><DataPreview preview={detail.preview} /><div className="mapping-summary-heading"><div><h3>已确认的字段</h3><p>字段修改会创建新的映射版本，原有记录继续保留。</p></div><div><Button icon={<HistoryOutlined />} onClick={async () => { try { setHistory((await dataApi.history(projectId, detail.id)).items) } catch (e) { void message.error(failure(e)) } }}>历史</Button><Button icon={<EditOutlined />} onClick={() => { setEditError(''); setEditing({ ...detail.mapping.config, confirmed: false }) }}>调整字段</Button></div></div>
            <div className="mapping-tags">{fields.filter(([k]) => detail.mapping.config.columns[k]).map(([k, label]) => <div key={k}><span>{label}</span><strong>{detail.preview.columns.find(c => c.key === detail.mapping.config.columns[k])?.name}</strong></div>)}</div>
            <Semantics mapping={detail.mapping.config} />
            {detail.mapping.validation.warnings.length > 0 && <Alert type="info" showIcon title="理解这份数据" description={detail.mapping.validation.warnings.join(' ')} />}
          </div></>}
      </section>}
    {importing && <ImportEditor projectId={projectId} initial={importing.draft} onClose={() => { setImporting(null); setReload(x => x + 1) }} onSaved={v => { setImporting(null); setSelected(v.id); setReload(x => x + 1); void message.success(`数据版本 V${v.number} 已保存`) }} />}
    <Drawer open={!!editing} title="创建新的字段版本" width={1040} onClose={() => !busy && setEditing(null)} maskClosable={!busy} closable={!busy}
      footer={<div className="import-footer"><span>保留全部历史对应关系</span><Button type="primary" loading={busy} disabled={!editing?.confirmed} onClick={async () => {
        if (!detail || !editing) return
        setBusy(true); setEditError('')
        try { await dataApi.revise(projectId, detail, editing); setEditing(null); setReload(x => x + 1); void message.success('新的字段版本已保存') } catch (e) { setEditError(failure(e)) } finally { setBusy(false) }
      }}>确认并保存新映射</Button></div>}>
      {editError && <Alert type="error" title={editError} showIcon />}{detail && editing && <fieldset className="import-fieldset" disabled={busy}><MappingEditor preview={detail.preview} value={editing} onChange={setEditing} /></fieldset>}
    </Drawer>
    <Drawer open={history !== null} title="字段版本历史" width={600} onClose={() => setHistory(null)}>{history?.map(h => <article className="mapping-history" key={h.id}><div><Tag color="cyan">M{h.revision}</Tag><span>{formatDate(h.created_at)}</span></div><dl>{fields.filter(([k]) => h.config.columns[k]).map(([k, label]) => <div key={k}><dt>{label}</dt><dd>{detail?.preview.columns.find(c => c.key === h.config.columns[k])?.name}</dd></div>)}</dl><Semantics mapping={h.config} /></article>)}</Drawer>
  </div>
}
