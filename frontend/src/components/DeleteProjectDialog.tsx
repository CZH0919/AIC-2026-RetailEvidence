import { useState } from 'react'
import { Alert, App, Modal } from 'antd'
import { api } from '../api'
import type { Project } from '../types'

export function DeleteProjectDialog({ project, onClose, onDeleted }: {
  project: Project | null; onClose: () => void; onDeleted: (id: string) => void;
}) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const { message } = App.useApp()
  async function remove() {
    if (!project || busy) return
    setBusy(true); setError('')
    try {
      await api.remove(project.id, project.revision)
      onDeleted(project.id)
      void message.success('店铺已删除')
    } catch (issue) { setError(issue instanceof Error ? issue.message : '删除失败，请稍后重试。') }
    finally { setBusy(false) }
  }
  return <Modal title="删除店铺" open={Boolean(project)} onCancel={() => { setError(''); onClose() }}
    onOk={() => void remove()} okText="确认删除" cancelText="取消" confirmLoading={busy}
    okButtonProps={{ danger: true }} cancelButtonProps={{ disabled: busy }} closable={!busy} keyboard={!busy} maskClosable={!busy}>
    <p className="delete-store-name">确定删除“{project?.name}”吗？</p>
    <p>该店铺上传的销售表、月报和分析结果也会从网站移除。删除后无法在网页恢复。</p>
    {error && <Alert type="error" showIcon title={error} />}
  </Modal>
}
