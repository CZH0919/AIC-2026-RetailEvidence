import { Button, Spin, Table } from 'antd'
import type { useAutomaticAnalyses } from './useAutomaticAnalyses'

const labels: Record<string, string> = {pending: '等待分析', preparing: '正在整理订单', running: '正在分析', ready: '已完成', no_result: '暂无明显规律', skipped: '数据不足', failed: '未完成'}

export function AutomaticAnalysisStatus({automatic}: {automatic: ReturnType<typeof useAutomaticAnalyses>}) {
  const {data, error, retry} = automatic
  if (!data) return error ? <p className="overview-muted">{error}</p> : null
  const running = data.status !== 'complete'
  const failed = Object.values(data.steps).some(s => s?.status === 'failed')
  return <details className="overview-action-details" style={{margin: '0 0 16px'}}>
    <summary>{running && <Spin size="small" />} 客户分群：{labels[data.steps.customers?.status ?? 'pending']} · 商品搭配：{labels[data.steps.association?.status ?? 'pending']}</summary>
    <p>客户分群：{data.steps.customers?.message}</p>
    <p>商品搭配：{data.steps.association?.message}</p>
    {running && <p className="overview-muted">月报可先查看，其他分析完成后会自动更新。</p>}
    {error && <p className="overview-muted">{error}</p>}
    {!!data.customer_groups?.length && <>
      <h4>客户回访机会</h4>
      <p>{data.customer_evidence?.opportunities?.length
        ? `找到 ${data.customer_evidence.opportunities[0].customers.toLocaleString('zh-CN')} 位过去购买较规律、本次间隔明显变长的客户。回访建议会与其他经营建议一起按价值筛选，出现在“接下来先做”中。`
        : '现有记录没有提供足够明确的回访机会，暂不推荐客户活动。'}</p>
      <details><summary>分组方法与概况</summary>
      <p>按购买次数、距上次购买的天数{data.customer_mode === 'RFM' ? '和累计购买金额' : ''}，用 K-means 把购买习惯相近的客户放在一组。分组用于了解客户差异，回访名单另按每人的实际购买日期筛选。</p>
      <p className="overview-muted">{data.customer_evidence ? `使用 ${data.customer_evidence.history_start} 至 ${data.customer_evidence.through_date} 的销售记录。` : '使用截至本月底已上传的销售记录。'}下表是各组的中位数，表示中间水平，并非每个人都符合的分组门槛。</p>
      <Table size="small" rowKey="cluster" pagination={false} dataSource={data.customer_groups} columns={[
        {title: '分组', dataIndex: 'cluster', render: (n: number) => `第${n + 1}组`},
        {title: '客户人数', dataIndex: 'customers'},
        {title: '购买次数', render: (_, row) => `${row.frequency_median.toLocaleString('zh-CN')}次`},
        {title: '距上次购买', render: (_, row) => `${row.recency_median.toLocaleString('zh-CN')}天`},
        ...(data.customer_mode === 'RFM' ? [{title: '累计购买金额', render: (_: unknown, row: {monetary_median?: number | null}) => row.monetary_median?.toLocaleString('zh-CN') ?? '—'}] : []),
      ]} />
      </details>
    </>}
    {failed && <Button size="small" onClick={retry}>重试未完成的分析</Button>}
  </details>
}
