import { changeLabel } from '../salesSignals'
export { changePercent } from '../salesSignals'
import type { SalesProduct } from '../retail'

const number = (value: number) => value.toLocaleString('zh-CN', {maximumFractionDigits: 2})

export function ChangeExplanation({product}: {product: SalesProduct}) {
  const c = product.comparison
  return <div className="signal-explanation">
    <p><strong>{changeLabel(product)}</strong></p>
    {c && <p className="product-detail-muted">比较：{c.current_start} 至 {c.current_end} / {c.previous_start} 至 {c.previous_end}</p>}
    {c && ['available', 'no_baseline'].includes(c.status) && c.current_quantity != null && c.previous_quantity != null && <p>这期售出 {number(c.current_quantity)}，前期售出 {number(c.previous_quantity)}。{c.previous_quantity === 0 && '前期销量为零，不计算涨跌百分比。'}</p>}
  </div>
}

export function AnomalyExplanation({product, detailed = false}: {product: SalesProduct; detailed?: boolean}) {
  const check = product.anomaly_check
  const dates = check?.tested_dates
  return <div className="signal-explanation">
    <p>{check?.message ?? '旧报告未记录这件商品是否完成异常检查。'}</p>
    {!!dates?.length && <p className="product-detail-muted">本月检查了 {dates.length} 天。{product.daily.length > dates.length && '其余日期未检查，不代表没有异常。'}</p>}
    {check?.coverage_note && <p className="product-detail-muted">{check.coverage_note}</p>}
    {detailed && !!dates?.length && <details><summary>查看检查日期</summary><p>{dates.join('、')}</p></details>}
  </div>
}

export function ProductSignals({product}: {product: SalesProduct}) {
  const c = product.comparison
  return <div className="sales-product-signals" style={{gap: 5, padding: '4px 0'}}>
    <span className={`sales-product-change ${product.flags.includes('growth') ? 'is-growth' : product.flags.includes('decline') ? 'is-decline' : ''}`}>{changeLabel(product)}</span>
    {c?.status === 'available' && c.current_quantity !== 0 && <span className="sales-product-neutral">{c.kind === 'week' ? '这7天' : '本月'} {number(c.current_quantity!)} / {c.kind === 'week' ? '前7天' : '上月'} {number(c.previous_quantity!)}</span>}
    <span className={product.anomalies.length ? 'sales-product-alert' : 'sales-product-neutral'}>{product.anomaly_check?.message ?? '旧报告未记录异常检查情况'}</span>
  </div>
}
