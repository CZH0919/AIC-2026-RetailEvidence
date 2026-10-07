import { request } from './api'
import type { Mapping } from './data'

export type CleaningConfig = { trim_identifiers: boolean; duplicates: 'keep' | 'drop_exact'; monetary_subset: 'all_customers' | 'complete_customers'; accept_selected_amount_source: boolean }
export type DataScope = { date_start: string | null; date_end: string | null; countries: string[]; item_ids: string[]; currency: string | null }
export type Capability = { allowed: boolean; state: string; reasons: string[] }
export type ViewCounts = { included_rows: number; excluded_rows: number; primary_reasons: Record<string, number> }
export type QualityReport = {
  context: { mapping_revision: number; policy_id: string; run_id: string; data_version_id: string }
  raw_rows: number; unique_source_orders: number; duplicate_candidates: number
  views: Record<string, ViewCounts>; capabilities: Record<string, Capability>; warnings: string[]
  summary: { rf_customers: number; rfm_customers: number; rf_orders: number; rfm_orders: number; amount_orders: number; complete_baskets: number; incomplete_baskets: number; unique_items: number; currencies: string[]; singleton_baskets: number; time_span_days: number }
  reason_labels: Record<string, string>; exclusion_samples: Record<string, unknown>[]; scope: DataScope; policy: CleaningConfig; mapping: Mapping
}
export type QualityRun = {
  id: string; dataset_version_id: string; policy_id: string; status: string; phase: string; progress: number; message: string
  created_at: string; started_at: string | null; finished_at: string | null; error_code: string | null; peak_rss_bytes: number
  parameters?: { scope: DataScope }; result?: QualityReport | null; events?: { status: string; message: string; created_at: string }[]
}
export type Policy = { id: string; number: number; mapping_revision: number; config: CleaningConfig }
export const cleanDefaults: CleaningConfig = { trim_identifiers: true, duplicates: 'keep', monetary_subset: 'all_customers', accept_selected_amount_source: false }
export const scopeDefaults: DataScope = { date_start: null, date_end: null, countries: [], item_ids: [], currency: null }
export const finished = new Set(['succeeded', 'completed_with_warnings', 'not_applicable', 'failed', 'cancelled', 'resource_limited', 'interrupted'])
export const stateLabel: Record<string, string> = { queued: '等待处理', running: '正在检查', succeeded: '检查完成', completed_with_warnings: '完成 · 有提示', not_applicable: '完成 · 条件不足', failed: '处理未完成', cancelled: '已取消', resource_limited: '达到处理上限', interrupted: '处理已中断' }
export const viewLabels: Record<string, string> = { common: '有效正向记录', rf: '客户频次与时间', rfm: '客户频次、时间与金额', amount: '有效金额', association: '完整购物篮' }
const root = (project: string) => `/projects/${encodeURIComponent(project)}`
export const qualityApi = {
  policies: (p: string, version: string) => request<{ items: Policy[] }>(`${root(p)}/versions/${version}/policies`),
  policy: (p: string, version: string, mappingRevision: number, config: CleaningConfig) => request<Policy>(`${root(p)}/versions/${version}/policies`, { method: 'POST', body: JSON.stringify({ mapping_revision: mappingRevision, config }) }),
  submit: (p: string, version: string, policy: string, scope: DataScope, key: string) => request<QualityRun>(`${root(p)}/runs`, { method: 'POST', body: JSON.stringify({ dataset_version_id: version, policy_id: policy, scope, idempotency_key: key }) }),
  runs: (p: string, version: string) => request<{ items: QualityRun[] }>(`${root(p)}/runs?${new URLSearchParams({ dataset_version_id: version, kind: 'quality' })}`),
  run: (p: string, id: string) => request<QualityRun>(`${root(p)}/runs/${id}`),
  cancel: (p: string, id: string) => request<QualityRun>(`${root(p)}/runs/${id}/cancel`, { method: 'POST' }),
  rows: (p: string, id: string, view: string) => request<{ items: Record<string, unknown>[]; total: number; view: string }>(`${root(p)}/runs/${id}/rows?${new URLSearchParams({ view, limit: '20' })}`),
}
