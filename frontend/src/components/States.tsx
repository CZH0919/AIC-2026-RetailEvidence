import { Button, Skeleton } from 'antd'
import { FileTextOutlined, FolderOpenOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ReactNode } from 'react'

export function EmptyState({ title, description, action, compact = false }: {
  title: string; description: string; action?: ReactNode; compact?: boolean
}) {
  return <div className={`empty-state ${compact ? 'compact' : ''}`}>
    <div className="empty-illustration" aria-hidden="true"><FileTextOutlined /><FolderOpenOutlined /></div>
    <h2>{title}</h2><p>{description}</p>{action}
  </div>
}

export function LoadingState() {
  return <div className="loading-state" role="status" aria-label="正在加载"><Skeleton active paragraph={{ rows: 3 }} /></div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="error-state" role="alert">
    <span className="error-symbol" aria-hidden="true">!</span><h2>暂时无法显示内容</h2>
    <p>{message}</p><Button icon={<ReloadOutlined />} onClick={onRetry}>重新加载</Button>
  </div>
}
