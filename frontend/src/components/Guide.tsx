import { Drawer } from 'antd'
import { HelpHint } from './HelpHint'
export function Guide({ open, onClose, dataOnly = false }: { open: boolean; onClose: () => void; dataOnly?: boolean }) {
  return <Drawer title={dataOnly ? '交易数据准备指南' : '使用指南'} open={open} onClose={onClose} size={440}>
    <div className="guide-content"><p className="guide-lead">从一份营业表开始；不确定的内容先保留未知。</p>
      {!dataOnly && <section><h3>1. 为同一家店建立项目</h3><p>同店不同月份可继续追加，便于比较；不同店或单位可分项目。</p><HelpHint topic="UX01" /></section>}
      <section><h3>2. 上传并查看预览</h3><p>在“数据记录”或“上传新数据”使用CSV/XLSX。上传完成后，还需要确认字段。</p><HelpHint topic="UX02" /><HelpHint topic="UX05" /></section>
      <section><h3>3. 确认字段和业务含义</h3><p>按原表核对商品、数量、时间、金额与状态。自动建议不是已确认事实，未知字段留空。</p><HelpHint topic="UX06" /><HelpHint topic="UX12" /></section>
      <section><h3>4. 分类、检查并生成月报</h3><p>选择月份，区分实物、费用、人工调整；金额单独确认。记录不完整时不要勾完整覆盖。</p><HelpHint topic="UX16" /><HelpHint topic="UX21" /></section>
      <section><h3>5. 看数字并核查商品</h3><p>销售额不是利润。点商品与异常日期看依据，未知原因不猜。月汇总没有每日走势或七天预测。</p><HelpHint topic="UX27" /><HelpHint topic="UX30" /><HelpHint topic="UX31" /></section>
      <section><h3>6. 库存、助手与导出</h3><p>库存要对应预测起点，历史报告不能用今天库存。AI仅解释本次证据；月报可下载、浏览器打印PDF。</p><HelpHint topic="UX33" /><HelpHint topic="UX37" /><HelpHint topic="UX44" /></section>
      {!dataOnly && <section><h3>7. 按条件使用更多分析</h3><p>在“更多分析”重新选择范围并检查，满足条件再运行客户分群或共购；质量门槛不足时不作经营结论。</p><HelpHint topic="UX39" /><HelpHint topic="UX41" /></section>}
      <section><h3>保留每一次结果</h3><p>字段和分类变更需要新月报，旧报告不会自动改变。只使用、分享有权处理的数据，模型解释不能代替真实经营核实。</p><HelpHint topic="UX43" /></section>
    </div>
  </Drawer>
}
