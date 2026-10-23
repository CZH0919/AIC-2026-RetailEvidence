import { useEffect, useState } from 'react'
import { Alert, Button, Form, Input, Modal, Radio } from 'antd'
import { api, ApiError } from '../api'
import type { Project, ProjectInput } from '../types'

export function ProjectEditor({ open, project, onClose, onSaved }: {
  open: boolean; project?: Project; onClose: () => void; onSaved: (project: Project) => void
}) {
  const [form] = Form.useForm<ProjectInput>()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (open) {
      form.resetFields()
      form.setFieldsValue(project ?? { name: '', description: '', color: 'teal' })
      setError('')
    }
  }, [open, project, form])

  async function submit(values: ProjectInput) {
    if (saving) return
    setSaving(true); setError('')
    const input = { ...values, name: values.name.trim(), description: (values.description ?? '').trim() }
    try {
      const saved = project ? await api.update(project.id, input, project.revision) : await api.create(input)
      onSaved(saved)
    } catch (failure) {
      const issue = failure instanceof ApiError ? failure : new ApiError('保存失败，请稍后重试。')
      setError(issue.message)
      const fieldNames = ['name', 'description', 'color'] as const
      form.setFields(fieldNames.filter(name => issue.fields[name]).map(name => ({ name, errors: [issue.fields[name]] })))
    } finally { setSaving(false) }
  }

  return <Modal open={open} title={project ? '编辑店铺' : '新建店铺'} width={520}
    onCancel={() => { if (!saving) onClose() }} maskClosable={!saving} closable={!saving} keyboard={!saving}
    footer={null} destroyOnHidden>
    <p className="modal-intro">按门店与统计口径整理销售记录，后续月份继续在这里上传。</p>
    <Form form={form} layout="vertical" onFinish={submit} requiredMark="optional" disabled={saving}>
      <Form.Item name="name" label="店铺名称" rules={[{ required: true, whitespace: true, message: '请填写店铺名称。' }, { max: 64, message: '店铺名称最多 64 个字符。' }]}>
        <Input autoFocus maxLength={64} showCount placeholder="例如：杉木生活馆·中心店" autoComplete="off" />
      </Form.Item>
      <Form.Item name="description" label="店铺说明" rules={[{ max: 500, message: '店铺说明最多 500 个字符。' }]}>
        <Input.TextArea maxLength={500} showCount rows={3} placeholder="记录业务问题、数据范围或分析目标" />
      </Form.Item>
      <Form.Item name="color" label="店铺标记">
        <Radio.Group className="color-options">
          {[['teal', '青绿'], ['blue', '海蓝'], ['amber', '琥珀'], ['plum', '烟紫']].map(([value, label]) =>
            <Radio.Button value={value} key={value}><span className={`color-dot ${value}`} />{label}</Radio.Button>)}
        </Radio.Group>
      </Form.Item>
      {error ? <Alert className="form-error" type="error" showIcon title={error} /> : null}
      <div className="modal-actions"><Button onClick={onClose} disabled={saving}>取消</Button>
        <Button type="primary" htmlType="submit" loading={saving}>{project ? '保存修改' : '创建店铺'}</Button>
      </div>
    </Form>
  </Modal>
}
