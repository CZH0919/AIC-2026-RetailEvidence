import { useState } from 'react'
import { Alert, Button, Checkbox, Input, Select } from 'antd'
import type { Mapping, Preview } from '../data'

export const fields = [
  ['order_id', '订单 / 购物篮标识'], ['item_id', '商品标识'], ['item_name', '商品名称'], ['customer_id', '客户标识'],
  ['event_time', '交易时间'], ['quantity', '数量'], ['unit_price', '单价'], ['line_amount', '行金额'],
  ['order_amount', '订单总额'], ['currency', '币种'], ['record_status', '交易状态'], ['country', '国家 / 地区'], ['category', '商品分类'],
]
const options = (pairs: string[][]) => pairs.map(([value, label]) => ({ value, label }))
export function MappingEditor({ preview, value, onChange }: { preview: Preview; value: Mapping; onChange: (v: Mapping) => void }) {
  const [status, setStatus] = useState('')
  const update = (patch: Partial<Mapping>) => onChange({ ...value, ...patch, confirmed: false })
  const select = (key: keyof Mapping, label: string, choices: string[][]) => <label className="data-field"><span>{label}</span><Select aria-label={label} value={value[key] as string | null} options={options(choices)} onChange={v => update({ [key]: v })} /></label>
  return <div className="mapping-editor">
    <div className="editor-intro"><span className="eyebrow">FIELD MAPPING</span><h3>让每一列都有明确含义</h3><p>已按列名提出对应建议。请核对样例，并保留无法确定的字段为空。</p></div>
    {preview.suggestions.warnings.length > 0 && <Alert type="warning" showIcon title="部分字段需要你判断" description={preview.suggestions.warnings.join(' ')} />}
    <div className="mapping-grid">{fields.map(([key, label]) => {
      const selected = preview.columns.find(c => c.key === value.columns[key])
      return <label className="data-field" key={key}><span>{label}</span><Select aria-label={`对应${label}`} allowClear placeholder="不对应此字段" value={value.columns[key] ?? undefined}
        options={preview.columns.map(c => ({ value: c.key, label: c.name, disabled: Object.entries(value.columns).some(([k, v]) => k !== key && v === c.key) }))}
        onChange={v => update({ columns: { ...value.columns, [key]: v ?? null }, ...(key === 'currency' && v ? { currency_constant: null } : {}) })} />
        <small>{selected ? `样例：${selected.examples.join(' · ') || '全部为空'}` : '保留未知，不补造字段'}</small></label>
    })}</div>
    <div className="semantics-heading"><h3>确认业务口径</h3><p>这些选择决定后续如何理解数据，不会修改原始文件。</p></div>
    <div className="mapping-grid">
      <label className="data-field"><span>每行是什么记录</span><Select aria-label="记录类型" value={value.record_kind ?? 'transactions'} options={options([['transactions', '一笔商品销售明细'], ['daily_summary', '某商品一天的销售汇总'], ['monthly_summary', '某商品一个月的销售汇总']])} onChange={kind => update({ record_kind: kind, ...(kind !== 'transactions' ? { order_boundary: 'unavailable', columns: { ...value.columns, order_id: null, order_amount: null }, amount_mode: value.amount_mode === 'order_amount' ? 'none' : value.amount_mode } : {}) })} /></label>
      {value.record_kind === 'monthly_summary' && <label className="data-field"><span>这份月汇总属于哪一月</span><input type="month" aria-label="月汇总月份" value={value.summary_month ?? ''} onChange={e => update({ summary_month: e.target.value || null })} /></label>}
      {select('order_boundary', '订单边界', [['order_id', '相同标识为同一订单'], ['basket_id', '相同标识为同一购物篮'], ['row_basket', '原始每行是一个购物篮'], ['unavailable', '无法确认订单边界']])}
      {select('amount_mode', '金额口径', [['none', '不使用金额'], ['line_amount', '使用行金额'], ['quantity_unit_price', '使用数量 × 单价'], ['order_amount', '使用订单总额，每单计一次']])}
      {value.amount_mode !== 'none' && !value.columns.currency && <label className="data-field"><span>固定币种</span><Input aria-label="固定币种" maxLength={3} placeholder="例如 GBP / CNY" value={value.currency_constant ?? ''} onChange={e => update({ currency_constant: e.target.value.toUpperCase() || null })} /></label>}
      {value.columns.quantity && <label className="data-field"><span>数量单位</span><Input aria-label="数量单位" maxLength={64} placeholder="例如 件、包或原始商品单位" value={value.quantity_unit} onChange={e => update({ quantity_unit: e.target.value })} /></label>}
      {value.columns.event_time && <>{select('time_format', '时间格式', [['iso8601', 'ISO 日期 / Excel 日期'], ['%Y-%m-%d', '年-月-日'], ['%Y/%m/%d', '年/月/日'], ['%Y-%m-%d %H:%M:%S', '年-月-日 时:分:秒'], ['%d/%m/%Y %H:%M', '日/月/年 时:分'], ['%m/%d/%Y %H:%M', '月/日/年 时:分'], ['%d/%m/%Y', '日/月/年'], ['%m/%d/%Y', '月/日/年']])}
        {select('timezone', '时间所属时区', [['Europe/London', '伦敦'], ['Asia/Shanghai', '中国标准时间'], ['UTC', 'UTC'], ['America/New_York', '纽约'], ['Europe/Berlin', '柏林'], ['Asia/Tokyo', '东京']])}</>}
      {select('status_rule', '取消与退货含义', [['unspecified', '含义未知，保留待核验'], ['all_forward', '确认全部为正向记录'], ['uci_cancel_prefix', '订单 C 前缀表示取消（UCI）'], ['status_column', '由状态列明确区分']])}
    </div>
    {value.status_rule === 'status_column' && <div className="status-values"><strong>原始状态对应关系</strong>{Object.entries(value.status_values).map(([raw, meaning]) => <div key={raw}><span>{raw}</span><Select aria-label={`状态 ${raw} 的含义`} value={meaning} options={options([['forward', '正向交易'], ['cancelled', '取消'], ['return', '退货'], ['unknown', '未知']])} onChange={v => update({ status_values: { ...value.status_values, [raw]: v } })} /><Button onClick={() => { const next = { ...value.status_values }; delete next[raw]; update({ status_values: next }) }}>移除</Button></div>)}
      <div><Input aria-label="添加原始状态" placeholder="输入文件中的原始状态" maxLength={100} value={status} onChange={e => setStatus(e.target.value)} /><Button disabled={!status.trim() || Object.keys(value.status_values).length >= 20} onClick={() => { update({ status_values: { ...value.status_values, [status.trim()]: 'unknown' } }); setStatus('') }}>添加</Button></div></div>}
    {value.amount_mode === 'order_amount' && <Alert type="warning" showIcon title="订单总额不能逐行累加" description="同一订单在多行重复的总额只计一次；金额不一致的订单需要核验。行金额与订单总额分别保存。" />}
    <div className="confirm-semantics"><Checkbox checked={value.confirmed} onChange={e => onChange({ ...value, confirmed: e.target.checked })}>我已核对字段对应、订单边界及上述业务含义</Checkbox></div>
  </div>
}
