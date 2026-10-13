import { Button, Input, Select } from 'antd'
import type { Mapping, Preview } from '../data'
import { MappingEditor } from './MappingEditor'

export function SalesImportFields({ preview, value, onChange }: { preview: Preview; value: Mapping; onChange: (value: Mapping) => void }) {
  const update = (patch: Partial<Mapping>) => onChange({ ...value, ...patch, confirmed: false })
  const setKind = (kind: string) => update({ record_kind: kind, ...(kind !== 'transactions' ? { order_boundary: 'unavailable', columns: { ...value.columns, order_id: null, order_amount: null }, amount_mode: value.amount_mode === 'order_amount' ? 'none' : value.amount_mode } : {}) })
  const noDateChoice = !value.columns.event_time && preview.columns.every(c => Object.entries(value.columns).some(([key, column]) => key !== 'event_time' && column === c.key))
  const column = (key: string, label: string, required = false) => {
    const selected = preview.columns.find(c => c.key === value.columns[key])
    return <label className="sales-upload-field" key={key}><span>{label}{required && <small>必选</small>}</span>
      <Select aria-label={label} allowClear value={value.columns[key] ?? undefined} placeholder={required ? `请选择${label}所在列` : '表格中没有'} options={preview.columns.map(c => ({ value: c.key, label: c.name, disabled: Object.entries(value.columns).some(([k, v]) => k !== key && v === c.key) }))} onChange={v => {
        const patch: Partial<Mapping> = { columns: { ...value.columns, [key]: v ?? null } }
        if (key === 'event_time' && v) { patch.time_format = value.time_format ?? 'iso8601'; patch.timezone = value.timezone ?? 'Asia/Shanghai' }
        update(patch)
      }} />
      <small>{selected ? `例如：${selected.examples.slice(0, 2).join('、') || '空值'}` : required ? '没有自动识别，请选择对应列。' : '可不填写。'}</small>
    </label>
  }
  return <div className="sales-upload-fields">
    <label className="sales-upload-field"><span>表格记录的是</span><Select aria-label="销售表记录类型" value={value.record_kind ?? 'transactions'} options={[{ value: 'transactions', label: '每笔销售的商品明细' }, { value: 'daily_summary', label: '每种商品每天的销售汇总' }, { value: 'monthly_summary', label: '整月销售汇总（不用日期列）' }]} onChange={setKind} /></label>
    {value.record_kind === 'monthly_summary' && <p className="sales-upload-muted">按月汇总分析，请在下方填写这份表所属月份。</p>}
    <div className="sales-upload-grid">{column('item_id', '商品名称或编号', true)}{column('quantity', '销量', true)}{value.record_kind !== 'monthly_summary' && <div className="sales-upload-date-field">
      {noDateChoice ? <div className="sales-upload-field"><span>销售日期</span><div className="sales-upload-no-date">这份表没有可选的日期列。</div></div> : column('event_time', '销售日期', true)}
      {!value.columns.event_time && <Button type="link" size="small" className="sales-upload-month-link" onClick={() => setKind('monthly_summary')}>没有日期，按月汇总分析</Button>}
    </div>}
      <label className="sales-upload-field"><span>销量单位</span><Input aria-label="销售表销量单位" value={value.quantity_unit} placeholder="例如：件、包、公斤" onChange={e => update({ quantity_unit: e.target.value })} /></label>
      <label className="sales-upload-field"><span>销售额怎么算</span><Select aria-label="销售额怎么算" value={value.amount_mode} options={[{ value: 'line_amount', label: '使用表格中的销售额' }, { value: 'quantity_unit_price', label: '销量 × 单价' }, { value: 'none', label: '没有销售额，只分析销量' }, ...(value.amount_mode === 'order_amount' ? [{ value: 'order_amount', label: '订单总额，每单计算一次' }] : [])]} onChange={amount_mode => update({ amount_mode })} /></label>
      {value.amount_mode === 'line_amount' && column('line_amount', '销售额', true)}
      {value.amount_mode === 'quantity_unit_price' && column('unit_price', '单价', true)}
      {value.amount_mode !== 'none' && !value.columns.currency && <label className="sales-upload-field"><span>销售额币种</span><Select aria-label="销售额币种" placeholder="请选择币种" value={value.currency_constant ?? undefined} options={[{ value: 'CNY', label: '人民币（CNY）' }, { value: 'GBP', label: '英镑（GBP）' }, { value: 'USD', label: '美元（USD）' }, { value: 'EUR', label: '欧元（EUR）' }]} onChange={currency_constant => update({ currency_constant })} /></label>}
      <label className="sales-upload-field"><span>销售记录包含</span><Select aria-label="销售记录包含" value={value.status_rule} options={[{ value: 'unspecified', label: '请选择记录内容' }, { value: 'all_forward', label: '正常销售记录' }, { value: 'uci_cancel_prefix', label: 'UCI 数据，C 开头订单为取消' }, { value: 'status_column', label: '包含取消、退货，按状态列区分' }]} onChange={status_rule => update({ status_rule })} /></label>
      {column('item_type', '商品或费用类型所在列')}
    </div>
    <p className="sales-upload-muted">类型列可填写“实物商品、费用、服务、记账”。没有类型列也可分析，之后在商品详情中确认；未确认前不自动当作实物商品。</p>
    <details className="sales-upload-more" open={value.status_rule === 'status_column' || undefined}><summary>更多字段设置</summary><MappingEditor preview={preview} value={value} onChange={onChange} /></details>
  </div>
}
