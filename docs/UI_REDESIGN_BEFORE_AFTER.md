# 三类样板：同报告前后对照

2026-10-19；基线160a90c，最终样板7b61d84，应用仍0.6.3。下列均实际运行截图，完全模拟数据，无Mock、设计贴图或私人商户资料。原图完整清单见verification/ui_redesign/screenshot_manifest.json，全部40张位于D任务evidence/before_v2、after_v2及远端同目录；仓库仅选取14张供评审。1440/1280/768/390均测试，正常/受限/错误证据另见验收。

固定项目8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a，版本079c4221-28b1-460c-9df2-be174312d824，run35cf3631-064c-4a90-a845-b06485eb9a3e，2026-09。截图宽度记录在文件名，高1000视口；月报/商品为fullPage，详情/分类为当前视口，超出部分可在原抽屉滚动。

## 实际入口

- [原版月报](http://127.0.0.1:18110/projects/8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a?run=35cf3631-064c-4a90-a845-b06485eb9a3e)
- [样板月报](http://127.0.0.1:18111/projects/8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a?run=35cf3631-064c-4a90-a845-b06485eb9a3e)
- [样板商品列表](http://127.0.0.1:18111/projects/8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a/products?run=35cf3631-064c-4a90-a845-b06485eb9a3e)，搜索P006后点击食用油500ml看详情。
- [样板分类表单](http://127.0.0.1:18111/projects/8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a?run=35cf3631-064c-4a90-a845-b06485eb9a3e&compose=1)。截图测试临时清除已有规则后填两条实物精确规则，均未保存；可自行添加规则查看布局，原报告不变。
- 受限状态：项目af729623-6e6a-436b-b7fc-4ebdfa6b5a31/run6192b66d-22e1-4c35-b47c-32788e76fb00为月汇总，无日曲线；错误状态在分类添加空规则，原检查/生成门槛保持。

## 1. 销售月报，1440

统一指标表面和数值、减少页头空间、品牌链接/细线分组。金额分项、风险/未知提示仍在指标前；原月份/历史/生成/导出/帮助/更多分析入口均保留。

|改前|改后|
|---|---|
|![月报前](ui_redesign_images/before_v2_1440_report.png)|![月报后](ui_redesign_images/after_v2_1440_report.png)|

## 2. 商品列表和详情，1440

保留完整表格，数字右齐，说明可换行且完整；局部横滚，不转成商品卡。详情中本月数值、异常/原始记录、七天参考、库存/备注/AI/依据保持原次序，叠层不变。

|改前|改后|
|---|---|
|![商品前](ui_redesign_images/before_v2_1440_products.png)|![商品后](ui_redesign_images/after_v2_1440_products.png)|
|![详情前](ui_redesign_images/before_v2_1440_detail.png)|![详情后](ui_redesign_images/after_v2_1440_detail.png)|

## 3. 业务分类规则，1440

每条规则有可见标题/五个标签，桌面两列，窄屏原DOM顺序单列；删除/新增/确认仍在原流程。不更改类型/金额含义、匹配优先级、版本冻结、错误校验或旧报告。

|改前|改后|
|---|---|
|![分类前](ui_redesign_images/before_v2_1440_classification.png)|![分类后](ui_redesign_images/after_v2_1440_classification.png)|

## 4. 窄屏与错误状态

390月报保持14px正文，主要数字26px；历史选择整行，原操作均有文字。分类错误提示和禁用态保留，不靠隐藏错误换整洁。

|改前|改后|
|---|---|
|![390前](ui_redesign_images/before_v2_390_report.png)|![390后](ui_redesign_images/after_v2_390_report.png)|
|![错误前](ui_redesign_images/before_v2_390_classification_error.png)|![错误后](ui_redesign_images/after_v2_390_classification_error.png)|
|![768前](ui_redesign_images/before_v2_768_report.png)|![768后](ui_redesign_images/after_v2_768_report.png)|

样板已完成工程回归，**审美尚未批准**。请重点判断青绿/中性表面比例、密度、字号、表格与规则表单是否适合日常使用。确认后再推广到项目库、导入/映射、质量与更多分析等其余页面；此处不把三页样板称为全站完成。
