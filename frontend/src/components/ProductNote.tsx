import { useEffect, useState } from 'react'
import { Alert, App, Button, Input, Select } from 'antd'
import { SaveOutlined } from '@ant-design/icons'
import { salesApi } from '../retail'
import type { SavedRecord } from '../retail'

const reasons = [
  { value: 'unknown', label: '尚不清楚' },
  { value: 'closed', label: '停业' },
  { value: 'stockout', label: '缺货' },
  { value: 'promotion', label: '促销' },
  { value: 'entry_error', label: '录入错误' },
  { value: 'other', label: '其他' },
]

export function ProductNote({ projectId, runId, itemId, dates }: {
  projectId: string; runId: string; itemId: string; dates: string[]
}) {
  const [day, setDay] = useState<string | null>(null)
  const [reason, setReason] = useState('unknown')
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState<SavedRecord | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { message } = App.useApp()

  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    salesApi.records(projectId, runId).then(response => {
      if (!active) return
      const record = Object.values(response.items).find(r => r.value.source === 'user_note'
        && r.value.item_id === itemId && r.value.day === day) ?? null
      setSaved(record); setReason(record?.value.reason ?? 'unknown'); setNote(record?.value.note ?? '')
    }).catch(issue => { if (active) setError(issue.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [projectId, runId, itemId, day])

  async function save() {
    setBusy(true); setError('')
    try {
      const record = await salesApi.itemNote(projectId, runId, {
        item_id: itemId, day, reason, note, expected_revision: saved?.revision ?? 0,
      })
      setSaved(record); void message.success('已保存核对记录')
    } catch (issue) { setError((issue as Error).message) }
    finally { setBusy(false) }
  }

  return <section className="sales-detail-section sales-product-note">
    <h3>记下核对结果</h3>
    <div className="sales-filter">
      <Select aria-label="核对记录日期" value={day ?? 'month'} disabled={busy || loading}
        onChange={value => setDay(value === 'month' ? null : value)}
        options={[{ value:'month', label:'本月整体' }, ...dates.map(value => ({value,label:value}))]} />
      <Select aria-label="店主确认的原因" value={reason} onChange={setReason}
        disabled={busy || loading} options={reasons} />
    </div>
    <Input.TextArea aria-label="商品核对备注" value={note} onChange={e => setNote(e.target.value)}
      maxLength={500} rows={3} disabled={busy || loading} placeholder="写下你查到的情况" />
    {error && <Alert type="error" title={error} showIcon />}
    <Button icon={<SaveOutlined />} loading={busy} disabled={loading || !!error}
      className="sales-ask" onClick={() => void save()}>保存核对记录</Button>
    <p className="sales-caveat">店主记录，不改变这份月报的统计或预测。</p>
  </section>
}
