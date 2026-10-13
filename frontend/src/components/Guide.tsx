import { Drawer } from 'antd'
import { SalesTableHelp } from './SalesTableHelp'

export function Guide({ open, onClose, dataOnly = false }: { open: boolean; onClose: () => void; dataOnly?: boolean }) {
  return <Drawer title={dataOnly ? '销售表准备指南' : '使用指南'} open={open} onClose={onClose} size={440}>
    <div className="guide-content">
      <p className="guide-lead">从销售记录出发，看清变化，再决定下一步。</p>
      {!dataOnly && <section><h3>1. 建立店铺</h3><p>在“我的店铺”新建店铺，用名称和说明记录业务范围。同一家店、同一统计口径的后续月份继续在原店铺上传，通常不必每月新建店铺。</p></section>}
      <section><h3>{dataOnly ? '' : '2. '}准备并上传销售表</h3><p>进入店铺的“销售总览”，选择“上传销售表”。表格保留一行表头，避免合并单元格；商品编号等重要标识请保存为文本。</p><SalesTableHelp /><p>单文件支持 100 MiB、150 万行、200 列。读取后先检查预览；乱码可调整读取设置，Excel 可选择工作表。</p></section>
      <section><h3>{dataOnly ? '' : '3. '}确认内容与记录范围</h3><p>核对商品、日期、销量、分析月份和金额含义。区分单价、每行销售额与订单总额；整单金额在多行重复时，只按订单计算一次。</p><p>仅在确实掌握完整记录时确认日期范围，并标明缺失日与停业日。页面会说明当前可用的分析；不要将缺失记录当作零销量。</p></section>
      {!dataOnly && <section><h3>4. 查看分析，核对建议</h3><p>“销售总览”查看当月表现和优先事项，“商品分析”查看商品贡献、变化与可用预测，“搭配建议”查看经常一起购买的商品。点击商品可追溯记录、确认类型；预测是否可用以商品详情为准。</p></section>}
      <section><h3>追加数据与查看历史</h3><p>后续月份仍上传到原店铺。如需结合多份表，在销售总览的“更多”中选择“生成月报”，勾选相关表格并核对日期重叠的处理方式。上传不会自动把所有历史表合并。</p><p>“数据记录”保留原文件、来源和字段选择；同名文件再次上传也会保存独立版本。修改字段或重新分析不会改写已有月报。</p></section>
      <div className="guide-note">先看实际销售表现，再结合数据完整性使用建议。只上传有权处理的数据。</div>
    </div>
  </Drawer>
}
