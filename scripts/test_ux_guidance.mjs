import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { helpContent } from '../frontend/src/helpContent.ts'
const audit = JSON.parse(fs.readFileSync(new URL('../docs/verification/ux_guidance/audit_issues.json', import.meta.url), 'utf8'))
test('Every high-risk audited concept has a unique, contextual help definition', () => {
  assert.equal(Object.keys(helpContent).length, 42)
  for (const issue of audit.filter(x => x.priority === 'P0')) {
    assert(helpContent[issue.id], issue.id)
    assert.equal(helpContent[issue.id].id, issue.id)
    assert(helpContent[issue.id].drawer)
    assert(helpContent[issue.id].sections.some(x => x.title === '没有数据时'))
    assert(helpContent[issue.id].sections.some(x => x.title === '请留意'))
  }
})
test('Short triggers remain discoverable; each definition has a usable example and no raw HTML', () => {
  for (const [id, topic] of Object.entries(helpContent)) {
    assert.equal(topic.id, id)
    assert(topic.label.length <= 10, `${id}: label too long`)
    assert(topic.pages.length > 0)
    assert(topic.sections.find(x => x.title === '例如')?.text.length > 10)
    assert(topic.sections.every(x => x.text.length > 0 && !/[<>]/.test(x.text)))
  }
})
test('Accounting, stock-date and AI unknown-data safeguards are explicitly explained', () => {
  const text = id => helpContent[id].sections.map(x => x.text).join(' ')
  assert.match(text('UX12'), /每单计一次/)
  assert.match(text('UX13'), /不做汇率换算/)
  assert.match(text('UX17'), /两个独立/)
  assert.match(text('UX33'), /不能配上今天/)
  assert.match(text('UX34'), /不确定.*不要/)
  assert.match(text('UX35'), /不保证/)
  assert.match(text('UX37'), /数字由程序/)
  assert.match(text('UX42'), /不证明/)
})
