import { useCallback, useState } from 'react'
import { App, Button, Drawer } from 'antd'
import { BookOutlined, ClockCircleOutlined, FolderOutlined, MenuOutlined } from '@ant-design/icons'
import { Link, NavLink, Outlet, useLocation, useNavigate, useOutletContext } from 'react-router-dom'
import { Guide } from './Guide'
import { ProjectEditor } from './ProjectEditor'
import type { Project } from '../types'
import { AccountMenu, useAccount } from '../Auth'

type Recent = Pick<Project, 'id' | 'name' | 'color'>
export interface WorkspaceContext { refresh: number; createProject: () => void; remember: (project: Project) => void; forget: (id: string) => void }
export function useWorkspace() { return useOutletContext<WorkspaceContext>() }

function readRecent(recentKey: string): Recent[] {
  try {
    const items: unknown = JSON.parse(localStorage.getItem(recentKey) ?? '[]')
    return Array.isArray(items) ? items.filter((i): i is Recent => typeof i?.id === 'string' && typeof i?.name === 'string' && ['teal', 'blue', 'amber', 'plum'].includes(i?.color)).slice(0, 4) : []
  } catch { return [] }
}

export function Shell() {
  const { user } = useAccount()
  const recentKey = `retailevidence.recent-projects.v2.${user!.id}`
  const [recent, setRecent] = useState(() => readRecent(recentKey))
  const [creating, setCreating] = useState(false)
  const [guide, setGuide] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const navigate = useNavigate()
  const location = useLocation()
  const currentStore = recent.find(project => project.id === location.pathname.split('/')[2])
  const { message } = App.useApp()
  const remember = useCallback((project: Project) => {
    setRecent(previous => {
      const next = [{ id: project.id, name: project.name, color: project.color }, ...previous.filter(p => p.id !== project.id)].slice(0, 4)
      try { localStorage.setItem(recentKey, JSON.stringify(next)) } catch { /* History is optional. */ }
      return next
    })
  }, [recentKey])
  const forget = useCallback((id: string) => {
    setRecent(previous => {
      const next = previous.filter(project => project.id !== id)
      try { localStorage.setItem(recentKey, JSON.stringify(next)) } catch { /* History is optional. */ }
      return next
    })
    setRefresh(value => value + 1)
  }, [recentKey])
  const navigation = <>
    <Link className="brand" to="/projects" onClick={() => setMobileNav(false)} aria-label="数证智析，返回我的店铺">
      <span className="brand-mark" aria-hidden="true"><i /><i /></span><span><strong>数证智析</strong><small>RetailEvidence Studio</small></span>
    </Link>
    <nav aria-label="主导航"><NavLink to="/projects" end className="nav-main" onClick={() => setMobileNav(false)}><FolderOutlined />我的店铺</NavLink></nav>
    <section className="recent-projects"><h2>最近访问</h2>
      {recent.length ? recent.map(project => <Link key={project.id} to={`/projects/${project.id}`} onClick={() => setMobileNav(false)}
        className={`recent-link ${location.pathname.startsWith(`/projects/${project.id}`) ? 'selected' : ''}`}>
        <span className={`color-dot ${project.color}`} /><span>{project.name}</span>
      </Link>) : <div className="recent-empty"><ClockCircleOutlined /><span>还没有访问过店铺</span></div>}
    </section>
    <button className="guide-button" onClick={() => { setMobileNav(false); setGuide(true) }}><BookOutlined />使用指南</button>
  </>

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">跳转到主要内容</a>
    <aside className="sidebar">{navigation}</aside>
    <Drawer open={mobileNav} onClose={() => setMobileNav(false)} placement="left" size={256} title="店铺导航" className="mobile-drawer">{navigation}</Drawer>
    <div className="workspace"><header className="topbar">
      <Button className="mobile-menu" type="text" icon={<MenuOutlined />} aria-label="打开导航" onClick={() => setMobileNav(true)} />
      <nav className="breadcrumb" aria-label="当前位置"><Link to="/projects" aria-current={location.pathname === '/projects' ? 'page' : undefined}>我的店铺</Link>{currentStore && <><span aria-hidden="true">/</span><span className="breadcrumb-store" title={currentStore.name} aria-current="page">{currentStore.name}</span></>}</nav>
      <AccountMenu />
    </header>
    <main id="main-content"><Outlet context={{ refresh, createProject: () => setCreating(true), remember, forget } satisfies WorkspaceContext} /></main>
    <footer className="workspace-footer"><span />数据有边界，结论有依据。<span /></footer></div>
    <ProjectEditor open={creating} onClose={() => setCreating(false)} onSaved={project => {
      setCreating(false); setRefresh(v => v + 1); remember(project); void message.success('店铺已创建'); navigate(`/projects/${project.id}`)
    }} />
    <Guide open={guide} onClose={() => setGuide(false)} />
  </div>
}
