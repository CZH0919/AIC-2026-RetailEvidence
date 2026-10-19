import { HelpHint } from './HelpHint'
import { Alert, Button, Checkbox, Input, Select } from 'antd'
import type { ClassificationPolicy, ClassificationRule, SourceInfo } from '../retail'
const kinds = [{value:'physical_product',label:'实物商品'},{value:'shipping_service',label:'运费/服务'},{value:'manual_adjustment',label:'人工调整'},{value:'other',label:'其他'},{value:'pending',label:'待确认'}]
const amounts = [{value:'include',label:'计入销售额'},{value:'exclude',label:'不计入销售额'},{value:'pending',label:'金额语义待确认'}]
export function classificationProblems(value: ClassificationPolicy): string[] {
  const problems: string[] = [], keys = new Set<string>()
  value.rules.forEach((r, i) => {
    if (!r.value.trim()) problems.push(`第${i + 1}条：填写原始匹配值，或移除不用的规则。`)
    if (!r.basis.trim()) problems.push(`第${i + 1}条：填写你确认类型和金额的依据。`)
    const key = JSON.stringify([r.match_by, r.value])
    if (keys.has(key)) problems.push(`第${i + 1}条：相同范围与匹配值已存在，请保留一条规则。`)
    keys.add(key)
  })
  return problems
}
export function ClassificationEditor({source, sourceLabel, value, onChange}:{source:SourceInfo; sourceLabel?:string; value:ClassificationPolicy; onChange:(v:ClassificationPolicy)=>void}) {
  const problems = classificationProblems(value)
  const rule = (index:number, patch:Partial<ClassificationRule>) => onChange({...value, confirmed:false, rules:value.rules.map((r,i)=>i===index?{...r,...patch}:r)})
  return <section className="classification-editor">
    <h4>确认记录类型 · 字段版本 {source.mapping_revision}</h4><p className="classification-source">{sourceLabel ?? `数据 ${source.version_id.slice(0,8)}`} · M{source.mapping_revision}</p><HelpHint topic="UX16" context="销量、商品列表与备货只包含已确认实物。金额是否计入需另行确认；不清楚的记录请保留待确认。修改后须重新检查并生成新月报，旧报告保留。" />
    <p>不清楚的记录保留“待确认”。</p>
    <label>其余记录类型<Select aria-label="其余记录类型" style={{width:'100%'}} value={value.default_kind} options={kinds} onChange={v=>onChange({...value, default_kind:v,confirmed:false})}/></label>
    <HelpHint topic="UX17" /><label>其余记录金额口径<Select aria-label="其余记录金额口径" style={{width:'100%'}} value={value.default_amount_treatment} options={amounts} onChange={v=>onChange({...value, default_amount_treatment:v,confirmed:false})}/></label>
    <HelpHint topic="UX18" />{problems.length > 0 && <Alert type="warning" showIcon title="请先补全分类规则" description={problems.slice(0,10).map(p => <p key={p}>{p}</p>)} />}{value.rules.map((r,i)=><div key={i} className="classification-rule">
      <h5>规则 {i+1}</h5>
      <label><span>匹配范围</span><Select aria-label={`匹配范围 ${i+1}`} value={r.match_by} options={[{value:'item_id',label:'商品编号精确匹配'},{value:'category',label:'已映射类型/分类精确匹配'},{value:'source_row_id',label:'来源行编号精确匹配'}]} style={{width:'100%'}} onChange={v=>rule(i,{match_by:v})}/></label>
      <label><span>匹配值</span><Input aria-label={`匹配值 ${i+1}`} value={r.value} onChange={e=>rule(i,{value:e.target.value})} placeholder="原始编号或已映射类型值" maxLength={200}/></label>
      <label><span>记录类型</span><Select aria-label={`记录类型 ${i+1}`} value={r.kind} options={kinds} style={{width:'100%'}} onChange={v=>rule(i,{kind:v})}/></label>
      <label><span>金额口径</span><Select aria-label={`金额口径 ${i+1}`} value={r.amount_treatment} options={amounts} style={{width:'100%'}} onChange={v=>rule(i,{amount_treatment:v})}/></label>
      <label className="classification-rule-basis"><span>分类依据</span><Input aria-label={`分类依据 ${i+1}`} value={r.basis} onChange={e=>rule(i,{basis:e.target.value})} placeholder="确认依据" maxLength={300}/></label>
      <Button className="classification-rule-remove" onClick={()=>onChange({...value,confirmed:false,rules:value.rules.filter((_,j)=>i!==j)})}>移除这条规则</Button>
    </div>)}
    {!!source.classification_suggestions?.length && <p>以上特殊编码来自该 UCI 数据源的建议，仍需你确认类型和金额口径；不会自动套用到其他上传表。</p>}
    {!!source.category_values?.length && <p>已映射分类值：{source.category_values.slice(0,20).join('、')}（行编号规则优先于商品编号，其次为分类，其余使用默认口径）</p>}
    <Button onClick={()=>onChange({...value,confirmed:false,rules:[...value.rules,{match_by:'item_id',value:'',kind:'pending',amount_treatment:'pending',basis:'用户确认'}]})}>添加分类规则</Button>
    <Checkbox disabled={problems.length > 0} checked={value.confirmed} onChange={e=>onChange({...value,confirmed:e.target.checked})}>我已核对本数据版本的记录类型及金额口径，待确认项保留不猜测</Checkbox>
  </section>
}
