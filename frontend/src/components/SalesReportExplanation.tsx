import { Button, Table } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import type { SalesReport } from '../retail'

const number = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
const methods: Record<string, string> = {
  gradient_boosting: '梯度提升树（HistGradientBoosting）',
  last_week: '上一周销量',
  four_week_mean: '过去四周平均销量',
  exponential_smoothing: '近期销量平滑参考', croston_sba: '间歇成交参考', selected_policy: '本次采用的销量参考',
}
const reasons: Record<string, string> = {
  cancelled: '已取消的销售', returned: '退货记录', unknown_status: '未确认是否成交',
  invalid_quantity: '销量为空或填写有误', missing_item: '没有商品名称或编号',
  invalid_time: '日期为空或格式有误', duplicate_removed: '按所选规则删除的重复记录',
  replaced_range: '已用新上传的记录替换', outside_scope: '不在本次分析日期范围内',
  order_conflict: '同一订单的日期、客户或币种不一致',
}

function unavailableReason(report: SalesReport, kind: 'forecast' | 'anomaly') {
  if (report.parameters.check_only) return '本次只检查了销售记录，还没有运行这项分析。'
  if (!report.summary.complete_month || !report.parameters.complete_coverage) {
    return '还未确认这个月的每日记录是否齐全，暂时不能分析。'
  }
  const reason = report[kind].reason
  if (reason.includes('90 天')) return '需要至少 90 天的完整每日销售记录，并且商品有足够的成交记录。'
  if (reason.includes('56 天')) return '需要至少 56 天的完整每日销售记录，并且商品有足够的历史成交记录。'
  if (reason.includes('样本不足')) return '可用来检查预测误差的历史记录太少，暂时没有预测结果。'
  return reason || '本次没有生成这项分析结果。'
}

