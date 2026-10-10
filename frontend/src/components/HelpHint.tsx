import { useEffect, useId, useRef, useState } from 'react'
import { Button, Drawer, Grid, Popover } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { helpContent } from '../helpContent'
import type { HelpId } from '../helpContent'
import type { KeyboardEvent } from 'react'

/** Local, deterministic help: never submits the surrounding form or calls AI. */
export function HelpHint({ topic, context }: { topic: HelpId; context?: string }) {
  const info = helpContent[topic]
  const [open, setOpen] = useState(false)
  const screen = Grid.useBreakpoint()
  const drawer = info.drawer || (screen.sm === undefined ? window.innerWidth < 576 : !screen.sm)
  const id = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const closer = useRef<HTMLButtonElement>(null)
  const change = (next: boolean) => {
    setOpen(next)
    if (!next) requestAnimationFrame(() => trigger.current?.focus())
  }
  useEffect(() => {
    if (!open) return
    const timer = setTimeout(() => closer.current?.focus(), 100)
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault(); event.stopPropagation()
        setOpen(false); requestAnimationFrame(() => trigger.current?.focus())
      }
    }
    document.addEventListener('keydown', escape, true)
    return () => { clearTimeout(timer); document.removeEventListener('keydown', escape, true) }
  }, [open, drawer])
  const keys = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); change(false) }
    if (event.key === 'Tab' && !drawer) {
      const buttons = event.currentTarget.querySelectorAll<HTMLElement>('button, a[href], [tabindex="0"]')
      if (!buttons.length) return
      const first = buttons[0], last = buttons[buttons.length - 1]
      if ((event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
        event.preventDefault(); (event.shiftKey ? last : first).focus()
      }
    }
  }
  const content = <section className="help-content" data-help-content={topic} onKeyDownCapture={keys}
    role={drawer ? undefined : 'dialog'} aria-modal={drawer ? undefined : 'false'} aria-labelledby={id + '-title'}>
    <div className="help-content-heading"><h3 id={id + '-title'}>{info.title}</h3>
      <Button ref={closer} htmlType="button" size="small" onClick={() => change(false)} aria-label={`关闭帮助：${info.title}`}>关闭说明</Button></div>
    {context && <p className="help-context">{context}</p>}
    {info.sections.map(section => <section key={section.title}><h4>{section.title}</h4><p>{section.text}</p></section>)}
  </section>
  const button = <Button ref={trigger} htmlType="button" type="text" size="small" className="help-hint"
    data-help-id={topic} aria-label={`查看帮助：${info.title}`} aria-expanded={open} aria-haspopup="dialog" aria-controls={open ? id : undefined}
    icon={<QuestionCircleOutlined aria-hidden="true" />} onKeyDown={event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); event.stopPropagation(); change(!open)
      }
    }} onClick={event => { event.preventDefault(); event.stopPropagation(); if (drawer) change(!open) }}>
    {info.label}</Button>
  return drawer ? <>{button}<Drawer id={id} className="help-drawer" title="操作说明" width={Math.min(560, window.innerWidth)} push={false}
    open={open} onClose={() => change(false)} keyboard={false} maskClosable afterOpenChange={shown => { if (!shown) trigger.current?.focus() }}>
    {content}</Drawer></> : <Popover open={open} trigger="click" placement="bottomLeft" content={<div id={id}>{content}</div>}
    onOpenChange={change} classNames={{ root: 'help-popover' }}>{button}</Popover>
}
