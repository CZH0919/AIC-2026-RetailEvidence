import { useEffect, useRef } from 'react'

export function SalesChart({ points, label }: { points: { date: string; value: number | null }[]; label: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    const draw = () => {
      const width = element.getBoundingClientRect().width, height = 210
      element.width = width * devicePixelRatio; element.height = height * devicePixelRatio
      const ctx = element.getContext('2d')
      if (!ctx) return
      ctx.scale(devicePixelRatio, devicePixelRatio); ctx.clearRect(0, 0, width, height)
      const left = 55, right = width - 15, top = 15, bottom = 175
      const maximum = Math.max(1, ...points.map(p => p.value ?? 0)) * 1.1
      ctx.font = '11px system-ui'; ctx.fillStyle = '#687773'
      for (let i = 0; i <= 4; i++) {
        const y = bottom - (bottom - top) * i / 4
        ctx.strokeStyle = '#e8edeb'; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke()
        ctx.textAlign = 'right'; ctx.fillText((maximum * i / 4).toLocaleString('zh-CN', { maximumFractionDigits: 0 }), left - 9, y + 4)
      }
      ctx.strokeStyle = '#147e6e'; ctx.lineWidth = 2
      let active = false
      ctx.beginPath()
      points.forEach((p, i) => {
        if (p.value === null) { active = false; return }
        const x = left + (right - left) * i / Math.max(1, points.length - 1), y = bottom - (bottom - top) * p.value / maximum
        if (active) ctx.lineTo(x, y); else ctx.moveTo(x, y)
        active = true
      }); ctx.stroke()
      points.forEach((p, i) => {
        if (p.value === null) return
        const x = left + (right - left) * i / Math.max(1, points.length - 1), y = bottom - (bottom - top) * p.value / maximum
        ctx.fillStyle = '#147e6e'; ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2); ctx.fill()
      })
      ctx.fillStyle = '#687773'; ctx.textAlign = 'center'
      const count = Math.max(1, points.length - 1)
      const step = Math.max(7, Math.ceil(45 * count / Math.max(1, right - left)))
      points.forEach((p, i) => {
        if (i === 0 || i === points.length - 1 || (i % step === 0 && (count - i) * (right - left) / count >= 40)) {
          ctx.fillText(p.date.slice(5), left + (right - left) * i / count, 198)
        }
      })
    }
    const observer = new ResizeObserver(draw); observer.observe(element); draw()
    return () => observer.disconnect()
  }, [points])
  return <figure className="sales-chart"><canvas ref={canvas} role="img" aria-label={label} /><details><summary>查看图表数据</summary><div className="sales-chart-data">{points.map(p => <span key={p.date}>{p.date}：{p.value === null ? '记录未确认' : p.value.toLocaleString()}</span>)}</div></details></figure>
}
