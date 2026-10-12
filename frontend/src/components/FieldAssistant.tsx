import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Input } from 'antd'
import { dataApi } from '../data'
import { assistantModeLabel } from '../productCopy'
import type { Draft, FieldExplanation, Mapping } from '../data'

export function FieldAssistant({ projectId, draft, value, onChange }: { projectId: string; draft: Draft; value: Mapping; onChange: (v: Mapping) => void }) {
  const [question, setQuestion] = useState('请解释商品标识、数量和金额字段，以及哪些业务口径仍需我确认。')
  const [answer, setAnswer] = useState<FieldExplanation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const ask = async () => {
    setBusy(true); setError(''); setAnswer(null)
    try {
      const result = await dataApi.explainFields(projectId, draft, question)
      if (active.current && result.preview_token === draft.preview_token) setAnswer(result)
    } catch { if (active.current) setError('字段解释暂不可用，请继续人工核对预览。') }
    finally { if (active.current) setBusy(false) }
  }
  return <section aria-label="字段理解助手" className="editor-intro">
    <h3>需要帮助理解字段吗？</h3><p>AI 帮你理解列名建议，只使用列名和问题，不发送原始明细；字段含义仍需你确认。</p>
    <Input aria-label="字段问题" maxLength={400} value={question} onChange={e => setQuestion(e.target.value)} />
    <Button loading={busy} disabled={!question.trim()} onClick={() => void ask()}>请 AI 解释字段</Button>
    {error && <Alert type="warning" title={error} />}
    {answer && <><Alert type={answer.ai_used ? 'info' : 'warning'} title={answer.ai_used ? 'AI 辅助字段解释' : assistantModeLabel(false, answer.mode)} description={answer.answer} />
      <p>{answer.notice}</p><Button disabled={!answer.ai_used} onClick={() => onChange({ ...value, columns: { ...value.columns, ...answer.proposal.columns }, currency_constant: answer.proposal.columns.currency ? null : value.currency_constant, confirmed: false })}>使用列名建议（仍需确认）</Button></>}
  </section>
}
