export type CoverageInput = {
  month: string; kinds: string[]; complete: boolean; start: string; end: string; missing: string
}

function day(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const valueMs = Date.parse(`${value}T00:00:00Z`)
  return Number.isFinite(valueMs) && new Date(valueMs).toISOString().slice(0, 10) === value ? valueMs : null
}

export function coverageReadiness(input: CoverageInput) {
  const kinds = new Set(input.kinds)
  if (!kinds.size) return {summary: '请先选择表格并确认字段。', forecast: '待确认数据', anomaly: '待确认数据'}
  if (kinds.size > 1) return {summary: '明细、日汇总和月汇总应分别生成月报。', forecast: '请分开选择表格', anomaly: '请分开选择表格'}
  if (kinds.has('monthly_summary')) return {summary: '可查看月度汇总和商品表现；完整月份之间可作比较。', forecast: '月汇总不支持日级预测', anomaly: '月汇总不支持每日异常'}
  if (!input.complete) return {summary: '可按已提供的记录生成月报；没有记录的日期保留未知。', forecast: '还需确认完整记录范围', anomaly: '还需确认完整记录范围'}
  const start = day(input.start), end = day(input.end), monthStart = day(`${input.month}-01`)
  if (start === null || end === null || end < start || monthStart === null) return {summary: '请填写有效的记录起止日期及分析月份。', forecast: '等待日期范围', anomaly: '等待日期范围'}
  const monthDate = new Date(monthStart)
  const monthEnd = Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth() + 1, 0)
  if (start > monthStart || end < monthEnd) return {summary: '当前范围未覆盖完整分析月份，只统计所填范围内的记录。', forecast: '还需覆盖完整分析月份', anomaly: '还需覆盖完整分析月份'}
  const span = Math.floor((monthEnd - start) / 86400000) + 1
  const missing = input.missing.split(',').map(s => s.trim()).filter(Boolean)
  if (missing.some(d => day(d) === null)) return {summary: '缺失日期请按 YYYY-MM-DD 填写，多个日期用英文逗号分隔。', forecast: '请核对缺失日期', anomaly: '请核对缺失日期'}
  const recentMissing = missing.some(d => { const value = day(d)!; return value <= monthEnd && value >= monthEnd - 89 * 86400000 })
  return {
    summary: `本月及此前已确认 ${span} 天记录范围。仅统计所填范围内的记录，列出的缺失日仍保留未知。`,
    forecast: span < 90 ? `至少需 90 天日记录，当前范围 ${span} 天` : recentMissing ? '近 90 天有缺失，预测可能不可用' : '日期条件具备，将检查成交历史与预测误差',
    anomaly: span < 56 ? `至少需 56 天日记录，当前范围 ${span} 天` : '将按可用的历史记录检查异常变化',
  }
}
