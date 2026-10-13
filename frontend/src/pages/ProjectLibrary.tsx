import { useEffect, useState } from 'react'
import { ArrowRightOutlined, BarChartOutlined, DatabaseOutlined, FolderOutlined, MoreOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Dropdown, Input, Pagination } from 'antd'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useWorkspace } from '../components/Shell'
import { DeleteProjectDialog } from '../components/DeleteProjectDialog'
import type { Project, ProjectList } from '../types'

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
}

export function ProjectLibrary() {
  const { createProject, refresh, forget } = useWorkspace()
  const [deleting, setDeleting] = useState<Project | null>(null)
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
    <div className="page-heading"><div><h1>我的店铺</h1><p>上传销售表，看清经营变化，找到值得关注的商品。</p></div>
      <Button type="primary" size="large" icon={<PlusOutlined />} onClick={createProject}>新建店铺</Button>
    </div>
    <section className="workflow library-workflow" aria-label="分析流程">
      <div><span className="step-number">1</span><FolderOutlined /><div><h3>建立店铺</h3><p>按门店与统计口径整理记录，<br />让数据与分析更有条理。</p></div></div>
      <div><span className="step-number">2</span><DatabaseOutlined /><div><h3>上传销售表</h3><p>核对字段含义与记录范围，<br />建立可靠的分析基础。</p></div></div>
      <div><span className="step-number">3</span><BarChartOutlined /><div><h3>查看销售分析</h3><p>从数据中发现规律，<br />支持更好的业务决策。</p></div></div>
    </section>
    <section className="library-panel" aria-labelledby="library-title">
      <div className="panel-toolbar"><h2 id="library-title">全部店铺 <span className="count">{result?.total ?? '—'}</span></h2>
        <Input className="project-search" prefix={<SearchOutlined />} placeholder="搜索店铺" aria-label="搜索店铺" value={search} onChange={e => setSearch(e.target.value)} allowClear maxLength={100} />
      </div>
      {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={() => setReload(v => v + 1)} /> : result?.items.length ? <>
        <div className="project-table-header" aria-hidden="true"><span>店铺名称</span><span>最近更新</span><span /></div>
        <ul className="project-list" aria-label="我的店铺列表">
          {result.items.map(project => <li key={project.id} className="project-list-entry">
            <Link className="project-row" to={`/projects/${project.id}`}>
              <div className="project-row-main"><span className={`project-icon ${project.color}`}><FolderOutlined /></span>
                <div><h3>{project.name}</h3><p>{project.description || '为这个店铺记录一个清晰的分析目标。'}</p></div></div>
              <time dateTime={project.updated_at}>{formatDate(project.updated_at)}</time><ArrowRightOutlined className="row-arrow" />
            </Link>
            <Dropdown trigger={['click']} menu={{ items: [{ key: 'delete', label: '删除店铺', danger: true }], onClick: () => setDeleting(project) }}>
              <Button className="project-row-menu" type="text" icon={<MoreOutlined />} aria-label={`${project.name}的更多操作`} />
            </Dropdown>
          </li>)}
        </ul>
        {result.total > 12 ? <div className="pagination"><Pagination current={page} pageSize={12} total={result.total} showSizeChanger={false} onChange={setPage} /></div> : null}
      </> : query ? <EmptyState title="没有找到匹配的店铺" description="试试其他名称，或清空搜索查看全部店铺。" action={<Button onClick={() => setSearch('')}>清空搜索</Button>} />
        : <EmptyState title="从一家店铺，开始了解销售" description="为不同业务问题建立独立空间，保存数据与分析结果。" action={<Button type="primary" size="large" onClick={createProject}>新建第一家店铺</Button>} />}
    </section>
    <DeleteProjectDialog project={deleting} onClose={() => setDeleting(null)} onDeleted={id => {
      setDeleting(null); forget(id)
      if (result?.items.length === 1 && page > 1) setPage(value => value - 1)
    }} />
  </>
}
