import { request } from './api'
import type { Mapping } from './data'

export type Prediction = { quantity: number; method: string; validation_mae: number; test_mae?: number | null; test_origins?: number; start: string; end: string; notice: string; range?: {lower: number; upper: number} | null; range_reason?: string }
export type ChangeDriver = {item_id: string; name: string; period: string; amount_change: number | null; quantity_change: number; quantity_effect: number | null; price_effect: number | null}
export type SalesProduct = { id: string; name: string; category: string | null; quantity: number; amount: number | null; change: number | null; flags: string[]; reason: string; daily: { date: string; quantity: number | null }[]; forecast: Prediction | null; forecast_reason?: string; anomalies: { date: string; actual: number; reference: number }[]; item_type?: {kind: string; label: string}; profile?: {labels: string[]; amount_share: number | null; amount_rank: number | null; contribution_band: string | null; weekly_cv: number | null; nonzero_day_share: number | null; complete_weeks: number; first_observed: string; last_observed: string}; contribution?: ChangeDriver | null; focus_reason?: string; anomaly_events?: {start: string; end: string; days: number; actual: number; reference: number; dates: string[]}[] }
export type SalesAction = { id: string; item_id: string; title: string; text: string; reason: string; review: string }
export type SalesParameters = { sources: { version_id: string; mapping_revision: number }[]; month: string; merge_mode: string; duplicates: string; complete_coverage: boolean; coverage_start: string | null; coverage_end: string | null; closed_dates: string[]; missing_dates?: string[]; check_only?: boolean }
export type SalesReport = {
  version?: string; context: { run_id: string }; month: string; available_months: string[]; parameters: SalesParameters;
  change_drivers?: {comparable: boolean; items: ChangeDriver[]; amount_change: number | null; notice: string};
  amount_composition?: Record<string, number> | null;
  summary: { quantity: number; amount: number | null; orders: number | null; products: number; attention_total: number; unit: string; currency: string | null; amount_label: string; complete_month: boolean; average_order: number | null; previous: { quantity: number; amount: number | null } | null };
  chart: { date: string; quantity: number | null; amount: number | null }[]; previous_chart?: { date: string; quantity: number | null; amount: number | null }[]; products: SalesProduct[];
  highlights: string[]; attention_ids: string[]; actions: SalesAction[]; notices: string[];
  quality: { input_rows: number; included_rows: number; excluded_rows: number; duplicate_candidates: number; reasons: { code: string; label: string; count: number }[] };
  sources: { version_id: string; filename: string; mapping_revision: number; canonical_sha256: string }[];
  forecast: { status: string; reason: string; selected_method?: string; tested_items?: number; published_items?: number; metrics: { method: string; split: string; mae: number | null; wape: number | null; samples: number }[] };
  anomaly: { status: string; reason: string; flagged_samples?: number; tested_samples?: number; warning?: string };
}
export type SalesRun = { id: string; status: string; message: string; created_at: string; finished_at: string | null; result: SalesReport | null; parameters?: { sales: SalesParameters } }
export type SourceInfo = { version_id: string; mapping_revision: number; start: string | null; end: string | null; months: string[]; suggested_month: string | null; mapping: Mapping }
export type SavedRecord = { value: { status?: string; note?: string; suggested_quantity?: number; notice?: string; item_id?: string; day?: string | null; reason?: string; source?: string }; revision: number; updated_at: string }
export type SourceRecords = { date: string; count: number; shown: number; items: { source_row_id: string; version_id: string; filename: string; quantity: string | null; line_amount: string | null; unit_price: string | null; event_time: string | null; reason: string }[] }
const root = (p: string) => `/projects/${encodeURIComponent(p)}`
export const salesApi = {
  list: (p: string) => request<{ items: SalesRun[] }>(`${root(p)}/runs?kind=sales&limit=100`),
  run: (p: string, id: string) => request<SalesRun>(`${root(p)}/runs/${id}`, undefined, 120000),
  source: (p: string, id: string) => request<SourceInfo>(`${root(p)}/sales/sources/${id}`, undefined, 120000),
  create: (p: string, params: SalesParameters) => request<SalesRun>(`${root(p)}/sales/runs`, { method: 'POST', body: JSON.stringify({ ...params, idempotency_key: crypto.randomUUID() }) }),
  cancel: (p: string, id: string) => request(`${root(p)}/runs/${id}/cancel`, { method: 'POST' }),
  records: (p: string, id: string) => request<{ items: Record<string, SavedRecord> }>(`${root(p)}/sales/runs/${id}/records`),
  itemRecords: (p: string, id: string, item_id: string, day: string) => request<SourceRecords>(`${root(p)}/sales/runs/${id}/item-records?${new URLSearchParams({ item_id, day })}`, undefined, 120000),
  action: (p: string, id: string, action: string, status: string, note: string, revision: number) => request<SavedRecord>(`${root(p)}/sales/runs/${id}/actions/${encodeURIComponent(action)}`, { method: 'PUT', body: JSON.stringify({ status, note, expected_revision: revision }) }),
  itemNote: (p: string, id: string, data: {item_id: string; day: string | null; reason: string; note: string; expected_revision: number}) => request<SavedRecord>(`${root(p)}/sales/runs/${id}/item-notes`, {method:'PUT', body:JSON.stringify(data)}),
  inventory: (p: string, id: string, data: unknown) => request<SavedRecord>(`${root(p)}/sales/runs/${id}/inventory`, { method: 'POST', body: JSON.stringify(data) }),
  ask: (p: string, id: string, question: string, item_id: string | null) => request<{ answer: string; ai_used: boolean; references?: string[]; run_id: string }>(`${root(p)}/sales/runs/${id}/ask`, { method: 'POST', body: JSON.stringify({ question, item_id }) }, 60000),
  download: (p: string, id: string, file: string) => `/api${root(p)}/sales/runs/${id}/files/${file}`,
  report: (p: string, id: string, all: boolean) => `/api${root(p)}/sales/runs/${id}/report?all_attention=${all}`,
}
