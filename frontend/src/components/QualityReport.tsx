import { useEffect, useState } from 'react'
import { Alert, Button, Select, Table, Tag } from 'antd'
import { CheckCircleOutlined, ExclamationCircleOutlined, InfoCircleOutlined } from '@ant-design/icons'
import type { QualityReport as Report } from '../quality'
import { qualityApi, viewLabels } from '../quality'

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
