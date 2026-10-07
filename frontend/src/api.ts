import type { Project, ProjectInput, ProjectList } from './types'

export class ApiError extends Error {
  code: string
  fields: Record<string, string>
  constructor(message: string, code = 'network_error', fields: Record<string, string> = {}) {
    super(message)
    this.code = code
    this.fields = fields
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('暂时无法连接，请检查连接后重试。')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(body?.error?.message ?? '请求未能完成，请稍后重试。', body?.error?.code, body?.error?.fields)
  }
  if (body === null) throw new ApiError('暂时无法读取内容，请稍后重试。')
  return body as T
}

export const api = {
  list: (q: string, offset: number, signal?: AbortSignal) =>
    request<ProjectList>(`/projects?${new URLSearchParams({ q, offset: String(offset), limit: '12' })}`, { signal }),
  get: (id: string, signal?: AbortSignal) => request<Project>(`/projects/${encodeURIComponent(id)}`, { signal }),
  create: (input: ProjectInput) => request<Project>('/projects', { method: 'POST', body: JSON.stringify(input) }),
  update: (id: string, input: ProjectInput, revision: number) => request<Project>(`/projects/${encodeURIComponent(id)}`, {
    method: 'PATCH', body: JSON.stringify({ ...input, revision }),
  }),
}
