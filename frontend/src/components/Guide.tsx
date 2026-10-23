import { Drawer } from 'antd'
import { SalesTableHelp } from './SalesTableHelp'
import './Guide.css'

export function Guide({ open, onClose, dataOnly = false }: { open: boolean; onClose: () => void; dataOnly?: boolean }) {
  return <Drawer title={dataOnly ? '销售表准备指南' : '使用指南'} open={open} onClose={onClose} size={480}>
    <div className="merchant-guide">
      {dataOnly ? <SalesTableHelp example /> : <>
        <p className="merchant-guide-intro">四步看懂店铺销售</p>
        <ol className="merchant-guide-steps">
          <li><h3>建店铺</h3><p>在“我的店铺”点击“新建店铺”，填写店铺名称。</p></li>
          <li><h3>上传销售表</h3><p>进入店铺，点击“上传销售表”，选择 CSV 或 Excel（XLSX）文件。</p></li>
          <li><h3>确认内容</h3><p>核对商品、日期、销量对应的列，选择分析月份，再点击“开始分析”。</p></li>
          <li><h3>查看分析</h3>
            <dl className="merchant-guide-results">
              <div><dt>销售总览</dt><dd>这个月卖得怎么样，接下来先做什么。</dd></div>
              <div><dt>商品分析</dt><dd>哪些商品卖得好，哪些变化需要留意。</dd></div>
              <div><dt>搭配建议</dt><dd>哪些商品常一起买，适合搭配摆放或销售。</dd></div>
            </dl>
          </li>
        </ol>
      </>}

      <div className="merchant-guide-more">
        <h3>需要时再看</h3>
        {!dataOnly && <details><summary>销售表怎么准备？</summary><SalesTableHelp example /></details>}
        <details><summary>销售额、单价怎么选？</summary><p>表里已有每行销售额，就选择对应列；只有单价，就选择“销量 × 单价”；没有金额，也可以只分析销量。</p><p>如果同一笔订单的总金额在多行重复出现，请在“更多字段设置”中选择“使用订单总额，每单计一次”。</p></details>
        <details><summary>日期有漏记，或店铺有停业怎么办？</summary><p>确认内容时填写实际记录范围。漏记的日期填为“缺失日”，没有营业的日期填为“停业日”。不确定是否齐全时，不勾选完整记录。</p></details>
        <details><summary>下个月还要新建店铺吗？</summary><p>不用。进入原店铺，继续上传新月份的销售表即可。</p><p>要把多份表一起分析，在“更多 → 生成月报”中勾选需要的表；有重复日期时，按页面提示选择处理方式。</p></details>
        <details><summary>在哪里找以前的表格和月报？</summary><p>月报上方的下拉框可切换历史月报。顶部“数据记录”可查看上传过的表格；切换页面后仍保留所选月报。</p></details>
        <details><summary>如何查看客户与商品搭配分析？</summary><p>“搭配建议”展示可用的商品组合与依据；“更多分析”可检查数据质量，并根据适用条件运行 RF/RFM 客户分群和商品共购。历史结果按时间、类型与状态选择。</p></details>
        <details><summary>预测与备货参考怎么使用？</summary><p>在商品详情查看预测日期和历史检验结果，再填写预测起点的可靠库存与确定到货量。修改填写内容后重新确认计算；标为“上次保存”的数值对应此前输入。</p></details>
        <details><summary>怎样管理账号？</summary><p>使用用户名登录。右上角账号菜单可修改密码或退出；各账号分别管理自己的店铺。修改密码后，其他登录会话会退出。</p></details>
      </div>
    </div>
  </Drawer>
}
