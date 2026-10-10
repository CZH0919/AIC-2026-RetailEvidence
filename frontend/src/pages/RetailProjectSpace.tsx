import { lazy, Suspense, useEffect, useState } from 'react'
import { App, Button } from 'antd'
import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { Link, NavLink, useLocation, useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { ProjectEditor } from '../components/ProjectEditor'
import { useWorkspace } from '../components/Shell'
import { ErrorState, LoadingState } from '../components/States'
import { DataWorkspace } from '../components/DataWorkspace'
import type { Project } from '../types'

const SalesWorkspace = lazy(() => import('../components/SalesWorkspace'))
const QualityWorkspace = lazy(() => import('../components/QualityWorkspace'))

export function ProjectRoute() {
  const { projectId } = useParams()
  return <ProjectSpace key={projectId} projectId={projectId ?? ''} />
}

function ProjectSpace({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true), [error, setError] = useState<ApiError | null>(null)
  const [reload, setReload] = useState(0), [editing, setEditing] = useState(false)
  const { remember } = useWorkspace(), { message } = App.useApp()
  const path = useLocation().pathname
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
  if (error || !project) return <ErrorState message={error?.message ?? '没有找到这个店铺。'} onRetry={() => setReload(v => v + 1)} />
  return <>
    <Link to="/projects" className="back-link"><ArrowLeftOutlined />返回店铺列表</Link>
    <div className="page-heading project-heading"><div><h1>{project.name}</h1>{project.description && <p>{project.description}</p>}</div><Button icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑店铺</Button></div>
    <nav className="project-tabs" aria-label="店铺导航"><NavLink to={`/projects/${project.id}`} end>销售月报</NavLink><NavLink to={`/projects/${project.id}/products`}>商品明细</NavLink><NavLink to={`/projects/${project.id}/data`}>数据记录</NavLink>{path.endsWith('/quality') && <NavLink to={`/projects/${project.id}/quality`}>更多分析</NavLink>}</nav>
    {path.endsWith('/data') ? <DataWorkspace projectId={project.id} /> : <Suspense fallback={<LoadingState />}>{path.endsWith('/quality') ? <QualityWorkspace projectId={project.id} /> : <SalesWorkspace projectId={project.id} productsMode={path.endsWith('/products')} />}</Suspense>}
    <ProjectEditor open={editing} project={project} onClose={() => setEditing(false)} onSaved={saved => { setProject(saved); remember(saved); setEditing(false); void message.success('已更新') }} />
  </>
}
