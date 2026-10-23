import { lazy, Suspense, useEffect, useState } from 'react'
import { App, Button, Drawer, Dropdown } from 'antd'
import { ArrowLeftOutlined, MoreOutlined } from '@ant-design/icons'
import { Link, NavLink, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { ProjectEditor } from '../components/ProjectEditor'
import { DeleteProjectDialog } from '../components/DeleteProjectDialog'
import { useWorkspace } from '../components/Shell'
import { ErrorState, LoadingState } from '../components/States'
import { DataWorkspace } from '../components/DataWorkspace'
import type { Project } from '../types'

const SalesWorkspace = lazy(() => import('../components/SalesWorkspace'))
const QualityWorkspace = lazy(() => import('../components/QualityWorkspace'))
const PairingWorkspace = lazy(() => import('../components/PairingWorkspace'))

export function ProjectRoute() {
  const { projectId } = useParams()
  return <ProjectSpace key={projectId} projectId={projectId ?? ''} />
}

function ProjectSpace({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true), [error, setError] = useState<ApiError | null>(null)
  const [reload, setReload] = useState(0), [editing, setEditing] = useState(false)
  const { remember, forget } = useWorkspace(), { message } = App.useApp()
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const path = location.pathname
  const [storeInfo, setStoreInfo] = useState(false)
  const selectedRun = new URLSearchParams(location.search).get('run')
  const salesQuery = selectedRun ? `?${new URLSearchParams({run: selectedRun})}` : ''
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
  return <div className="retail-project">
    <header className="retail-store-header">
      <Link to="/projects" className="retail-back-link" aria-label="返回店铺列表"><ArrowLeftOutlined /></Link>
      <h1>{project.name}</h1>
      <Dropdown trigger={['click']} menu={{ items: [{ key: 'info', label: '店铺介绍' }, { key: 'edit', label: '编辑店铺' }, { type: 'divider' }, { key: 'delete', label: '删除店铺', danger: true }], onClick: ({ key }) => {
        if (key === 'delete') setDeleting(true)
        else if (key === 'edit') setEditing(true)
        else setStoreInfo(true)
      } }}><Button type="text" icon={<MoreOutlined />} aria-label="店铺设置" /></Dropdown>
    </header>
    <nav className="project-tabs" aria-label="店铺导航">
      <NavLink to={`/projects/${project.id}${salesQuery}`} end>销售总览</NavLink>
      <NavLink to={`/projects/${project.id}/products${salesQuery}`}>商品分析</NavLink>
      <NavLink to={`/projects/${project.id}/pairings${salesQuery}`}>搭配建议</NavLink>
      <NavLink to={`/projects/${project.id}/data${salesQuery}`}>数据记录</NavLink>
      <NavLink to={`/projects/${project.id}/quality${salesQuery}`}>更多分析</NavLink>
    </nav>
    {path.endsWith('/data') ? <DataWorkspace projectId={project.id} /> : <Suspense fallback={<LoadingState />}>{path.endsWith('/quality') ? <QualityWorkspace projectId={project.id} /> : path.endsWith('/pairings') ? <PairingWorkspace projectId={project.id} /> : <SalesWorkspace projectId={project.id} productsMode={path.endsWith('/products')} />}</Suspense>}
    <Drawer title="店铺介绍" open={storeInfo} width={440} onClose={() => setStoreInfo(false)}><h3>{project.name}</h3><p>{project.description || '还没有填写店铺介绍。'}</p></Drawer>
    <ProjectEditor open={editing} project={project} onClose={() => setEditing(false)} onSaved={saved => { setProject(saved); remember(saved); setEditing(false); void message.success('已更新') }} />
    <DeleteProjectDialog project={deleting ? project : null} onClose={() => setDeleting(false)} onDeleted={id => { forget(id); navigate('/projects') }} />
  </div>
}
