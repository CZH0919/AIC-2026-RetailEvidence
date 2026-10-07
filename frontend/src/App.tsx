import { Component, type ReactNode } from 'react'
import { Button } from 'antd'
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { EmptyState } from './components/States'
import { ProjectLibrary } from './pages/ProjectLibrary'
import { ProjectRoute } from './pages/ProjectSpace'

class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (this.state.failed) return <div className="app-error"><h1>页面暂时无法显示</h1><p>重新加载后再试，已保存的项目不会丢失。</p><Button type="primary" onClick={() => window.location.reload()}>重新加载</Button></div>
    return this.props.children
  }
}

export function Application() {
  return <ErrorBoundary><BrowserRouter><Routes><Route element={<Shell />}>
    <Route path="/" element={<Navigate to="/projects" replace />} />
    <Route path="/projects" element={<ProjectLibrary />} />
    <Route path="/projects/:projectId" element={<ProjectRoute />} />
    <Route path="/projects/:projectId/data" element={<ProjectRoute />} />
    <Route path="/projects/:projectId/quality" element={<ProjectRoute />} />
    <Route path="*" element={<EmptyState title="这个页面不存在" description="返回项目库，继续你的分析。" action={<Link className="button-link" to="/projects">返回项目库</Link>} />} />
  </Route></Routes></BrowserRouter></ErrorBoundary>
}
