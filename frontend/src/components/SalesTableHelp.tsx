export function SalesTableHelp({ example = false }: { example?: boolean }) {
  return <div className="sales-table-help">
    <p><strong>至少准备：</strong>商品名称或编号、销售日期、销量。列名可以不同，下一步选择对应列即可。</p>
    <p>只有整月汇总也可以：至少提供商品与销量，下一步选择“整月销售汇总”并填写所属月份；这类表不提供日级预测或搭配分析。</p>
    <p>销售额或单价可选；需要分析商品搭配时，请保留订单编号和每笔订单的完整商品明细。</p>
    {example && <details><summary>看一个销售表小例子</summary><table><caption>每行是一条商品销售记录</caption><thead><tr><th>商品</th><th>销售日期</th><th>销量</th></tr></thead><tbody><tr><td>帆布袋</td><td>2026-09-01</td><td>2</td></tr><tr><td>马克杯</td><td>2026-09-02</td><td>1</td></tr></tbody></table></details>}
  </div>
}
