import { SalesTableHelp } from './SalesTableHelp'
import { useEffect, useState } from 'react'
import { Alert, Button, DatePicker, Drawer, Select, Spin, Steps, Table } from 'antd'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import { CloudUploadOutlined, FileTextOutlined } from '@ant-design/icons'
import { dataApi, initialMapping, parseDefaults } from '../data'
import type { Draft, Mapping, ParseOptions, Version, VersionDetail } from '../data'
import { salesApi } from '../retail'
import type { SalesParameters, SalesRun, SourceInfo } from '../retail'
import { finished } from '../quality'
import { SalesImportFields } from './SalesImportFields'
import { CoverageConfirmation } from './CoverageConfirmation'

function salesMapping(draft: Draft): Mapping {
  const mapping = initialMapping(draft)
  // A product name can identify products when the file has no separate code.
  if (!mapping.columns.item_id && mapping.columns.item_name) {
    mapping.columns = { ...mapping.columns, item_id: mapping.columns.item_name, item_name: null }
  }
  if (mapping.amount_mode === 'none') {
    mapping.amount_mode = mapping.columns.line_amount ? 'line_amount' : mapping.columns.quantity && mapping.columns.unit_price ? 'quantity_unit_price' : 'none'
  }
  return { ...mapping, quantity_unit: mapping.quantity_unit || '原始商品单位', time_format: mapping.columns.event_time ? mapping.time_format ?? 'iso8601' : null, timezone: mapping.columns.event_time ? mapping.timezone ?? 'Asia/Shanghai' : null }
}

function previewMonth(draft: Draft, mapping: Mapping) {
  const dates = draft.preview?.rows.map(row => String(row[mapping.columns.event_time ?? ''] ?? '')).map(value => value.match(/^(\d{4})[-/](\d{1,2})[-/]/)).filter(match => !!match && Number(match[2]) >= 1 && Number(match[2]) <= 12) ?? []
  return dates.map(match => `${match![1]}-${match![2].padStart(2, '0')}`).sort().at(-1) ?? ''
}

