import type { SalesProduct } from './retail'
const number = (value: number) => value.toLocaleString('zh-CN', {maximumFractionDigits: 2})

export function changePercent(change: number): string {
  const value = Math.abs(change * 100)
  // A rounded percentage must never turn remaining sales into zero sales.
  if (change > -1 && change < 0 && value >= 99.95) return '>99.9'
  if (value > 0 && value < .1) return '<0.1'
  return value.toFixed(1).replace(/\.0$/, '')
}

export function changeLabel(product: SalesProduct): string {
  const c = product.comparison
  if (!c) return '旧报告未保存比较详情'
  if (c.status === 'missing_records') return '记录不完整，暂不比较'
  if (c.status === 'closed') return '包含停业日期，暂不比较'
  if (c.status === 'legacy_unknown') return '旧报告未保存完整比较数量'
  const period = c.kind === 'week' ? '月底7天' : '本月'
  if (c.current_quantity != null && c.previous_quantity === 0) return `${period}售出 ${number(c.current_quantity)}，前期为0`
  if (product.change === null) return '记录不足，暂不比较'
  if (c.current_quantity === 0 && (c.previous_quantity ?? 0) > 0) return `${period}售出0，${c.kind === 'week' ? '前7天' : '上月'} ${number(c.previous_quantity!)}`
  if (product.change === 0) return `${period}销量持平`
  return `${period}${product.change > 0 ? '增加' : '减少'} ${changePercent(product.change)}%`
}

