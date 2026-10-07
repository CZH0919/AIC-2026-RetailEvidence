import { request } from './api'

export type Column = { key: string; name: string; missing: number; examples: string[] }
export type Preview = { row_count: number; blank_rows_skipped: number; columns: Column[]; rows: Record<string, string | null>[]; suggestions: { columns: Record<string, string>; warnings: string[] } }
export type ParseOptions = { encoding: string; delimiter: string; sheets: string[]; shape: string; basket_column: string | null; item_separator: string }
export type Mapping = { columns: Record<string, string | null>; order_boundary: string; amount_mode: string; currency_constant: string | null; quantity_unit: string; time_format: string | null; timezone: string | null; status_rule: string; status_values: Record<string, string>; confirmed: boolean }
export type MappingVersion = { id: string; revision: number; config: Mapping; created_at: string; validation: { warnings: string[] } }
export type Draft = { id: string; filename: string; suffix: string; bytes: number; preview_token: string | null; inspection: { sheets: string[] }; options: ParseOptions | null; preview: Preview | null; mapping_draft: Mapping | null; source_dataset: string | null }
export type Version = { id: string; number: number; filename: string; sha256: string; bytes: number; row_count: number; mapping_revision: number; source_dataset: string | null; created_at: string }
export type VersionDetail = Version & { options: ParseOptions; preview: Preview; mapping: MappingVersion }
export type PublicDataset = { id: string; title: string; bytes: number; source_url: string; license: string }

const base = (p: string) => `/projects/${encodeURIComponent(p)}`
const post = (body: unknown) => ({ method: 'POST', body: JSON.stringify(body) })
export const dataApi = {
  versions: (p: string) => request<{ items: Version[] }>(`${base(p)}/versions`),
  version: (p: string, v: string) => request<VersionDetail>(`${base(p)}/versions/${v}`),
  drafts: (p: string) => request<{ items: Draft[] }>(`${base(p)}/imports`),
  catalog: () => request<{ items: PublicDataset[] }>('/public-datasets'),
  upload: (p: string, file: File) => request<Draft>(`${base(p)}/imports?${new URLSearchParams({ filename: file.name })}`, { method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' } }, 660000),
  publicImport: (p: string, id: string) => request<Draft>(`${base(p)}/imports/public/${id}`, post({}), 660000),
  preview: (p: string, d: string, options: ParseOptions) => request<Draft>(`${base(p)}/imports/${d}/preview`, post(options), 660000),
  saveDraft: (p: string, d: Draft, mapping: Mapping) => request<Draft>(`${base(p)}/imports/${d.id}/mapping-draft`, { method: 'PUT', body: JSON.stringify({ preview_token: d.preview_token, mapping }) }),
  discard: (p: string, d: string) => request(`${base(p)}/imports/${d}`, { method: 'DELETE' }),
  confirm: (p: string, d: Draft, mapping: Mapping) => request<VersionDetail>(`${base(p)}/imports/${d.id}/confirm`, post({ preview_token: d.preview_token, mapping }), 660000),
  history: (p: string, v: string) => request<{ items: MappingVersion[] }>(`${base(p)}/versions/${v}/mappings`),
  revise: (p: string, v: VersionDetail, mapping: Mapping) => request<MappingVersion>(`${base(p)}/versions/${v.id}/mappings`, post({ expected_revision: v.mapping.revision, mapping }), 660000),
}
export const parseDefaults: ParseOptions = { encoding: 'utf-8-sig', delimiter: ',', sheets: [], shape: 'transactions', basket_column: null, item_separator: '|' }
export function initialMapping(draft: Draft): Mapping {
  const source = draft.source_dataset
  const columns = draft.preview?.suggestions.columns ?? {}
  const retail = source === 'online_retail' || source === 'online_retail_ii'
  // The Retail II source uses Price, whose meaning is only supplied by its source notice.
  const price = draft.preview?.columns.find(c => c.name === 'Price')
  return draft.mapping_draft ?? { columns: retail && price ? { ...columns, unit_price: price.key } : columns,
    order_boundary: draft.options?.shape === 'basket_list' ? 'row_basket' : source === 'groceries' ? 'basket_id' : columns.order_id ? 'order_id' : 'unavailable',
    amount_mode: retail ? 'quantity_unit_price' : 'none', currency_constant: retail ? 'GBP' : null,
    quantity_unit: retail ? '原始商品单位' : '', time_format: retail ? 'iso8601' : null, timezone: retail ? 'Europe/London' : null,
    status_rule: retail ? 'uci_cancel_prefix' : source === 'groceries' ? 'all_forward' : 'unspecified', status_values: {}, confirmed: false }
}
