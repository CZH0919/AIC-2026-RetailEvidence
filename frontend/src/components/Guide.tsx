import { Drawer } from 'antd'

export function Guide({ open, onClose, dataOnly = false }: { open: boolean; onClose: () => void; dataOnly?: boolean }) {
  return <Drawer title={dataOnly ? '交易数据准备指南' : '使用指南'} open={open} onClose={onClose} size={440}>
    <div className="guide-content">
      <p className="guide-lead">清晰的数据边界，是可靠分析的起点。</p>
      {!dataOnly ? <section><h3>按业务问题组织项目</h3><p>为不同门店、时间范围或分析目标创建独立项目。名称帮助你快速找到项目，说明用于记录分析背景。</p></section> : null}
      <section><h3>准备交易明细</h3><p>整理为 CSV 或 Excel 表格。通常每行代表订单中的一条商品明细，保留表头，避免合并单元格。</p></section>
      <section><h3>导入与确认</h3><p>在“数据与版本”上传文件，或选择公开数据。单文件支持 100 MiB、150 万行、200 列；CSV 可选择编码，XLSX 可选择工作表。同名文件再次导入，也会生成独立版本。</p></section>
      <section><h3>保留订单与商品标识</h3><p>同一订单的明细使用相同订单标识；商品使用稳定编号。客户、时间、数量和金额可帮助明确可用的分析范围。</p></section>
      <section><h3>说明金额含义</h3><p>区分单价、行金额和订单总额。整单金额若在多行重复，不能作为每行金额再次累加。</p></section>
      <section><h3>保持原始数据可追溯</h3><p>保留原文件和来源说明，记录时间范围、币种及退货规则。只使用有权处理的数据。</p></section>
      <section><h3>保留每次字段选择</h3><p>字段可以手动调整并保存草稿。创建数据版本后，再次修改字段会保留一份新的映射记录，历史设置仍可查看。Excel 已改写的长编号无法自动恢复，请以文本保存重要标识。</p></section>
      <div className="guide-note">选择文件、查看预览、确认字段与口径，即可保存数据版本。</div>
    </div>
  </Drawer>
}