export function SalesReportExplanation({ report, onDownload }: {
  report: SalesReport; onDownload: (file: string) => void;
}) {
  // The report generator leaves the daily chart empty only for monthly summaries.
  const monthly = report.chart.length === 0 && report.products.length > 0
  const forecastCount = report.products.filter(product => product.forecast).length
  const anomalyCount = report.products.filter(product => product.anomalies.length > 0).length
  const incompleteDaily = !report.summary.complete_month || !report.parameters.complete_coverage
  const excluded = report.quality.reasons.filter(reason => reason.count > 0)
  const compareMonth = new Date(`${report.month}-01T00:00:00Z`)
  compareMonth.setUTCMonth(compareMonth.getUTCMonth() - 1)
  const previousMonth = compareMonth.toISOString().slice(0, 7)

  return <div className="report-explanation">
    <section>
      <h3>用了哪些数据</h3>
      <p className="report-explanation-month">分析月份：<strong>{report.month}</strong>{report.summary.previous && <> · 对比月份：<strong>{previousMonth}</strong></>}</p>
      <ul className="report-source-list">{report.sources.map(source => <li key={source.version_id}>{source.filename}</li>)}</ul>
      <div className="report-record-counts">
        <div><span>读取记录</span><strong>{number(report.quality.input_rows)}</strong></div>
        <div><span>用于分析</span><strong>{number(report.quality.included_rows)}</strong></div>
        <div><span>未计入</span><strong>{number(report.quality.excluded_rows)}</strong></div>
      </div>
      <p className="report-explanation-muted">这里是所用文件的总条数{report.summary.previous && '，包含历史对比记录'}，不是本月订单数。</p>
      {excluded.length > 0 ? <details className="report-exclusion-details">
        <summary>为什么有 {number(report.quality.excluded_rows)} 条记录未计入</summary>
        <ul>{excluded.map(reason => <li key={reason.code}><span>{reasons[reason.code] ?? reason.label}</span><strong>{number(reason.count)} 条</strong></li>)}</ul>
      </details> : <p className="report-explanation-muted">这些记录全部用于分析，没有排除记录。</p>}
      {report.quality.duplicate_candidates > 0 && report.parameters.duplicates === 'keep' && <p className="report-explanation-muted">有 {number(report.quality.duplicate_candidates)} 条疑似重复记录，本次按所选设置保留并计入。</p>}
    </section>

    <section>
      <h3>销售数字怎么算</h3>
      <dl className="report-calculation-list">
        <div><dt>销量</dt><dd>把本月有效销售记录中的数量相加。</dd></div>
        <div><dt>销售额</dt><dd>{report.summary.amount == null ? '没有足够的金额信息，本次未计算销售额。' : report.summary.amount_label.includes('按单价') ? '每条销量 × 单价，再相加。取消和退货不计入。' : '汇总成交金额，取消和退货不计入。'}</dd></div>
        <div><dt>比上月变化</dt><dd>{report.summary.previous ? '（本月数值 − 上月数值）÷ 上月数值；上月为零时不显示百分比。' : '本次没有上月对比结果。'}</dd></div>
      </dl>
      {!report.summary.complete_month && <p className="report-explanation-muted">本月记录尚未确认齐全，销售数字只反映已提供的记录；没有记录的日期不算作零销量。</p>}
      {report.amount_composition && <details><summary>销售额包含哪些记录</summary><p>实物商品：{number(report.amount_composition.physical)}；费用或服务：{number(report.amount_composition.fee_service)}；记账项目：{number(report.amount_composition.accounting)}；类型待确认：{number(report.amount_composition.unknown)} {report.summary.currency}。费用或记账金额保留在已确认的销售口径中，不用于实物备货计算。</p></details>}
    </section>

    <section>
      <h3>预测和异常提醒</h3>
      {monthly ? <div className="report-availability-note">
        <strong>这份表是月汇总</strong>
        <p>只有每月总销量，没有每天的销量，因此不能预测未来七天销量，也不能找出哪一天销量异常。</p>
        <p className="report-explanation-muted">如需这些分析，请上传带销售日期的明细或每日汇总。</p>
      </div> : report.forecast.status !== 'evaluated' && report.anomaly.status !== 'evaluated' && incompleteDaily && !report.parameters.check_only ? <div className="report-availability-note">
        <strong>每日记录还未确认齐全</strong>
        <p>暂时不能预测未来七天销量，也不能检查每日销量异常。</p>
        <p className="report-explanation-muted">请核对是否漏传了销售记录，并确认完整的记录日期范围。</p>
      </div> : <div className="report-analysis-results">
        <div><h4>未来七天销量</h4>
          {report.forecast.status === 'evaluated' ? <><p>{forecastCount > 0 ? `本月商品中，${number(forecastCount)} 款可查看七天销量预测。` : '已检查历史预测误差，暂时没有适合显示预测的商品。'}</p><p className="report-explanation-muted">先用过去的销量试算并比较误差，再估计接下来七天能卖多少。进货数量还需结合库存。</p></> : <p>{unavailableReason(report, 'forecast')}</p>}
        </div>
        <div><h4>销量异常</h4>
          {report.anomaly.status === 'evaluated' ? <><p>{anomalyCount > 0 ? `${number(anomalyCount)} 款商品出现销量异常，商品详情中可查看具体日期和当日销量。` : '已检查，没有发现需要提醒的销量异常。'}</p><p className="report-explanation-muted">比较当天销量和过去的销售情况，找出差别明显的日期，供你核对原因。</p></> : <p>{unavailableReason(report, 'anomaly')}</p>}
        </div>
      </div>}
    </section>

    <details className="report-technical-details">
      <summary>技术详情与下载</summary>
      <div className="report-technical-content">
        <h4>重点商品怎么选</h4>
        <p>{monthly ? '比较本月和上月的商品销量' : '比较月底最后七天和前七天的商品销量'}，变化达到 25% 且数量至少相差 3 {report.summary.unit}时，标为明显增加或减少。重点商品还包括有销量异常提醒的商品{report.change_drivers && '和销售额贡献较高的商品，兼顾变化影响与不同关注事项'}，首页最多展示五款。</p>
        <h4>预测方法与误差</h4>
        {report.forecast.metrics.length > 0 ? <>
          <p>{report.change_drivers ? '按历史成交情况比较不同销量参考，并检查最后几个时间段的表现。' : '对比梯度提升树、上一周销量、过去四周平均销量。'}本次主要采用：{methods[report.forecast.selected_method ?? ''] ?? report.forecast.selected_method ?? '未选择'}。</p>
          <p>用过去的数据检查七天总销量预测误差。MAE 是平均相差的销量；WAPE 是绝对误差总和除以实际销量总和，越小越好。</p>
          {report.forecast.test_used_for_selection === false && <p>先在较早的验证期确定方法和回退规则，再用最后三个时间段评价固定方案；检验结果不会反过来改变方法选择。</p>}
          <Table size="small" rowKey={row => row.method + row.split} pagination={false} dataSource={report.forecast.metrics} scroll={{ x: 560 }} columns={[
            { title: '方法', dataIndex: 'method', render: (value: string) => methods[value] ?? value },
            { title: '数据用途', dataIndex: 'split', render: (value: string) => value === 'test' ? '检验结果' : '选择方法' },
            { title: 'MAE', dataIndex: 'mae', render: number },
            { title: 'WAPE', dataIndex: 'wape', render: (value: number | null) => value == null ? '—' : `${(value * 100).toFixed(1)}%` },
          ]} />
        </> : <p>本次没有预测检验结果。</p>}
        {report.anomaly.status === 'evaluated' && <><h4>异常提醒依据</h4><p>{report.change_drivers ? '比较此前相同星期的实际销量，保留偏离明显的日期，将连续日期归为一次核对事项；不判断缺货或活动原因。' : 'Isolation Forest（孤立森林），结合当天销量、过去七天平均销量和过去二十八天波动，并筛选出变化幅度明显的记录。'}</p></>}
        <h4>文件与字段设置</h4>
        <ul className="report-source-list">{report.sources.map(source => <li key={source.version_id}>{source.filename} · 字段设置第 {source.mapping_revision} 版</li>)}</ul>
        <div className="sales-evidence-downloads">
          {[
            ['sales_row_audit.csv', '每条记录的处理结果'],
            ...(report.forecast.metrics.length > 0 ? [['sales_backtests.csv', '历史预测检验记录']] : []),
            ['sales_report.json', '完整计算结果'], ['manifest.json', '版本与参数'],
          ].map(([file, label]) => <Button key={file} icon={<DownloadOutlined />} onClick={() => onDownload(file)}>{label}</Button>)}
        </div>
      </div>
    </details>
  </div>
}
