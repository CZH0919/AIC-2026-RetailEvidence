export function SalesTableHelp({ example = false }: { example?: boolean }) {
  return <div className="sales-table-help">
    <p><strong>表里需要：</strong>商品名称或编号、销售日期、销量。销售额或单价有的话也一起上传。</p>
    <details><summary>只有整月汇总，没有销售日期？</summary><p>也可以上传。下一步选择“整月销售汇总”，填写所属月份即可；至少要有商品和销量。</p><p>月汇总可以比较每月销量；每日趋势、七天预测和商品搭配需要更详细的销售记录。</p></details>
    <details><summary>想看哪些商品经常一起买？</summary><p>请保留订单编号，以及每笔订单里买了哪些商品。同一订单内的商品，才能用于分析搭配。</p></details>
    {example && <details><summary>看一个销售表例子</summary><table><caption>每行记录一种商品的销售</caption><thead><tr><th>商品</th><th>销售日期</th><th>销量</th></tr></thead><tbody><tr><td>帆布袋</td><td>2026-09-01</td><td>2</td></tr><tr><td>马克杯</td><td>2026-09-02</td><td>1</td></tr></tbody></table></details>}
    <details><summary>文件格式和读取问题</summary><p>支持 CSV、Excel（XLSX），单个文件不超过 100 MiB。第一行写列名，避免合并单元格；商品编号有前导 0 时，请保存为文本。</p><p>出现乱码时，在“更多读取设置”中调整文件编码，再点击“重新读取”；Excel 有多张工作表时，选择包含销售记录的那张。</p></details>
  </div>
}
