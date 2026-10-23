import type { SalesProduct } from '../retail'

const number = (v: number | null) => v === null ? '—' : v.toLocaleString('zh-CN', {maximumFractionDigits: 2})

export function ProductEvidence({product, currency}: {product: SalesProduct; currency: string | null}) {
  const profile = product.profile, change = product.contribution
  if (!profile) return null
  return <details className="product-detail-disclosure">
    <summary><span>销售表现与变化依据</span><small>{profile.labels.slice(0, 2).join(' · ') || '查看销售记录'}</small></summary>
    <div className="product-detail-content">
      {profile.amount_share !== null && <p>占本月销售额 {(profile.amount_share * 100).toFixed(1)}%，按销售额排名第 {profile.amount_rank}。</p>}
      {!!profile.labels.length && <p>{profile.labels.join('；')}。</p>}
      {profile.nonzero_day_share !== null && <p>有效记录日期中，有 {(profile.nonzero_day_share * 100).toFixed(1)}% 的日期发生销售；周销量统计覆盖 {profile.complete_weeks} 个完整周。</p>}
      <p>最早销售记录：{profile.first_observed}；最近销售记录：{profile.last_observed}。</p>
      {change?.amount_change != null && <p>与上月相比，销售额变化 {number(change.amount_change)} {currency}。{change.period === 'only_current' ? '仅本月观察到销售记录。' : change.period === 'only_previous' ? '仅上月观察到销售记录。' : ''}</p>}
      {change?.quantity_effect != null && <p>按销量与成交均价拆解：数量变化对应 {number(change.quantity_effect)} {currency}，均价变化对应 {number(change.price_effect)} {currency}，两项合计为销售额变化。</p>}
      {product.item_type && <p>{product.item_type.kind === 'unknown' ? '记录类型尚未确认，可通过详情顶部的“确认或调整类型”进行核对。' : `记录类型：${product.item_type.label}。${product.item_type.kind !== 'physical' ? '不用于实物备货计算。' : ''}`}</p>}
    </div>
  </details>
}
