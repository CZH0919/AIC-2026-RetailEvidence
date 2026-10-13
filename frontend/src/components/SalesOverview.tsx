import { Button, Select } from 'antd'
import { MessageOutlined } from '@ant-design/icons'
import type { SalesAction, SalesReport, SavedRecord } from '../retail'
import { SalesChart } from './SalesChart'

const number = (value: number | null) => value === null ? '—' : value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })

function comparison(current: number | null, previous: number | null | undefined) {
  if (current === null || previous == null) return '暂无上月对比'
  if (previous === 0) return '上月为 0'
  const change = (current - previous) / previous * 100
  return change === 0 ? '与上月持平' : `比上月${change > 0 ? '增加' : '减少'} ${Math.abs(change).toFixed(1)}%`
}

export function SalesOverview({ report, chartScope, onChartScope, records, onProduct, onAllProducts, onActionGroup, onActionStatus, onActionNote, onAsk }: {
  report: SalesReport
  chartScope: string
  onChartScope: (scope: string) => void
  records: Record<string, SavedRecord>
  onProduct: (id: string) => void
  onAllProducts: () => void
  onActionGroup: (action: SalesAction) => void
  onActionStatus: (action: SalesAction, status: string) => void
  onActionNote: (action: SalesAction) => void
  onAsk: () => void
}) {
  const { summary } = report
  const amountChart = summary.amount !== null && report.chart.some(point => point.amount !== null)
  const chart = chartScope === 'previous' && report.previous_chart?.length ? report.previous_chart : report.chart
  const highlights = report.highlights.map(id => report.products.find(product => product.id === id)).filter(product => product !== undefined).slice(0, 5)
  const actions = report.actions.slice(0, 3)

  return <div className="sales-overview">
    <section className="overview-metrics" aria-label="本月销售概况">
      <div>
        <span title={summary.amount_label}>销售额</span>
        <strong>{number(summary.amount)}<small>{summary.currency}</small></strong>
        <p>{summary.amount === null ? '表格没有可用金额' : comparison(summary.amount, summary.previous?.amount)}</p>
      </div>
      <div>
        <span>销量</span>
        <strong>{number(summary.quantity)}</strong>
        <p>{comparison(summary.quantity, summary.previous?.quantity)}<small>{summary.unit}</small></p>
      </div>
    </section>

    <section className="overview-trend">
      <div className="overview-section-heading"><h3>销售趋势 <small className="overview-muted">{amountChart ? `销售额 · ${summary.currency ?? ''}` : `销量 · ${summary.unit}`}</small></h3>
        {!!report.previous_chart?.length && <div className="overview-chart-switch" aria-label="比较月份">
          <Button size="small" type={chartScope === 'current' ? 'primary' : 'text'} onClick={() => onChartScope('current')}>本月</Button>
          <Button size="small" type={chartScope === 'previous' ? 'primary' : 'text'} onClick={() => onChartScope('previous')}>上月</Button>
        </div>}
      </div>
      {chart.length ? <SalesChart points={chart.map(point => ({ date: point.date, value: amountChart ? point.amount : point.quantity }))} label={`${chart[0].date.slice(0, 7)} 每日${amountChart ? '销售额' : '销量'}`} /> : <p className="overview-muted">这份表是月汇总，没有每日销售曲线。</p>}
      {!summary.complete_month && <p className="overview-muted">按已导入的销售记录统计。</p>}
      {!!report.change_drivers?.items.length && <details className="overview-action-details"><summary>哪些商品带动了销售额变化</summary>
        {report.change_drivers.items.slice(0, 5).map(item => <p key={item.item_id}><Button type="link" size="small" onClick={() => onProduct(item.item_id)}>{item.name}</Button>：{number(item.amount_change)} {summary.currency}{item.period === 'only_current' ? '（仅本月有记录）' : item.period === 'only_previous' ? '（仅上月有记录）' : ''}</p>)}
        <p className="overview-muted">{report.change_drivers.notice}</p>
      </details>}
    </section>

    <div className="overview-bottom-grid">
      <section className="overview-panel">
        <div className="overview-section-heading"><h3>重点商品</h3><Button type="link" size="small" onClick={onAllProducts}>查看全部</Button></div>
        {highlights.length > 0 && <p className="overview-muted">先看这 {highlights.length} 款，点击商品查看趋势和原因。</p>}
        <ul className="overview-products">
          {highlights.map(product => <li key={product.id}>
            <Button type="link" className="overview-product-name" onClick={() => onProduct(product.id)}>{product.name}</Button>
            <div className="overview-product-stats"><span>销量 <strong>{number(product.quantity)}</strong></span>{product.amount !== null && <span>销售额 <strong>{number(product.amount)}</strong> {summary.currency}</span>}</div>
            <div className="overview-product-hints">
              {!!product.profile && <span>{product.focus_reason}</span>}
              {product.flags.includes('growth') && <span className="overview-positive">{product.daily.length ? '月底' : '本月'}销量增加</span>}
              {product.flags.includes('decline') && <span>{product.daily.length ? '月底' : '本月'}销量减少</span>}
              {product.anomalies.length > 0 && <span>销量异常：{product.anomalies.length} 天</span>}
            </div>
          </li>)}
        </ul>
        {!highlights.length && <p className="overview-muted">本次没有重点提醒，可查看全部商品。</p>}
      </section>

      <section className="overview-panel">
        <div className="overview-section-heading"><h3>接下来先做</h3><span className="overview-muted">{actions.length} 项行动</span></div>
        {actions.map((action, index) => <article className="overview-action" key={action.id}>
          <span className="overview-action-number">{index + 1}</span>
          <div>
            <h4>{action.title}</h4>
            <p>{action.text.replace(/\s*另有.*$/, '')}</p>
            <Button type="link" size="small" onClick={() => onActionGroup(action)}>查看相关记录（{action.related_items?.length ?? 1}）</Button>
            <details className="overview-action-details">
              <summary>依据与处理记录</summary>
              <p>{action.reason}</p><p className="overview-muted">{action.review}</p>
              <div className="sales-action-tools">
                <Select aria-label={`处理状态 ${action.title}`} value={records[`action:${action.id}`]?.value.status ?? 'pending'} style={{ width: 105 }} options={[{ value: 'pending', label: '待处理' }, { value: 'done', label: '已处理' }, { value: 'declined', label: '暂不采用' }]} onChange={status => onActionStatus(action, status)} />
                <Button size="small" onClick={() => onActionNote(action)}>备注</Button>
              </div>
              {records[`action:${action.id}`]?.value.note && <p className="sales-note">{records[`action:${action.id}`].value.note}</p>}
            </details>
          </div>
        </article>)}
        {!actions.length && <p className="overview-muted">本次没有特别行动建议，继续查看销售变化。</p>}
      </section>
    </div>
    <footer className="overview-footer"><Button type="text" icon={<MessageOutlined />} onClick={onAsk}>有疑问？问问销售助手</Button></footer>
  </div>
}
