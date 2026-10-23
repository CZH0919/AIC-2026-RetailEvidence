/** Only these two invariant explanations may move into on-demand help.
 * Unrecognized notices remain visible, including new server warnings. */
const backgroundExplanations = new Set([
  '只统计确认的正向销售，取消和退货不自动扣入净收入。',
  '未提供库存和成本，销量变化不代表缺货、积压或利润变化。',
])
export function splitReportNotices(notices: string[]) {
  return {
    explanations: notices.filter(notice => backgroundExplanations.has(notice)),
    warnings: notices.filter(notice => !backgroundExplanations.has(notice)),
  }
}
