import { Alert, Button, Drawer, Select, Table, Tag } from 'antd'
import type { SalesRun } from '../retail'
import type { Version } from '../data'
import { monthLabel, monthlyReports, reportMonth, reportReady } from '../reportSelection'
import { stateLabel } from '../quality'

export function ReportPicker({runs, current, disabled, onChoose}: {runs: SalesRun[]; current: SalesRun | null; disabled: boolean; onChoose: (id: string) => void}) {
  const groups = monthlyReports(runs)
  if (!groups.length) return null
  return <label className="report-month-picker"><span>销售月份</span><Select aria-label="销售月份" disabled={disabled} value={current ? reportMonth(current) : undefined}
    style={{width: 175}} options={groups.map(g => ({value: g.month, label: monthLabel(g.month)}))}
    onChange={month => { const latest = groups.find(g => g.month === month)?.reports[0]; if (latest) onChoose(latest.id) }} /></label>
}

export function HistoricalReportNotice({runs, current, onChoose, disabled}: {runs: SalesRun[]; current: SalesRun | null; onChoose: (id: string) => void; disabled: boolean}) {
  const latest = current && monthlyReports(runs).find(g => g.month === reportMonth(current))?.reports[0]
  if (!current?.result || !latest || latest.id === current.id) return null
  return <Alert className="report-history-notice" type="info" showIcon title="正在查看历史报告"
    description={`${monthLabel(reportMonth(current))} · ${new Date(current.finished_at ?? current.created_at).toLocaleString('zh-CN')} 生成`}
    action={<Button disabled={disabled} onClick={() => onChoose(latest.id)}>返回该月最新报告</Button>} />
}

export function ReportHistory({open, onClose, runs, current, versions, onChoose, disabled}: {open: boolean; onClose: () => void; runs: SalesRun[]; current: SalesRun | null; versions: Version[]; onChoose: (id: string) => void; disabled: boolean}) {
  const latest = new Set(monthlyReports(runs).map(g => g.reports[0].id))
  return <Drawer title="历史报告" open={open} onClose={onClose} width={800}>
    <p className="report-history-intro">每个月默认显示最新生成成功的报告。这里保留此前的报告和生成记录。</p>
    <Table rowKey="id" size="small" dataSource={runs} pagination={{pageSize: 8, showSizeChanger: false}} scroll={{x: 640}} columns={[
      {title: '销售月份', width: 135, render: (_: unknown, r: SalesRun) => monthLabel(reportMonth(r))},
      {title: '生成时间', width: 175, render: (_: unknown, r: SalesRun) => new Date(r.finished_at ?? r.created_at).toLocaleString('zh-CN')},
      {title: '使用的销售表', render: (_: unknown, r: SalesRun) => <div className="report-history-files">{r.parameters?.sales.sources?.map(s => <div key={s.version_id}>{versions.find(v => v.id === s.version_id)?.filename ?? '原销售表'}</div>)}</div>},
      {title: '操作', width: 125, render: (_: unknown, r: SalesRun) => !reportReady(r) ? <span>{stateLabel[r.status] ?? r.status}</span> : <div style={{display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4, whiteSpace: 'nowrap'}}>{latest.has(r.id) && <Tag color="green">该月最新</Tag>}{r.id === current?.id ? <span>正在查看</span> : <Button type="link" disabled={disabled} onClick={() => onChoose(r.id)}>查看</Button>}</div>},
    ]} />
  </Drawer>
}
