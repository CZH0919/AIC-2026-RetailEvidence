/** Calendar values stay YYYY-MM-DD strings; never convert picker values through time zones. */
export function calendarDay(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return null
  const ms = Date.parse(`${value}T00:00:00Z`)
  return Number.isFinite(ms) && new Date(ms).toISOString().slice(0, 10) === value ? ms : null
}

export function validMonth(value: string) {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(value) && calendarDay(`${value}-01`) !== null
}

export function monthLastDay(value: string) {
  if (!validMonth(value)) return ''
  const [year, month] = value.split('-').map(Number)
  const days = [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return `${value}-${days[month - 1]}`
}

export function calendarDates(value: string) {
  return [...new Set(value.split(/[,，;；\r\n]+/).map(s => s.trim()).filter(Boolean))]
}

export function dateRangeError(start: string, end: string) {
  if ((start && calendarDay(start) === null) || (end && calendarDay(end) === null)) return '请填写有效日期，格式为 YYYY-MM-DD。'
  if (start && end && start > end) return '开始日期不能晚于截止日期，请核对起止顺序。'
  return null
}

export function coverageError(input: {month: string; complete: boolean; start: string; end: string; missing: string; closed?: string}) {
  if (!validMonth(input.month)) return '请选择有效的分析月份。'
  if (!input.complete) return null
  if (!input.start || !input.end) return '确认记录完整后，请填写完整记录开始日和截止日。'
  const range = dateRangeError(input.start, input.end)
  if (range) return range
  if ((calendarDay(input.end)! - calendarDay(input.start)!) / 86400000 > 1095) return '完整记录范围不能超过 1095 天，请缩小范围。'
  if (input.start > monthLastDay(input.month) || input.end < `${input.month}-01`) return '分析月份与完整记录范围没有交集，请调整月份或记录范围。'
  const missing = calendarDates(input.missing), closed = calendarDates(input.closed ?? '')
  if (missing.length > 1096 || closed.length > 366) return '缺失日期最多 1096 天，停业日期最多 366 天。'
  if ([...missing, ...closed].some(v => calendarDay(v) === null)) return '缺失和停业日期请填写真实的 YYYY-MM-DD 日期，多天可用逗号分隔。'
  if (missing.some(v => closed.includes(v))) return '同一天不能同时标为记录缺失和已确认停业，请核对。'
  return null
}
