import { useEffect, useRef, useState } from 'react'
import { Alert, App, Button, Checkbox, Collapse, Input, Progress, Select, Tag } from 'antd'
import { CheckCircleOutlined, ClockCircleOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { ApiError } from '../api'
import { dataApi } from '../data'
import type { MappingVersion, Version } from '../data'
import { cleanDefaults, finished, qualityApi, scopeDefaults, stateLabel } from '../quality'
import type { CleaningConfig, DataScope, QualityReport as Report, QualityRun } from '../quality'
import { formatDate } from '../pages/ProjectLibrary'
import { EmptyState, ErrorState, LoadingState } from './States'
import { QualityReport } from './QualityReport'

export default function QualityWorkspace({ projectId }: { projectId: string }) {
  const [versions, setVersions] = useState<Version[] | null>(null)
  const [version, setVersion] = useState('')
  const [mappings, setMappings] = useState<MappingVersion[]>([])
  const [mapping, setMapping] = useState(1)
  const [config, setConfig] = useState<CleaningConfig>(cleanDefaults)
  const [scope, setScope] = useState<DataScope>(scopeDefaults)
  const [runs, setRuns] = useState<QualityRun[]>([])
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<QualityRun | null>(null)
  const [error, setError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState<string[]>(['settings'])
  const [reload, setReload] = useState(0)
  const submitKey = useRef<string | null>(null)
  const { message } = App.useApp()
  useEffect(() => {
    let active = true
    setError('')
    dataApi.versions(projectId).then(value => {
      if (active) { setVersions(value.items); setVersion(old => old || value.items[0]?.id || '') }
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [projectId, reload])
  useEffect(() => {
    let active = true
    setMappings([]); setSelected(''); setDetail(null); setRuns([])
    if (version) dataApi.history(projectId, version).then(value => {
      if (active) { setMappings(value.items); setMapping(value.items[0]?.revision ?? 1) }
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [projectId, version])
  useEffect(() => { submitKey.current = null }, [version, mapping, config, scope])
  useEffect(() => {
    if (!version) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const refresh = async () => {
      try {
        const [list, current] = await Promise.all([qualityApi.runs(projectId, version), selected ? qualityApi.run(projectId, selected) : Promise.resolve(null)])
        if (!active) return
        setRuns(list.items); setError('')
        if (current) setDetail(current)
        else if (list.items.length) setSelected(list.items[0].id)
      } catch (e) { if (active) setError(e instanceof Error ? e.message : '暂时无法读取处理记录。') }
      if (active) timer = setTimeout(refresh, 1500)
    }
    void refresh()
    return () => { active = false; clearTimeout(timer) }
  }, [projectId, version, selected, reload])
  const submit = async () => {
    setBusy(true); setSubmitError('')
    submitKey.current ??= crypto.randomUUID()
    try {
      const policy = await qualityApi.policy(projectId, version, mapping, config)
      const selectedScope = { ...scope, countries: scope.countries.filter(v => v.trim()), item_ids: scope.item_ids.filter(v => v.trim()) }
      const run = await qualityApi.submit(projectId, version, policy.id, selectedScope, submitKey.current)
      submitKey.current = null; setSelected(run.id); setDetail(run); setExpanded([]); setReload(v => v + 1)
      void message.success('质量检查已提交，可继续查看其他项目')
    } catch (e) {
      const issue = e instanceof ApiError ? e : new ApiError('提交未完成，请重试。')
      if (issue.code !== 'network_error') submitKey.current = null
      setSubmitError(issue.message); void message.error(issue.message)
    } finally { setBusy(false) }
  }
  const restoreSettings = async () => {
    if (!detail?.parameters) return
    setBusy(true); setSubmitError('')
    try {
      const policies = await qualityApi.policies(projectId, detail.dataset_version_id)
      const policy = policies.items.find(value => value.id === detail.policy_id)
      if (!policy) throw new Error('未找到本次清洗策略，请刷新后重试。')
      if (!detail.parameters?.scope) throw new Error('未找到本次范围设置，请刷新后重试。')
      setMapping(policy.mapping_revision); setConfig(policy.config); setScope(detail.parameters.scope)
      setExpanded(['settings']); submitKey.current = null
      void message.success('已载入本次设置，调整后可重新检查')
    } catch (e) { setSubmitError(e instanceof Error ? e.message : '暂时无法读取设置，请重试。') }
    finally { setBusy(false) }
  }
  if (!versions && !error) return <LoadingState />
  if (!versions) return <ErrorState message={error} onRetry={() => setReload(v => v + 1)} />
  if (!versions.length) return <section className="workspace-panel"><EmptyState compact title="先添加一份数据，再检查质量" description="导入并确认字段后，可以查看质量问题和各项分析的适用条件。" action={<Link className="button-link" to={`/projects/${projectId}/data`}>前往导入数据</Link>} /></section>
  const active = detail && !finished.has(detail.status)
  return <div className="quality-workspace">
    <div className="data-heading"><div><span className="eyebrow">DATA QUALITY</span><h2>先确认数据，再相信结论</h2><p>看清记录的去向，明确每项分析可以使用的数据范围。</p></div><Button type="primary" icon={<PlayCircleOutlined />} loading={busy} disabled={!mappings.length} onClick={() => void submit()}>检查数据质量</Button></div>
    {error && <Alert className="import-alert" type="warning" showIcon title={error} />}
    {submitError && <Alert className="import-alert" type="error" showIcon title={submitError} />}
    <section className="workspace-panel quality-settings"><div className="quality-source-select"><label className="data-field"><span>数据版本</span><Select aria-label="质量检查数据版本" value={version} disabled={busy} options={versions.map(v => ({ value: v.id, label: `V${v.number} · ${v.filename}` }))} onChange={setVersion} /></label>
      <label className="data-field"><span>字段版本</span><Select aria-label="质量检查字段版本" value={mapping} disabled={busy} options={mappings.map(m => ({ value: m.revision, label: `M${m.revision} · ${formatDate(m.created_at)}` }))} onChange={setMapping} /></label></div>
      <Collapse activeKey={expanded} onChange={keys => setExpanded(typeof keys === 'string' ? [keys] : keys)} ghost items={[{ key: 'settings', label: '清洗策略与分析范围', children: <fieldset className="import-fieldset" disabled={busy}>
        <div className="mapping-grid"><label className="data-field"><span>完全重复记录</span><Select aria-label="完全重复记录处理" value={config.duplicates} onChange={v => setConfig({ ...config, duplicates: v })} options={[{ value: 'keep', label: '保留并标记' }, { value: 'drop_exact', label: '移除完全重复记录' }]} /><small>订单与商品相同，不等于重复记录。</small></label>
          <label className="data-field"><span>客户金额缺失时</span><Select aria-label="客户金额缺失策略" value={config.monetary_subset} onChange={v => setConfig({ ...config, monetary_subset: v })} options={[{ value: 'all_customers', label: '先使用不依赖金额的 RF' }, { value: 'complete_customers', label: '允许仅对金额完整客户使用 RFM' }]} /><small>不把缺失金额填成零。</small></label>
          <label className="data-field"><span>开始日期（可选）</span><Input type="date" aria-label="开始日期" value={scope.date_start ?? ''} onChange={e => setScope({ ...scope, date_start: e.target.value || null })} /></label>
          <label className="data-field"><span>结束日期（可选，包含当天）</span><Input type="date" aria-label="结束日期" value={scope.date_end ?? ''} onChange={e => setScope({ ...scope, date_end: e.target.value || null })} /></label>
          <label className="data-field"><span>国家 / 地区（可选）</span><Input.TextArea aria-label="国家或地区筛选" rows={2} placeholder="每行一个，与数据中的取值一致" value={scope.countries.join('\n')} onChange={e => setScope({ ...scope, countries: e.target.value.split('\n') })} /></label>
          <label className="data-field"><span>商品范围（可选）</span><Input.TextArea aria-label="商品范围筛选" rows={2} placeholder="每行一个商品标识" value={scope.item_ids.join('\n')} onChange={e => setScope({ ...scope, item_ids: e.target.value.split('\n') })} /></label>
          <label className="data-field"><span>只分析某币种（可选）</span><Input aria-label="币种筛选" maxLength={3} placeholder="例如 CNY、GBP" value={scope.currency ?? ''} onChange={e => setScope({ ...scope, currency: e.target.value.toUpperCase() || null })} /><small>不同币种分别分析，不做汇率换算。</small></label>
        </div><div className="quality-policy-checks"><Checkbox checked={config.trim_identifiers} onChange={e => setConfig({ ...config, trim_identifiers: e.target.checked })}>去除订单、商品和客户标识的首尾空白</Checkbox>
          <Checkbox checked={config.accept_selected_amount_source} onChange={e => setConfig({ ...config, accept_selected_amount_source: e.target.checked })}>多个金额来源不一致时，确认以当前字段版本选定的金额口径为准</Checkbox></div>
        <p className="field-help">每次结果固定数据版本、字段与清洗策略。修改设置会产生新的处理记录，原始文件保持完整。</p>
      </fieldset> }]} />
    </section>
    <div className="quality-run-heading"><div><h3>处理记录</h3><span>选择一次记录，查看对应结果</span></div><Button type="text" icon={<ReloadOutlined />} onClick={() => setReload(v => v + 1)}>刷新</Button></div>
    <div className="quality-run-strip">{runs.length ? runs.map(run => <button key={run.id} className={`run-chip ${run.id === selected ? 'selected' : ''}`} onClick={() => { setSelected(run.id); setDetail(null) }}><span>{finished.has(run.status) ? <CheckCircleOutlined /> : <ClockCircleOutlined />}{stateLabel[run.status] ?? run.status}</span><small>{new Date(run.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</small></button>) : <p>还没有处理记录。选择数据与策略后，开始第一次检查。</p>}</div>
    {detail && <section className="workspace-panel quality-result-panel"><div className="quality-result-header"><div><Tag color={detail.result ? 'cyan' : active ? 'blue' : 'default'}>{stateLabel[detail.status]}</Tag><span>{detail.message}</span></div>{active && <Button danger onClick={async () => { try { setDetail(await qualityApi.cancel(projectId, detail.id)); void message.info('取消请求已提交') } catch (e) { void message.error(e instanceof Error ? e.message : '未能取消，请重试。') } }}>取消处理</Button>}</div>
      {active && <div className="quality-processing"><Progress percent={detail.progress} status="active" strokeColor="#087f73" /><p>处理在后台继续。离开页面后，可以从这条记录查看结果。</p></div>}
      {isQualityReport(detail.result) ? <QualityReport key={detail.id} report={detail.result} projectId={projectId} runId={detail.id} /> : !active && <div className="quality-stopped"><InfoText status={detail.status} /><Button loading={busy} onClick={() => void restoreSettings()}>调整设置</Button></div>}
      <div className="quality-events" aria-label="处理过程">{detail.events?.map((e, i) => <div key={`${e.created_at}-${i}`}><i /><span>{e.message}</span><time>{new Date(e.created_at).toLocaleTimeString('zh-CN', { hour12: false })}</time></div>)}</div>
    </section>}
  </div>
}

function InfoText({ status }: { status: string }) {
  return <p>{status === 'cancelled' ? '本次处理已取消，原始数据与已有结果保持完整。' : status === 'interrupted' ? '本次处理被中断。查看设置后可重新提交，系统不会自行重跑。' : '本次没有发布结果。请检查提示，调整设置后重新提交。'}</p>
}

function isQualityReport(value: QualityRun['result']): value is Report {
  return Boolean(value && 'capabilities' in value && 'views' in value)
}
