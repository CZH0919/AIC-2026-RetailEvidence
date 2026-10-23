/** Product language shared across screens. Stored evidence values stay unchanged. */
export const assistantModeLabel = (used: boolean, mode?: string): string => used ? 'AI 辅助解释' : ({
  clarification: '请补充问题', data_limit: '数据暂不支持', evidence_explanation: '计算依据说明',
  knowledge_explanation: '使用说明', out_of_scope: '问题超出范围',
  inference_timeout: '回答等待超时 · 预设说明', inference_unavailable: '助手暂不可用 · 预设说明',
  rejected_model_output: '解释未通过核对 · 预设说明',
} as Record<string, string>)[mode ?? ''] ?? '预设说明 · 未完成AI回答'
export const timeFormatLabels: Record<string, string> = {
 iso8601: '表格日期 / 标准日期时间', '%Y-%m-%d': '年-月-日', '%Y/%m/%d': '年/月/日',
 '%Y-%m-%d %H:%M:%S': '年-月-日 时:分:秒', '%d/%m/%Y %H:%M': '日/月/年 时:分',
 '%m/%d/%Y %H:%M': '月/日/年 时:分', '%d/%m/%Y': '日/月/年', '%m/%d/%Y': '月/日/年',
}
export const timezoneLabels: Record<string, string> = {
 'Europe/London': '伦敦时间', 'Asia/Shanghai': '中国标准时间', UTC: '世界标准时间（UTC）',
 'America/New_York': '纽约时间', 'Europe/Berlin': '柏林时间', 'Asia/Tokyo': '东京时间',
}
export const qualityCopy = (text: string): string => ({
 '金额不完整客户未进入 RFM 视图，RF 仍保留符合条件的客户。': '缺少购买金额的客户不参与含金额的分群；符合条件时仍可按购买时间与次数分析。',
 '纳入当前有效视图': '用于本项分析',
 '客户分群已完成，请查看群体画像和诊断。': '客户分群已完成，请查看购买习惯与分组质量。',
} as Record<string, string>)[text] ?? text