export function SalesImportWizard({ projectId, versions, initialSources = [], existing = false, onClose, onDone }: { projectId: string; versions: Version[]; initialSources?: string[]; existing?: boolean; onClose: () => void; onDone: (run: SalesRun) => void }) {
  const [step, setStep] = useState(existing ? 1 : 0)
  const [draft, setDraft] = useState<Draft | null>(null), [mapping, setMapping] = useState<Mapping | null>(null)
  const [options, setOptions] = useState<ParseOptions>({ ...parseDefaults, sheets: [] })
  const [sourceIds, setSourceIds] = useState(initialSources.length ? initialSources : versions[0] ? [versions[0].id] : [])
  const [sourceInfo, setSourceInfo] = useState<SourceInfo[]>([]), [saved, setSaved] = useState<VersionDetail | null>(null), [savedMapping, setSavedMapping] = useState('')
  const [month, setMonth] = useState(''), [complete, setComplete] = useState(false), [duplicates, setDuplicates] = useState('keep'), [merge, setMerge] = useState('append'), [closed, setClosed] = useState('')
  const [coverageStart, setCoverageStart] = useState(''), [coverageEnd, setCoverageEnd] = useState(''), [missing, setMissing] = useState('')
  const [current, setCurrent] = useState<SalesRun | null>(null)
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const [pollRetry, setPollRetry] = useState(0)
  const work = async (label: string, action: () => Promise<void>) => {
    setBusy(label); setError('')
    try { await action() } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }
  useEffect(() => {
    if (!existing || !sourceIds.length) return
    let active = true
    setSourceInfo([]); setBusy('正在读取表格信息'); setError('')
    Promise.all(sourceIds.map(id => salesApi.source(projectId, id))).then(info => {
      if (active) { setSourceInfo(info); setMonth(info.at(-1)?.suggested_month ?? ''); setComplete(false) }
    }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setBusy('') })
    return () => { active = false }
  }, [existing, projectId, sourceIds, retry])
  useEffect(() => {
    if (!current || finished.has(current.status)) return
    let active = true, polling = false
    const timer = window.setInterval(async () => {
      if (polling) return
      polling = true
      try {
        const run = await salesApi.run(projectId, current.id)
        if (active) setCurrent(run)
      } catch (e) { if (active) { setError((e as Error).message); window.clearInterval(timer) } }
      finally { polling = false }
    }, 1800)
    return () => { active = false; window.clearInterval(timer) }
  }, [projectId, current?.id, current?.status, pollRetry])
  useEffect(() => {
    if (current?.result?.products.length) onDone(current)
  }, [current, onDone])
  async function read(fileDraft: Draft, parse: ParseOptions) {
    const next = await dataApi.preview(projectId, fileDraft.id, parse)
    const fields = salesMapping(next)
    setDraft(next); setMapping(fields); setSaved(null); setSavedMapping('')
    setMonth(previewMonth(next, fields)); setSourceInfo([]); setComplete(false)
  }
  function upload(file: File) {
    if (!/\.(csv|xlsx)$/i.test(file.name)) { setError('请选择 CSV 或 XLSX 销售表。'); return }
    if (file.size > 100 * 1024 * 1024) { setError('文件超过 100 MB，请分成较小的表格。'); return }
    void work('正在读取销售表', async () => {
      const received = await dataApi.upload(projectId, file)
      const parse = { ...parseDefaults, sheets: received.inspection.sheets.slice(0, 1) }
      setDraft(received); setMapping(null); setOptions(parse); setSaved(null)
      await read(received, parse)
    })
  }
  function validate(fields: Mapping) {
    if (!fields.columns.item_id) throw new Error('请选择商品名称或编号所在列。')
    if (!fields.columns.quantity) throw new Error('请选择销量所在列。')
    if (fields.record_kind !== 'monthly_summary' && !fields.columns.event_time) throw new Error('请选择日期列。整月汇总表没有日期时，点击“没有日期，按月汇总分析”。')
    if (!fields.quantity_unit.trim()) throw new Error('请填写销量单位，例如件、包或公斤。')
    if (fields.amount_mode === 'line_amount' && !fields.columns.line_amount) throw new Error('请选择销售额所在列，或选择只分析销量。')
    if (fields.amount_mode === 'quantity_unit_price' && !fields.columns.unit_price) throw new Error('请选择单价所在列，或选择只分析销量。')
    if (fields.amount_mode !== 'none' && !fields.columns.currency && !fields.currency_constant) throw new Error('请选择销售额币种。')
    if (fields.status_rule === 'unspecified') throw new Error('请选择表格包含正常销售，还是包含取消、退货记录。')
  }
  async function analyze() {
    if (!month) { setError('请选择要分析的月份。'); return }
    await work('正在准备分析', async () => {
      let info = sourceInfo
      if (!existing) {
        if (!draft || !mapping) return
        const fields = { ...mapping, summary_month: mapping.record_kind === 'monthly_summary' ? month : mapping.summary_month, confirmed: true }
        validate(fields)
        const key = JSON.stringify(fields)
        let version = saved
        if (!version) version = await dataApi.confirm(projectId, draft, fields)
        else if (key !== savedMapping) { await dataApi.revise(projectId, version, fields); version = await dataApi.version(projectId, version.id) }
        setSaved(version); setSavedMapping(key)
        info = [await salesApi.source(projectId, version.id)]
        setSourceInfo(info)
      }
      if (!info.length) throw new Error('请先选择销售表。')
      if (!info.some(s => s.months.includes(month))) throw new Error('所选月份不在这份表格里，请选择下方已识别的月份。')
      if (complete && (!coverageStart || !coverageEnd || coverageEnd < coverageStart)) throw new Error('请填写并核对完整记录的起止日期。')
      const params: SalesParameters = { sources: info.map(s => ({ version_id: s.version_id, mapping_revision: s.mapping_revision })), month, complete_coverage: complete, coverage_start: complete ? coverageStart : null, coverage_end: complete ? coverageEnd : null, merge_mode: merge, duplicates, closed_dates: complete ? closed.split(',').map(s => s.trim()).filter(Boolean) : [], missing_dates: complete ? missing.split(',').map(s => s.trim()).filter(Boolean) : [], check_only: false }
      setCurrent(await salesApi.create(projectId, params)); setStep(2)
    })
  }
  const running = !!current && !finished.has(current.status)
  const months = [...new Set(sourceInfo.flatMap(s => s.months))].sort().reverse()
  const result = current?.result
  const changedReading = !!draft?.preview && JSON.stringify(options) !== JSON.stringify(draft.options)
  const close = () => running && current ? onDone(current) : onClose()
  return <Drawer title={existing ? '生成销售月报' : '上传销售表'} open width={820} onClose={close} closable={!busy} maskClosable={!busy && !running} keyboard={!busy} className="sales-upload-drawer" footer={<div className="sales-upload-footer"><span>{busy || (running ? '分析完成后会自动打开销售总览' : '按步骤确认，程序自动完成分析')}</span><div>
    <Button disabled={!!busy} onClick={close}>暂时关闭</Button>
    {step === 1 && !existing && !saved && <Button disabled={!!busy} onClick={() => setStep(0)}>上一步</Button>}
    {step === 0 && <Button type="primary" disabled={!draft?.preview || changedReading || !!busy} onClick={() => setStep(1)}>下一步</Button>}
    {step === 1 && <Button type="primary" loading={!!busy} disabled={existing && !sourceInfo.length} onClick={() => void analyze()}>开始分析</Button>}
    {step === 2 && !running && <Button type="primary" onClick={() => { setStep(1); setCurrent(null); setError('') }}>调整后重试</Button>}
  </div></div>}>
    <div className="sales-upload"><Steps current={step} size="small" items={[{ title: '上传表格' }, { title: '确认内容' }, { title: '查看分析' }]} />
      {error && <Alert className="sales-upload-alert" type="error" showIcon message={error} action={running ? <Button size="small" onClick={() => void work('正在读取分析进度', async () => { setCurrent(await salesApi.run(projectId, current!.id)); setPollRetry(v => v + 1) })}>重试</Button> : existing && <Button size="small" onClick={() => setRetry(v => v + 1)}>重试</Button>} />}
      {busy && <div className="sales-upload-progress" role="status"><Spin size="small" /><span>{busy}，请稍候。</span></div>}
      <fieldset disabled={!!busy} className="sales-upload-fieldset">
        {step === 0 && <>
          {!draft ? <div className="sales-upload-zone"><CloudUploadOutlined /><h3>上传你的销售表</h3><p>支持 CSV、Excel（XLSX），上传后自动读取并预览。</p><label className="file-picker">选择文件<input type="file" accept=".csv,.xlsx" aria-label="选择销售表" disabled={!!busy} onChange={e => { if (e.target.files?.[0]) upload(e.target.files[0]); e.target.value = '' }} /></label><small>单个文件不超过 100 MiB</small><SalesTableHelp example /></div> : <>
            <div className="sales-upload-file"><FileTextOutlined /><strong>{draft.filename}</strong><label className="sales-upload-replace">换一个文件<input type="file" accept=".csv,.xlsx" aria-label="更换销售表" disabled={!!busy} onChange={e => { if (e.target.files?.[0]) upload(e.target.files[0]); e.target.value = '' }} /></label></div>
            {draft.preview && <><p className="sales-upload-muted">已读取 {draft.preview.row_count.toLocaleString()} 行，先看看前 5 行是否正常。</p><Table className="sales-upload-preview" size="small" pagination={false} rowKey="source_row_id" dataSource={draft.preview.rows.slice(0, 5)} scroll={{ x: 'max-content' }} columns={draft.preview.columns.map(c => ({ title: c.name, dataIndex: c.key, key: c.key, width: 130, render: (value: string | null) => <span className="sales-upload-cell">{value ?? '—'}</span> }))} /></>}
            {draft.inspection.sheets.length > 1 && <label className="sales-upload-field"><span>选择工作表</span><Select aria-label="销售表工作表" mode="multiple" value={options.sheets} options={draft.inspection.sheets.map(s => ({ value: s, label: s }))} onChange={sheets => { const next = { ...options, sheets }; setOptions(next); void work('正在读取工作表', () => read(draft, next)) }} /></label>}
          </>}
          {draft && <details className="sales-upload-more" open={!draft.preview || undefined}><summary>更多读取设置</summary><div className="sales-upload-grid">
            {draft.suffix === '.csv' && <><label className="sales-upload-field"><span>文件编码</span><Select aria-label="销售表文件编码" value={options.encoding} options={[{ value: 'utf-8-sig', label: 'UTF-8' }, { value: 'gb18030', label: 'GBK / GB18030' }, { value: 'cp1252', label: 'Windows-1252' }]} onChange={encoding => setOptions(v => ({ ...v, encoding }))} /></label><label className="sales-upload-field"><span>列分隔符</span><Select aria-label="销售表列分隔符" value={options.delimiter} options={[[',', '逗号'], [';', '分号'], ['\t', '制表符'], ['|', '竖线']].map(([value, label]) => ({ value, label }))} onChange={delimiter => setOptions(v => ({ ...v, delimiter }))} /></label></>}
          </div>{changedReading && <p>读取设置已改变，请重新读取后继续。</p>}<Button disabled={!!busy} onClick={() => void work('正在重新读取销售表', () => read(draft, options))}>重新读取</Button></details>}
        </>}
        {step === 1 && <><div className="sales-upload-intro"><h3>确认这份表格的内容</h3><p>{existing ? '选择销售表和月份，并核对下方记录范围与可用分析。' : '核对字段和月份，再确认记录范围；下方会说明可用的分析。'}</p></div>
          {existing ? <label className="sales-upload-field"><span>使用销售表</span><Select aria-label="分析使用的销售表" mode="multiple" value={sourceIds} options={versions.map(v => ({ value: v.id, label: v.filename }))} onChange={setSourceIds} /></label> : draft?.preview && mapping && <SalesImportFields preview={draft.preview} value={mapping} onChange={next => { setMapping(next); setSourceInfo([]) }} />}
          <div className="sales-upload-month"><label className="sales-upload-field"><span>分析月份</span><DatePicker picker="month" aria-label="上传流程分析月份" placeholder="选择月份" format="YYYY-MM" value={month ? dayjs(`${month}-01`) : null} onChange={date => setMonth(date?.format('YYYY-MM') ?? '')} /></label>
            {!!months.length && <label className="sales-upload-field"><span>表格里已识别的月份</span><Select aria-label="已识别月份" value={months.includes(month) ? month : undefined} placeholder="选择月份" options={months.map(value => ({ value, label: value }))} onChange={setMonth} /></label>}
          </div>
          {!existing && mapping?.columns.event_time && !sourceInfo.length && <p className="sales-upload-muted">月份根据预览日期填写，可修改。日期格式和时区可在“更多字段设置”中调整。</p>}
          <CoverageConfirmation month={month} kinds={existing ? sourceInfo.map(s => s.mapping.record_kind ?? 'transactions') : mapping ? [mapping.record_kind ?? 'transactions'] : []}
            complete={complete} start={coverageStart} end={coverageEnd} missing={missing} closed={closed}
            onComplete={setComplete} onStart={setCoverageStart} onEnd={setCoverageEnd} onMissing={setMissing} onClosed={setClosed} />
          <details className="sales-upload-more"><summary>更多分析设置</summary><div className="sales-upload-settings">
            <label className="sales-upload-field"><span>重复记录</span><Select aria-label="上传流程重复记录" value={duplicates} options={[{ value: 'keep', label: '保留重复候选' }, { value: 'drop_exact', label: '删除完全相同的记录' }]} onChange={setDuplicates} /></label>
            {sourceIds.length > 1 && existing && <label className="sales-upload-field"><span>多个文件日期重叠时</span><Select aria-label="上传流程重叠日期" value={merge} options={[{ value: 'append', label: '仅追加不重叠日期' }, { value: 'replace_overlap', label: '用较新文件替换重叠日期' }]} onChange={setMerge} /></label>}
          </div></details>
          <p className="sales-upload-muted">点击“开始分析”，即确认以上选择。程序会处理空值、取消和退货等记录，详情可在月报中查看。</p>
        </>}
        {step === 2 && <div className="sales-upload-result"><h3>{running ? '正在生成销售分析' : '暂时没有可用结果'}</h3><p>{running ? '正在整理销售记录、分析变化并生成月报。完成后自动打开销售总览。' : result ? '所选月份没有可用销售记录，请更换月份或检查字段。' : current?.message}</p>
          {running && <Spin />}
          {running && <Button onClick={() => void work('正在取消分析', async () => { await salesApi.cancel(projectId, current!.id); setCurrent(await salesApi.run(projectId, current!.id)) })}>取消分析</Button>}
          {result && <details className="sales-upload-more"><summary>查看处理详情</summary><p>读取 {result.quality.input_rows.toLocaleString()} 行，采用 {result.quality.included_rows.toLocaleString()} 行。</p>{result.quality.reasons.map(reason => <p key={reason.code}>{reason.label}：{reason.count.toLocaleString()} 行</p>)}</details>}
        </div>}
      </fieldset>
    </div>
  </Drawer>
}
