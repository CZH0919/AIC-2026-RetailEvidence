import test from 'node:test'
import assert from 'node:assert/strict'
import { AsyncScope } from '../frontend/src/asyncScope.ts'
import { ApiError, request } from '../frontend/src/api.ts'

const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('an unchanged report accepts its own delayed response', async () => {
  const scope = new AsyncScope(); scope.select('report-A')
  const current = scope.capture(), request = deferred()
  const result = request.promise.then(value => current() ? value : null)
  scope.select('report-A'); request.resolve({ amount: 66434.4 })
  assert.deepEqual(await result, { amount: 66434.4 })
})

test('A → B → A never revives an older response', async () => {
  const scope = new AsyncScope(); scope.select('report-A')
  const current = scope.capture(), request = deferred()
  const result = request.promise.then(value => current() ? value : null)
  scope.select('report-B'); scope.select('report-A'); request.resolve('old answer')
  assert.equal(await result, null)
  assert.equal(scope.capture()(), true)
})

test('changing settings invalidates in-flight checks even before polling cleanup', async () => {
  const scope = new AsyncScope(); scope.select('month=2026-09;confirmed=true')
  const current = scope.capture(), request = deferred()
  const result = request.promise.then(value => current() ? value : null)
  scope.select('month=2026-08;confirmed=true'); request.resolve('September check')
  assert.equal(await result, null)
})

test('switching product cancels product responses without cancelling report responses', () => {
  const run = new AsyncScope(), product = new AsyncScope()
  run.select('report-A'); product.select('report-A/product-1')
  const reportResponse = run.capture(), productResponse = product.capture()
  product.select('report-A/product-2')
  assert.equal(reportResponse(), true)
  assert.equal(productResponse(), false)
})

test('unmount and subsequent activation do not revive stale responses', () => {
  const scope = new AsyncScope(); scope.select('A'); const old = scope.capture()
  scope.dispose(); assert.equal(old(), false)
  scope.activate(); assert.equal(old(), false); assert.equal(scope.capture()(), true)
})

test('session check distinguishes an expired session from a temporary server failure', async () => {
  const originalFetch = globalThis.fetch
  try {
    for (const status of [401, 500]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: 'request_error', message: '测试状态' } }), { status, headers: { 'Content-Type': 'application/json' } })
      await assert.rejects(request('/auth/me'), error => error instanceof ApiError && error.status === status)
    }
  } finally { globalThis.fetch = originalFetch }
})

test('an offline session check remains a transport error, not an expired-session response', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => { throw new TypeError('offline') }
    await assert.rejects(request('/auth/me'), error => error instanceof ApiError && error.status === undefined && error.code === 'network_error')
  } finally { globalThis.fetch = originalFetch }
})

test('each stock input and its confirmation invalidates a delayed calculation', async () => {
  const original = { available: 10, incoming: 7, arrival_date: '2026-10-02', reserve: 3, pack_size: 6, confirmed: true }
  const edits = { available: 11, incoming: 8, arrival_date: '2026-10-03', reserve: 4, pack_size: 12, confirmed: false }
  for (const [field, value] of Object.entries(edits)) {
    const scope = new AsyncScope(); scope.select(JSON.stringify(['run-A', 'item-1', true, original]))
    const current = scope.capture(), pending = deferred()
    const result = pending.promise.then(result => current() ? result : null)
    scope.select(JSON.stringify(['run-A', 'item-1', true, { ...original, [field]: value }]))
    pending.resolve({ suggested_quantity: 168 })
    assert.equal(await result, null, field)
  }
})

test('reopening the report settings does not revive a pending create response', async () => {
  const scope = new AsyncScope(); scope.select('open:2026-09')
  const current = scope.capture(), pending = deferred()
  let navigateTo = null
  const finish = pending.promise.then(run => { if (current()) navigateTo = run.id })
  scope.select('closed:2026-09'); scope.select('open:2026-09')
  pending.resolve({ id: 'created-from-old-settings' }); await finish
  assert.equal(navigateTo, null)
})
