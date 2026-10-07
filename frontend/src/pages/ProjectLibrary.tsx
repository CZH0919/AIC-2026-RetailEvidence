import { useEffect, useState } from 'react'
import { ArrowRightOutlined, BarChartOutlined, DatabaseOutlined, FolderOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Input, Pagination } from 'antd'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useWorkspace } from '../components/Shell'
import type { ProjectList } from '../types'

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
}

export function ProjectLibrary() {
  const { createProject, refresh } = useWorkspace()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [result, setResult] = useState<ProjectList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => { const timer = setTimeout(() => { setQuery(search); setPage(1) }, 250); return () => clearTimeout(timer) }, [search])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    api.list(query, (page - 1) * 12, controller.signal).then(data => { if (!controller.signal.aborted) setResult(data) })
      .catch(issue => { if (!controller.signal.aborted) setError(issue.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [query, page, refresh, reload])

  return <>
    <div className="page-heading"><div><h1>分析项目</h1><p>将交易数据组织成独立项目，让每一次分析都有清晰的依据。</p></div>
      <Button type="primary" size="large" icon={<PlusOutlined />} onClick={createProject}>新建项目</Button>
    </div>
    <section className="library-panel" aria-labelledby="library-title">
      <div className="panel-toolbar"><h2 id="library-title">全部项目 <span className="count">{result?.total ?? '—'}</span></h2>
        <Input className="project-search" prefix={<SearchOutlined />} placeholder="搜索项目" aria-label="搜索项目" value={search} onChange={e => setSearch(e.target.value)} allowClear maxLength={100} />
      </div>
      {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={() => setReload(v => v + 1)} /> : result?.items.length ? <>
        <div className="project-table-header" aria-hidden="true"><span>项目名称</span><span>最近更新</span><span /></div>
        <ul className="project-list" aria-label="分析项目列表">
          {result.items.map(project => <li key={project.id}>
            <Link className="project-row" to={`/projects/${project.id}`}>
              <div className="project-row-main"><span className={`project-icon ${project.color}`}><FolderOutlined /></span>
                <div><h3>{project.name}</h3><p>{project.description || '为这个项目记录一个清晰的分析目标。'}</p></div></div>
              <time dateTime={project.updated_at}>{formatDate(project.updated_at)}</time><ArrowRightOutlined className="row-arrow" />
            </Link>
          </li>)}
        </ul>
        {result.total > 12 ? <div className="pagination"><Pagination current={page} pageSize={12} total={result.total} showSizeChanger={false} onChange={setPage} /></div> : null}
      </> : query ? <EmptyState title="没有找到匹配的项目" description="试试其他名称，或清空搜索查看全部项目。" action={<Button onClick={() => setSearch('')}>清空搜索</Button>} />
        : <EmptyState title="从一个项目，开始探索" description="为不同业务问题建立独立空间，保存数据与分析结果。" action={<Button type="primary" size="large" onClick={createProject}>新建第一个项目</Button>} />}
    </section>
    <section className="workflow" aria-label="分析流程">
      <div><span className="step-number">1</span><FolderOutlined /><div><h3>建立项目</h3><p>为特定业务问题创建独立项目，<br />让数据与分析更有条理。</p></div></div>
      <div><span className="step-number">2</span><DatabaseOutlined /><div><h3>准备交易数据</h3><p>整理交易记录与字段含义，<br />建立可靠的分析基础。</p></div></div>
      <div><span className="step-number">3</span><BarChartOutlined /><div><h3>探索分析</h3><p>从数据中发现规律，<br />支持更好的业务决策。</p></div></div>
    </section>
  </>
}
