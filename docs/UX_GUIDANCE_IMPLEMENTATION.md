# 操作提示实现记录

改造前审查报告独立提交：`6c82ab2616104e8842052b99e11b1ea426f9a40d`。基线0.6.1，后端算法/schema保持。完成后的真实复测结果见 [验收报告](UX_GUIDANCE_ACCEPTANCE.md)，本文件不代替测试证据。

## 统一组件和内容

`frontend/src/components/HelpHint.tsx`提供按钮、短说明Popover和复杂Drawer；`frontend/src/helpContent.ts`集中42个主题，唯一ID对应原审查编号。`help.css`控制宽度、换行与可见焦点。普通按钮htmlType=button，避免表单提交；点击可展开，Escape/关闭说明/遮罩关闭后返回触发按钮，手机短主题也转为可滚动Drawer。复杂帮助push=false，不推开原操作抽屉；帮助不调用AI、不改字段、不清空表单。

## 交互缺陷处置

- UX19：分类卡片展示文件名、V数据版本与M字段版本，长文件名换行。
- UX20：匹配值/依据空白及同范围精确值重复就地提示规则编号，禁用确认与检查，保留移除操作。后端仍做最终校验。
- UX33：预测起点非当前日时醒目提示不要填今天库存，同时显示本次快照日期；保持原确认与公式。
- UX36：409及读取错误可读取最新记录而保留草稿，展示当前已保存文字，人工核对后再次保存；不自动覆盖。
- UX38：月报/商品分别提供真实可问问题，点击仅填问题，用户编辑后提问。
- UX46：站内指南按当前上传、分类、检查、月报、核查、库存、AI、导出、更多分析路径重写，主题复用。

不改变自动确认、金额、退款、分类优先级、预测/异常发布阈值、历史不可变、订单金额唯一、任务预算或资源限制。没有新增前端任意调参功能、模型依赖或中间件。

## 逐项对应

|审查编号|主题|处理|实现位置|
|---|---|---|---|
|UX01|按店铺组织项目|统一主题 UX01|ProjectEditor/ProjectLibrary|
|UX02|上传前准备与下一步|统一主题 UX02|ImportEditor|
|UX03|CSV编码与分隔符|统一主题 UX03|ImportEditor|
|UX04|Excel工作表合并|统一主题 UX04|ImportEditor|
|UX05|文件结构与业务记录粒度|统一主题 UX05|ImportEditor|
|UX06|映射建议与未知字段|统一主题 UX06|MappingEditor|
|UX07|商品编号、名称与分类|统一主题 UX07|MappingEditor|
|UX08|订单标识与订单边界|统一主题 UX08|MappingEditor|
|UX09|客户标识与隐私|统一主题 UX09|MappingEditor|
|UX10|时间格式与时区|统一主题 UX10|MappingEditor|
|UX11|数量与销售单位|统一主题 UX11|MappingEditor|
|UX12|单价、行金额与订单总额|统一主题 UX12|MappingEditor|
|UX13|币种与禁止自动换汇|统一主题 UX13|MappingEditor|
|UX14|取消、退货与未知状态|统一主题 UX14|MappingEditor|
|UX15|月汇总所属月份与能力|统一主题 UX15|MappingEditor|
|UX16|业务记录类型|统一主题 UX16|ClassificationEditor/SalesWorkspace|
|UX17|分类金额口径独立确认|统一主题 UX17|ClassificationEditor/SalesWorkspace|
|UX18|精确分类规则与依据|统一主题 UX18|ClassificationEditor/SalesWorkspace|
|UX19|追加文件分类卡片身份|界面处置 + 相关主题|ClassificationEditor/SalesWorkspace|
|UX20|空分类规则就地校验|界面处置 + 相关主题|ClassificationEditor/SalesWorkspace|
|UX21|完整覆盖与停业日期|统一主题 UX21|ClassificationEditor/SalesWorkspace|
|UX22|追加与重叠替换范围|统一主题 UX22|ClassificationEditor/SalesWorkspace|
|UX23|完全重复候选|统一主题 UX23|ClassificationEditor/SalesWorkspace|
|UX24|数据检查与多视图排除|统一主题 UX24|QualityWorkspace/QualityReport/SalesWorkspace|
|UX25|更多分析的范围与金额来源|统一主题 UX25|QualityWorkspace/QualityReport/SalesWorkspace|
|UX26|金额不完整客户的RFM范围|统一主题 UX26|QualityWorkspace/QualityReport/SalesWorkspace|
|UX27|月报指标与销售额边界|统一主题 UX27|SalesWorkspace|
|UX28|月度比较与日趋势限制|统一主题 UX28|SalesWorkspace|
|UX29|重点商品与最多三条行动|统一主题 UX29|SalesWorkspace|
|UX30|异常日期与历史中位数|统一主题 UX30|SalesWorkspace|
|UX31|七天参考与拒绝预测|统一主题 UX31|SalesWorkspace|
|UX32|预测回测误差与方法|统一主题 UX32|SalesWorkspace|
|UX33|库存快照日期与历史数据|界面处置 + 相关主题|SalesWorkspace|
|UX34|可售库存与确定到货|统一主题 UX34|SalesWorkspace|
|UX35|备用量、包装单位与公式|统一主题 UX35|SalesWorkspace|
|UX36|核查备注与并发冲突恢复|界面处置 + 相关主题|ProductNote|
|UX37|AI证据、澄清与回退|统一主题 UX37|SalesWorkspace（原FieldAssistant保持，映射建议解释由UX06补充）|
|UX38|可选择的问题示例|界面处置 + 相关主题|SalesWorkspace（原FieldAssistant保持，映射建议解释由UX06补充）|
|UX39|RF/RFM客户画像|统一主题 UX39|QualityReport|
|UX40|群数与分群诊断|统一主题 UX40|QualityReport|
|UX41|商品共购适用条件|统一主题 UX41|QualityReport|
|UX42|支持度、置信度、提升度|统一主题 UX42|QualityReport|
|UX43|数据版本、字段版本与历史报告|统一主题 UX43|DataWorkspace/SalesWorkspace|
|UX44|导出格式与完整数据|统一主题 UX44|DataWorkspace/SalesWorkspace|
|UX45|任务排队、取消与失败|统一主题 UX45|DataWorkspace/SalesWorkspace|
|UX46|站内使用指南更新|界面处置 + 相关主题|Guide|

## 键盘与响应式修复

真实复测发现初次断点初始化导致帮助容器切换丢失焦点，以及768px轻提示超出右边界，分别修复于14161c3与317a2c4。最终追加Tab测试发现嵌套抽屉焦点离开当前帮助，修复于a673a44。所有帮助在正文范围循环Tab，Escape只关闭帮助，原表单继续保留；遮罩、标题关闭和正文关闭都返回触发按钮。112.124秒的最终真实浏览器专项11组PASS、42主题全覆盖。失败日志和截图保留，没有用旧PASS替代。

版本0.6.2统一应用API、任务manifest、pyproject及前端包元数据；此前pyproject/任务manifest仍写0.6.0，这次修正新运行的版本记录。schema5、sales-v2.2.0及旧报告文件保持。原字段CPU解释功能并未新增智能确认；新示例按钮仅位于销售助手。
