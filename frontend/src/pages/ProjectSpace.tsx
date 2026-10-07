import { lazy, Suspense, useEffect, useState } from 'react'
import { App, Button } from 'antd'
import { ArrowLeftOutlined, ArrowRightOutlined, CheckOutlined, EditOutlined, FileTextOutlined, FolderOutlined } from '@ant-design/icons'
import { Link, NavLink, useLocation, useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { Guide } from '../components/Guide'
import { ProjectEditor } from '../components/ProjectEditor'
import { useWorkspace } from '../components/Shell'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import type { Project } from '../types'
import { formatDate } from './ProjectLibrary'
import { DataWorkspace } from '../components/DataWorkspace'
import { dataApi } from '../data'

const QualityWorkspace = lazy(() => import('../components/QualityWorkspace'))

export function ProjectRoute() {
  const { projectId } = useParams()
  return <ProjectSpace key={projectId} projectId={projectId ?? ''} />
}

function ProjectSpace({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [reload, setReload] = useState(0)
  const [editing, setEditing] = useState(false)
  const [guide, setGuide] = useState(false)
  const [versionCount, setVersionCount] = useState<number | null>(null)
  const { remember } = useWorkspace()
  const { message } = App.useApp()
  const isData = useLocation().pathname.endsWith('/data')
  const isQuality = useLocation().pathname.endsWith('/quality')
  useEffect(() => {
    let active = true
    dataApi.versions(projectId).then(r => { if (active) setVersionCount(r.items.length) }).catch(() => { if (active) setVersionCount(null) })
    return () => { active = false }
  }, [projectId, isData])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(null)
    api.get(projectId, controller.signal).then(data => {
      if (!controller.signal.aborted) { setProject(data); remember(data) }
    }).catch(issue => { if (!controller.signal.aborted) setError(issue) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [projectId, reload, remember])

  if (loading) return <LoadingState />
  if (error?.code === 'not_found' || error?.code === 'validation_error') return <EmptyState title="没有找到这个项目" description="项目链接可能已失效，请从项目库重新选择。" action={<Link className="button-link" to="/projects">返回项目库</Link>} />
  if (error || !project) return <ErrorState message={error?.message ?? '暂时无法读取项目。'} onRetry={() => setReload(v => v + 1)} />

  return <>
    <Link to="/projects" className="back-link"><ArrowLeftOutlined />返回项目库</Link>
    <div className="page-heading project-heading"><div className="project-title"><span className={`project-icon large ${project.color}`}><FolderOutlined /></span><div><h1>{project.name}</h1><p>{project.description || '一个新的分析空间，等待你的业务问题。'}</p></div></div>
      <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑项目</Button>
    </div>
    <nav className="project-tabs" aria-label="项目导航"><NavLink to={`/projects/${project.id}`} end>项目概览</NavLink><NavLink to={`/projects/${project.id}/data`}>数据与版本</NavLink><NavLink to={`/projects/${project.id}/quality`}>质量与任务</NavLink></nav>
    {isQuality ? <Suspense fallback={<LoadingState />}><QualityWorkspace projectId={project.id} /></Suspense> : isData ? <DataWorkspace projectId={project.id} /> : <div className="project-content-grid">
      <section className="workspace-panel">
        <div className="section-title"><h2>{isData ? '准备第一份交易数据' : '数据与分析'}</h2><span>{isData ? '从清晰的明细开始' : '当前项目'}</span></div>
        <EmptyState compact title={versionCount ? `已保存 ${versionCount} 个数据版本` : '从数据开始你的分析'}
          description={versionCount ? '查看原始预览与已确认字段，或添加新的数据来源。' : '把交易数据带入这个项目，为每个结论保留清晰的来源。'}
          action={isData ? <Button type="primary" icon={<FileTextOutlined />} onClick={() => setGuide(true)}>查看文件要求</Button> : <Link className="button-link" to={`/projects/${project.id}/data`}>{versionCount ? '查看数据与版本' : '准备导入数据'}<ArrowRightOutlined /></Link>} />
        {isData ? <div className="file-requirements"><span>CSV / XLSX</span><p>保留表头 · 一行一条商品明细 · 记录来源与口径</p></div> : null}
      </section>
      <aside className="project-aside"><section><h2>项目概况</h2><dl>
        <div><dt>创建日期</dt><dd>{formatDate(project.created_at)}</dd></div><div><dt>最近更新</dt><dd>{formatDate(project.updated_at)}</dd></div>
        <div><dt>数据状态</dt><dd>{versionCount === null ? '前往数据页查看' : versionCount ? `${versionCount} 个版本` : '尚未添加'}</dd></div></dl></section>
        <section className="next-steps"><h2>下一步</h2><div className="step-complete"><CheckOutlined /><span>建立独立分析项目</span></div><div><span className="step-circle" /><span>准备对应的交易数据</span></div>
          <p>每个项目的名称与说明独立保存。切换项目，可以继续另一个业务问题。</p>
        </section>
      </aside>
    </div>}
    <ProjectEditor open={editing} project={project} onClose={() => setEditing(false)} onSaved={saved => {
      setProject(saved); remember(saved); setEditing(false); void message.success('项目已更新')
    }} />
    <Guide open={guide} dataOnly onClose={() => setGuide(false)} />
  </>
}
