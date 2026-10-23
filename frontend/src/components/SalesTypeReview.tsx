import { useMemo, useState } from 'react'
import { Alert, Button, Checkbox, Drawer, Input, Select, Table } from 'antd'
import { itemKindOptions, salesApi } from '../retail'
import type { ItemKind, SalesParameters, SalesProduct, SalesReport, SalesRun } from '../retail'
import { HelpHint } from './HelpHint'

export function SalesTypeReview({ projectId, report, focusId, onClose, onDone }: {
  projectId: string; report: SalesReport; focusId?: string; onClose: () => void; onDone: (run: SalesRun) => void
}) {
  const [query, setQuery] = useState(focusId ?? '')
  const [changes, setChanges] = useState<Record<string, ItemKind>>({})
  const [selected, setSelected] = useState<string[]>([])
  const [batchKind, setBatchKind] = useState<ItemKind>('physical')
  const [onlyUnknown, setOnlyUnknown] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const products = useMemo(() => new Map(report.products.map(p => [p.id, p])), [report.products])
  const visible = report.products.filter(p => (!onlyUnknown || !p.item_type || p.item_type.kind === 'unknown') && `${p.name} ${p.id}`.toLowerCase().includes(query.toLowerCase()))
  const edits = Object.entries(changes).filter(([id, kind]) => kind !== (products.get(id)?.item_type?.kind ?? 'unknown'))
  const reclassified = edits.filter(([id, kind]) => kind === 'physical' && ['fee_service', 'accounting'].includes(products.get(id)?.item_type?.kind ?? ''))
  const update = (next: Record<string, ItemKind>) => { setChanges(v => ({ ...v, ...next })); setConfirmed(false) }
  async function submit() {
    setBusy(true); setError('')
    try {
      const old = report.parameters
      // Send only accepted input fields; frozen reports also contain server-generated hashes.
      const parameters: SalesParameters = {
        sources: old.sources, month: old.month, merge_mode: old.merge_mode,
        duplicates: old.duplicates, complete_coverage: old.complete_coverage,
        coverage_start: old.coverage_start, coverage_end: old.coverage_end,
        closed_dates: old.closed_dates, missing_dates: old.missing_dates ?? [],
        item_start_dates: old.item_start_dates ?? {}, budget_seconds: old.budget_seconds ?? 1200,
        item_types: { ...old.item_types, ...Object.fromEntries(edits) }, check_only: false,
      }
      onDone(await salesApi.create(projectId, parameters))
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <Drawer title="确认商品与记录类型" open width={800} onClose={onClose} closable={!busy} maskClosable={!busy} keyboard={!busy}
    footer={<div className="sales-type-confirm-footer"><Checkbox checked={confirmed} disabled={!edits.length || busy} onChange={e => setConfirmed(e.target.checked)}>我已核对所改记录的实际类型，同意据此生成新的分析结果</Checkbox><div className="sales-type-footer"><span>已调整 {edits.length} 项</span><div><Button disabled={busy} onClick={onClose}>取消</Button><Button type="primary" loading={busy} disabled={!edits.length || !confirmed} onClick={() => void submit()}>确认并生成新月报</Button></div></div></div>}>
    <div className="sales-type-review">
      <HelpHint topic="types" />
      <p>区分可以备货的实物、费用或服务，以及记账项目。未确认的记录继续保留保护；本次调整会重新分析当前月份，历史月报保持原样。</p>
      <div className="sales-type-controls"><Input.Search aria-label="搜索待确认记录" placeholder="商品名称或编号" value={query} onChange={e => setQuery(e.target.value)} />
        <Checkbox checked={onlyUnknown} onChange={e => { setOnlyUnknown(e.target.checked); setSelected([]) }}>只看类型待确认</Checkbox></div>
      <div className="sales-type-batch"><span>已选 {selected.length} 项</span><Select aria-label="批量确认类型" value={batchKind} options={itemKindOptions} onChange={setBatchKind} /><Button disabled={!selected.length || busy} onClick={() => { update(Object.fromEntries(selected.map(id => [id, batchKind]))); setSelected([]) }}>应用到已选项</Button></div>
      <p className="sales-type-hint">批量选择仅用于原本类型待确认的记录。已识别的费用或记账项目，请逐项核对后调整。</p>
      {error && <Alert type="error" showIcon title={error} />}
      <Table<SalesProduct> rowKey="id" size="small" tableLayout="fixed" dataSource={visible} pagination={{pageSize: 10, showSizeChanger: false, showTotal: total => `共 ${total} 项`}}
        rowSelection={{selectedRowKeys: selected, onChange: keys => setSelected(keys.map(String)), getCheckboxProps: p => ({disabled: busy || !['unknown', ''].includes(p.item_type?.kind ?? '')})}}
        columns={[
          {title: '商品或记录', key: 'item', render: (_: unknown, p) => <div className="sales-type-item"><strong>{p.name}</strong><small>{p.id}</small></div>},
          {title: '确认类型', key: 'type', width: 160, render: (_: unknown, p) => <Select aria-label={`记录类型 ${p.id}`} disabled={busy} value={changes[p.id] ?? p.item_type?.kind ?? 'unknown'} options={itemKindOptions} onChange={kind => update({[p.id]: kind})} />},
        ]} />
      {reclassified.length > 0 && <Alert type="warning" showIcon title={`其中 ${reclassified.length} 项原为费用或记账，正在改为实物`} description="请确认这些记录确实可以按实物管理库存，不能仅因为名称像商品就改变类型。" />}
    </div>
  </Drawer>
}
