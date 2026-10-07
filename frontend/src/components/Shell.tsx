import { useCallback, useState } from 'react'
import { App, Button, Drawer } from 'antd'
import { BookOutlined, ClockCircleOutlined, FolderOutlined, MenuOutlined } from '@ant-design/icons'
import { Link, NavLink, Outlet, useLocation, useNavigate, useOutletContext } from 'react-router-dom'
import { Guide } from './Guide'
import { ProjectEditor } from './ProjectEditor'
import type { Project } from '../types'

type Recent = Pick<Project, 'id' | 'name' | 'color'>
export interface WorkspaceContext { refresh: number; createProject: () => void; remember: (project: Project) => void }
export function useWorkspace() { return useOutletContext<WorkspaceContext>() }
const recentKey = 'retailevidence.recent-projects.v1'

function readRecent(): Recent[] {
  try {
    const items: unknown = JSON.parse(localStorage.getItem(recentKey) ?? '[]')
    return Array.isArray(items) ? items.filter((i): i is Recent => typeof i?.id === 'string' && typeof i?.name === 'string' && ['teal', 'blue', 'amber', 'plum'].includes(i?.color)).slice(0, 4) : []
  } catch { return [] }
}

export function Shell() {
  const [recent, setRecent] = useState(readRecent)
  const [creating, setCreating] = useState(false)
  const [guide, setGuide] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const navigate = useNavigate()
  const location = useLocation()
  const { message } = App.useApp()
  const remember = useCallback((project: Project) => {
    setRecent(previous => {
      const next = [{ id: project.id, name: project.name, color: project.color }, ...previous.filter(p => p.id !== project.id)].slice(0, 4)
      try { localStorage.setItem(recentKey, JSON.stringify(next)) } catch { /* History is optional. */ }
      return next
    })
  }, [])
  const navigation = <>
    <Link className="brand" to="/projects" onClick={() => setMobileNav(false)} aria-label="数证智析，返回项目库">
      <span className="brand-mark" aria-hidden="true"><i /><i /></span><span><strong>数证智析</strong><small>RetailEvidence Studio</small></span>
    </Link>
    <nav aria-label="主导航"><NavLink to="/projects" end className="nav-main" onClick={() => setMobileNav(false)}><FolderOutlined />项目库</NavLink></nav>
    <section className="recent-projects"><h2>最近访问</h2>
      {recent.length ? recent.map(project => <Link key={project.id} to={`/projects/${project.id}`} onClick={() => setMobileNav(false)}
        className={`recent-link ${location.pathname.startsWith(`/projects/${project.id}`) ? 'selected' : ''}`}>
        <span className={`color-dot ${project.color}`} /><span>{project.name}</span>
      </Link>) : <div className="recent-empty"><ClockCircleOutlined /><span>尚未访问项目</span></div>}
    </section>
    <button className="guide-button" onClick={() => { setMobileNav(false); setGuide(true) }}><BookOutlined />使用指南</button>
  </>

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">跳转到主要内容</a>
    <aside className="sidebar">{navigation}</aside>
    <Drawer open={mobileNav} onClose={() => setMobileNav(false)} placement="left" size={256} title="工作区导航" className="mobile-drawer">{navigation}</Drawer>
    <div className="workspace"><header className="topbar">
      <Button className="mobile-menu" type="text" icon={<MenuOutlined />} aria-label="打开导航" onClick={() => setMobileNav(true)} />
      <nav className="breadcrumb" aria-label="面包屑"><span>工作区</span><span aria-hidden="true">/</span><Link to="/projects">项目库</Link>{location.pathname !== '/projects' ? <><span aria-hidden="true">/</span><span>项目空间</span></> : null}</nav>
    </header>
    <main id="main-content"><Outlet context={{ refresh, createProject: () => setCreating(true), remember } satisfies WorkspaceContext} /></main>
    <footer className="workspace-footer"><span />数据有边界，结论有依据。<span /></footer></div>
    <ProjectEditor open={creating} onClose={() => setCreating(false)} onSaved={project => {
      setCreating(false); setRefresh(v => v + 1); remember(project); void message.success('项目已创建'); navigate(`/projects/${project.id}`)
    }} />
    <Guide open={guide} onClose={() => setGuide(false)} />
  </div>
}
