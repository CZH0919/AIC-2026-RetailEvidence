import { Table } from 'antd'
import type { Preview } from '../data'

export function DataPreview({ preview }: { preview: Preview }) {
  return <div className="data-preview"><div className="preview-caption"><strong>原始数据预览</strong><span>前 {preview.rows.length} 条 · 共 {preview.row_count.toLocaleString()} 行</span></div>
    <Table size="small" pagination={false} rowKey="source_row_id" scroll={{ x: 'max-content', y: 320 }}
      dataSource={preview.rows} columns={preview.columns.map(c => ({ key: c.key, dataIndex: c.key,
        title: <span>{c.name}<small className="column-missing">{c.missing ? `${c.missing.toLocaleString()} 个缺失` : '无缺失'}</small></span>, width: 170,
        render: (v: string | null) => v === null ? <span className="missing-value">空值</span> : <span className="cell-value" title={v}>{v}</span> }))} />
    <p className="field-help">保留原始值与来源行号。预览中的长文本最多显示 500 个字符，完整内容保存在数据版本中。{preview.blank_rows_skipped > 0 && ` 已跳过 ${preview.blank_rows_skipped} 个全空行。`}</p>
  </div>
}
