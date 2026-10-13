import { Button } from 'antd'
import type { SalesProduct } from '../retail'

export function SalesAssistantQuestions({ product, disabled, onChoose }: { product?: SalesProduct; disabled: boolean; onChoose: (question: string) => void }) {
  const questions = product ? [
    '这件商品的销量有什么变化？',
    product.forecast ? '这件商品的七天销量预测有多可靠？' : '这件商品为什么没有销量预测？',
    product.anomaly_events?.length || product.anomalies.length ? '这件商品有哪些异常记录需要核对？' : product.forecast ? '这件商品能直接按预测数量备货吗？' : '这件商品目前能计算备货量吗？',
  ] : ['本月销售额变化主要来自哪些商品？', '哪些数据未计入本次分析？', '能从这份月报判断利润吗？']
  return <div className="sales-assistant-questions"><p>可以这样问（点击填入）</p>{questions.map(question => <Button key={question} disabled={disabled} onClick={() => onChoose(question)}>{question}</Button>)}</div>
}
