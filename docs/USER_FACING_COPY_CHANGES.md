# 用户可见文案改造记录（0.6.3）

审查基线530791b（0.6.2）；原始审计先独立提交511e810966689f7fa4d8fe8b67b96608f40444e7，之后才修改产品。实现d50fbfd、正常进货提问修正cf4c26a、月报概览证据提示修正ae6b4d。原始AUDIT及before证据没有覆盖。

32项均有本轮处理与对应验证：5P0、19P1、8P2；主处置为8功能修复、20改写、3移入按需详情、1删除。另保留8类必要概念，不将它们当成待删除缺陷：利润限制、缺失/退款/分类、预测误差与基线、真实AI与程序说明、数据/字段/运行与来源、RF/RFM与支持度、文件格式、原始用户输入。

## 工程与真实行为

- `frontend/src/productCopy.ts`集中状态、时间及展示用质量解释；SalesWorkspace清除上次成功状态，FieldAssistant明确人确认列名；42帮助内容仅改已审查话术。
- QualityReport主区使用购买习惯与中文指标，候选表/共购评测置于原生可键盘操作details；坏质量提示和热门方法比较保留。DataWorkspace/MappingEditor保存值与校验不变。
- `backend/app/assistant_output.py`完整校验结构、引用、内部自述与无依据库存断言；不删除单词、不截断输出。`sales_answer.py`解释已经计算的预测、异常、概念与服务范围，明确ai_used=false。正常销售概览、字段和商品问答继续真实模型。
- retail_api的sales-explain-v6只给本问题需要的证据；字段助手fieldprompt-v2。程序仍绑定数字与原商品名。诱导商品/列名原文不丢失，也不成为系统指令。
- 导出只将分类SHA移入“报告复核信息”，HTML、CSV、JSON及manifest数字/来源合同不变；9项核心算法/数据/数据库文件与基线逐SHA相同，无schema迁移。

## 每条原文、改后文案与证据

完整机器记录：[issue_dispositions.json](verification/user_facing_copy/after/issue_dispositions.json)。下面所有P0/P1均有文字对比，截图仅来自实际浏览器。帮助文案是已打开过的42主题集中定义，不冒称每句都有单独截图。

### COPY-01 · P0 · 商品AI问答 · FIXED

原文：这件商品值得关注是因为销量和销售额较高，但可能存在库存不足的情况。建议先核对销售记录和库存情况，再决定是否补货。核对事项包括销售记录、库存和到货时间。

处置：功能修复。改后：月底最后 7 天售出 5933 原始商品单位，前 7 天为 14 原始商品单位。 本月有 6 天的销量偏离历史表现，建议核对原因。 这是销售记录中的变化，不能据此断定缺货或促销原因；请查看异常日期及原始记录。

源码：`backend/app/retail_api.py`。前证据：`before/copy_ai_questions/Q02`；后证据：`after/copy_ai_questions/Q02.png`。

### COPY-02 · P0 · 七天预测AI问答 · FIXED

原文：销量预测是根据已确认的销售额和销量计算得出的。核对销售记录、库存和到货时间是进货前的必要步骤。核对下降原因，不要直接减少进货。

处置：功能修复。改后：本商品采用过去四周平均参考，参考最近四周的销售记录估计七天累计销量。2011-11-01至2011-11-07约1,495.75原始商品单位；历史验证中七天总量平均差约291.42原始商品单位。预测不能直接等同采购量；还要核对预测起点的可售库存、确定到货、备用量和包装单位。销售表不能自动确认这些库存信息，也不保证不会缺货。

源码：`backend/app/retail_api.py`。前证据：`before/copy_ai_questions/Q05`；后证据：`after/copy_ai_questions/Q05.png`。

### COPY-03 · P0 · 模型错误响应 · FIXED

原文：我是开发助手，我将按照系统提示词要求处理，随后展示服务器内部文件路径。

处置：功能修复。改后：这次解释未通过核对，请以月报中的计算结果为准。内部自述整条拒绝，未截取其中正常句。

源码：`backend/app/retail_api.py / backend/app/field_assistant.py`。前证据：`before/copy_faults/internal`；后证据：`after/copy_faults/internal.png`。

### COPY-04 · P0 · 模型输出结构 · FIXED

原文：本月销量为626,765，请结合本次月报核对销售记录。

处置：功能修复。改后：包含额外内部计划字段的对象整条拒绝；answer/references之外不接受其他键。

源码：`backend/app/retail_api.py`。前证据：`before/copy_faults/extra_fields`；后证据：`after/copy_faults/extra_fields.png`。

### COPY-05 · P0 · 连续AI提问失败 · FIXED

原文：CPU 模型实际推理
暂时无法连接，请检查连接后重试。

处置：功能修复。改后：提问未完成。暂时无法连接，请检查连接后重试。

源码：`frontend/src/components/SalesWorkspace.tsx`。前证据：`before/copy_status/ai_request_error`；后证据：`after/copy_status/ai_request_error.png`。

### COPY-06 · P1 · 复合AI提问 · FIXED

原文：不能只凭销售变化判断是否缺货。这份营业表没有当前库存记录，请核对对应日期的库存、到货和销售记录。

处置：功能修复。改后：本商品采用过去四周平均参考，参考最近四周的销售记录估计七天累计销量。2011-11-01至2011-11-07约1,495.75原始商品单位；历史验证中七天总量平均差约291.42原始商品单位。预测不能直接等同采购量；还要核对预测起点的可售库存、确定到货、备用量和包装单位。销售表不能自动确认这些库存信息，也不保证不会缺货。

源码：`backend/app/retail_api.py`。前证据：`before/copy_ai_questions/Q07`；后证据：`after/copy_ai_questions/Q07.png`。

### COPY-07 · P1 · 概念与跨分析AI提问 · FIXED

原文：没有客户数据，无法进行客户分群。核对销售记录、库存和到货时间，再决定是否补货。核对下降原因，不要直接减少进货。

处置：功能修复。改后：客户分群需要稳定的客户编号、订单和购买时间；加入购买金额还需要可靠的金额记录。缺少这些信息时不能可靠分组。请到“更多分析”查看这份数据的实际适用条件，销售月报不能代替那里的数据检查。 支持度表示全部购物篮中两件商品一起出现的比例；置信度表示买了前一件商品的篮子中，也有后一件的比例。提升度与后一件平时的出现比例比较，较高也不代表因果或经营收益。共购结果还要看样本数与质量检查。

源码：`backend/app/retail_api.py`。前证据：`before/copy_ai_questions/Q08`；后证据：`after/copy_ai_questions/Q08.png`。

### COPY-08 · P1 · 销售助手标签 · FIXED

原文：CPU 模型实际推理；模型超时，使用证据回退；模型不可用，使用证据回退；证据模板回退

处置：改写。改后：AI 辅助解释 / 计算依据说明 / 使用说明 / 问题超出范围 / 回答等待超时 · 预设说明 / 解释未通过核对 · 预设说明

源码：`frontend/src/components/SalesWorkspace.tsx`。前证据：`before/ux_candidate_journey/06_real_cpu_ai`；后证据：`after/copy_ai_questions/Q01.png`。

### COPY-09 · P1 · 字段理解助手 · FIXED

原文：本地 CPU AI 解释列名建议；没有发送原始记录，业务含义仍由你确认。
CPU AI 字段解释

处置：改写。改后：AI 帮你理解列名建议，只使用列名和问题，不发送原始明细；字段含义仍需你确认。

源码：`frontend/src/components/FieldAssistant.tsx`。前证据：`before/ux_candidate_journey/01_field_cpu_ai`；后证据：`after/ux_candidate_journey/01_field_cpu_ai.png`。

### COPY-10 · P2 · 未知字段帮助UX06 · FIXED

原文：列名建议只是规则匹配；字段助手另显示是否有CPU模型解释。任何建议都需要你核对原始含义。

处置：改写。改后：{"id": "UX06", "title": "映射建议与未知字段", "label": "不确定怎么办？", "pages": ["字段与口径 / 自动对应建议、确认复选框"], "drawer": true, "sections": [{"title": "这是什么", "text": "列名建议根据名称匹配，字段助手会标明是否有AI解释；任何建议都需要你核对原表含义。"}, {"title": "如何选择", "text": "一列只对应一种含义。不知道的字段清空，暂存草稿；不能为了通过校验随意对应。"}, {"title": "例如", "text": "会员号可对应客户标识，收银员号不能。"}, {"title": "没有数据时", "text": "缺客户不能分群；缺订单边界不能做可靠共购；缺日时间不能做日趋势、异常和七天预测。"}, {"title": "请留意", "text": "错误确认会固定错误的数据含义，影响后续全部计算。"}]}

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_help_final/results.json`；后证据：`after/help_content.json（UX06；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-11 · P1 · 库存帮助UX33 · FIXED

原文：显著显示预测起点；日期不是今天时提示历史/未来参考。实时备货请使用近期真实销售资料生成相应报告。

处置：改写。改后：{"id": "UX33", "title": "库存快照日期与历史数据", "label": "该填哪天库存？", "pages": ["商品详情 / 可售库存确认日期"], "drawer": true, "sections": [{"title": "这是什么", "text": "库存必须是预测起点那一天、同商品同单位的可售库存。历史报告不能配上今天的库存。"}, {"title": "如何选择", "text": "先看页面中的预测起点，再填写那一天的库存。要为当前经营备货，请用近期销售资料生成报告。"}, {"title": "例如", "text": "2011-11-01起点只能核对当日库存，不可填写今天店里10瓶。"}, {"title": "没有数据时", "text": "没有该日可靠库存就不要确认，不计算补货数量。"}, {"title": "请留意", "text": "日期错配会产生没有现实意义的采购参考。"}]}

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_help_final/help_UX33_1440`；后证据：`after/help_content.json（UX33；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-12 · P1 · 备注帮助UX36 · FIXED

原文：提供读取最新记录的明确操作，保留当前草稿，展示他人最新文字，核对后由用户再次保存。

处置：改写。改后：{"id": "UX36", "title": "核查备注与他人更新", "label": "备注如何核对？", "pages": ["商品详情 / 备注、日期、保存失败"], "drawer": false, "sections": [{"title": "这是什么", "text": "备注是店主核查记录，不改变月报统计和预测；未知原因不要猜。多人修改时系统保护较新版本。"}, {"title": "如何选择", "text": "遇到他人已更新的提示，点击“读取最新记录，保留我的草稿”，核对两份内容后再保存。"}, {"title": "例如", "text": "A已保存促销核查，B不能直接覆盖；先读A记录再决定自己的说明。"}, {"title": "没有数据时", "text": "未查清选尚不清楚；不要把系统报警改成已证实缺货。"}]}

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_task_paths/F_note_conflict_recovered`；后证据：`after/help_content.json（UX36；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-13 · P1 · 备注帮助的内部影响说明 · FIXED

原文：无恢复操作会丢失工作进度或促使用户刷新丢草稿。

处置：删除。改后：删除“无恢复操作会……”内部影响说明；保留冲突发生时读取最新记录和保留草稿的操作指导。

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_help_final/results.json`；后证据：`after/help_content.json（UX36；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-14 · P1 · AI帮助UX37 · FIXED

原文：数字由程序计算。CPU模型只解释本次月报证据；需要澄清、数据限制、不可用、超时或证据核验失败会明确标记。
模型不可用时有证据回退，仍可使用月报；稍后再试，不用反复生成报告。

处置：改写。改后：{"id": "UX37", "title": "理解回答与预设说明", "label": "回答能相信吗？", "pages": ["字段助手、销售助手 / 状态与回答"], "drawer": true, "sections": [{"title": "这是什么", "text": "数字来自月报计算。AI只辅助解释本次证据；数据不足、回答未完成或解释未通过核对时，会说明原因。"}, {"title": "如何选择", "text": "看回答状态，点依据核对。涉及某件商品先打开详情；字段建议仍须人工确认。"}, {"title": "例如", "text": "问为什么留意某件商品可以解释已知变化；不能自动知道利润、今日库存或异常原因。"}, {"title": "没有数据时", "text": "助手暂不可用时显示预设说明，已有月报仍可查看；稍后重试，不用反复生成报告。"}, {"title": "请留意", "text": "AI不能确认未知业务事实；预设说明没有完成AI回答，不能据此补造结论。"}]}

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_help_final/results.json`；后证据：`after/help_content.json（UX37；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-15 · P1 · 分群帮助UX40 · FIXED

原文：诊断保留只供核查，不为好看降低门槛。

处置：改写。改后：{"id": "UX40", "title": "分组数量与质量检查", "label": "这些指标是什么？", "pages": ["更多分析 / 选择K、轮廓系数、ARI"], "drawer": false, "sections": [{"title": "这是什么", "text": "K是分成几个群；轮廓系数衡量群间区分，ARI衡量重复分组稳定性。这里用于质量门槛，不是经营收益或准确率。"}, {"title": "如何选择", "text": "先看结果是否通过质量检查及原因，再比较各组的购买习惯；系统使用固定分析设置。"}, {"title": "例如", "text": "G1只是第一群，K4表示4群；指标通过也需店主核实可否行动。"}, {"title": "没有数据时", "text": "未通过质量检查的分组只供核查，不宜据此制定经营策略。"}, {"title": "请留意", "text": "把诊断指标当客户预测准确率会夸大效果。"}]}

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_help_final/results.json`；后证据：`after/help_content.json（UX40；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-16 · P1 · 共购帮助UX41 · FIXED

原文：真实Groceries9835篮可分析；只有商品月总量不能还原谁一起买。

处置：改写。改后：{"id": "UX41", "title": "商品共购适用条件", "label": "为什么不能共购？", "pages": ["更多分析 / 共购按钮、资源限制"], "drawer": true, "sections": [{"title": "这是什么", "text": "共购需要真实完整购物篮，只说明同一篮子中一起出现。数据过大、篮子不完整或样本不足会限制分析。"}, {"title": "如何选择", "text": "先看质量卡原因，在清洗策略选择合适的日期或数据；不要为了少商品而破坏每单完整性。当前使用固定参数。"}, {"title": "例如", "text": "同一张小票的牛奶和面包可组成购物篮；只有每月各商品总销量，无法知道是否一起购买。"}, {"title": "没有数据时", "text": "缺订单边界不要捏造购物篮，可做销售复盘。"}, {"title": "请留意", "text": "不能把商品销量高当一起买，也不能将相关关系当因果。"}]}

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_help_final/results.json`；后证据：`after/help_content.json（UX41；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-17 · P2 · 共购帮助UX42 · FIXED

原文：Hit@5表示用最多五个候选尝试补回留出的商品，命中率不是销售收益。覆盖率表示能给出候选的测试篮比例；与热门法一起看，规则未必更好。

处置：改写。改后：{"id": "UX42", "title": "支持度、置信度、提升度", "label": "如何理解规则？", "pages": ["共购结果 / 规则和评估"], "drawer": false, "sections": [{"title": "这是什么", "text": "支持度是全部分析篮中A与B一起出现比例；置信度是含A篮中也含B比例；提升度把此比例与B平时出现比例比较。"}, {"title": "如何选择", "text": "先看样本数、独立测试与是否建议发布；大于1表示相对更常一起出现，不证明A导致B购买。"}, {"title": "例如", "text": "100篮中10篮含A且6篮含B，则A→B置信度60%、支持度6%；若B平时20%，提升度3。"}, {"title": "没有数据时", "text": "历史关系可能随季节变化；无真实试验不能宣称营业额增长。"}, {"title": "请留意", "text": "规则不是必买组合或利润保证；测试命中率也不是异常识别准确率。"}, {"title": "如何看评测", "text": "“前五候选命中率”表示最多推荐五件商品时，能否找回测试中隐藏的商品；这不是实际购买率或经营收益。覆盖率是能给建议的比例，也要比较热门商品方法。"}]}

源码：`frontend/src/helpContent.ts`。前证据：`before/ux_help_final/results.json`；后证据：`after/help_content.json（UX42；42主题真实打开/关闭见after/ux_help_final/results.json）`。

### COPY-18 · P1 · 客户分群简介 · FIXED

原文：使用通过质量检查的订单视图，生成可复核的 RF/RFM 群体画像。

处置：改写。改后：按客户的购买习惯分组，帮助核对近期购买、购买次数和金额；分组不等于已经验证的客户标签。

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_RFM`；后证据：`after/copy_ui_review/分组质量详情_desktop.png`。

### COPY-19 · P1 · 客户分群表头 · FIXED

原文：R 中位数；F 中位数；M 中位数

处置：改写。改后：距最近购买天数（中位数）、购买次数（中位数）、购买金额（中位数）

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_RFM`；后证据：`after/copy_ui_review/分组质量详情_desktop.png`。

### COPY-20 · P2 · 分组概览 · FIXED

原文：选择 K；可发布画像；不建议发布

处置：改写。改后：分组数量、通过质量检查、仅供核查

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_RFM`；后证据：`after/copy_ui_review/分组质量详情_desktop.png`。

### COPY-21 · P1 · 分群质量候选表 · FIXED

原文：K；最小群体；轮廓系数；ARI 中位数；判定；诊断保留

处置：移动。改后：主结果保留业务分组；点击“分组质量详情”展开所有候选数值和未发布原因。

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_RFM`；后证据：`after/copy_ui_review/分组质量详情_desktop.png`。

### COPY-22 · P1 · 商品共购简介 · FIXED

原文：从完整购物篮中挖掘规则，并用固定留出篮评测 Top-5 补全。

处置：改写。改后：核对购物篮中常同时出现的商品；关系不代表因果或促销收益。

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_association`；后证据：`after/copy_ui_review/共购质量详情_desktop.png`。

### COPY-23 · P1 · 商品共购规则表 · FIXED

原文：前件；后件；Lift

处置：改写。改后：已购买商品、常同时出现的商品、支持度、置信度、提升度

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_association`；后证据：`after/copy_ui_review/共购质量详情_desktop.png`。

### COPY-24 · P1 · 商品共购评测表 · FIXED

原文：集合；评测篮；规则 Hit@5；规则覆盖率；热门 Hit@5

处置：移动。改后：点击“共购质量详情”查看前五候选命中率、可给建议的比例、热门方法对照；不是实际购买率。

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_association`；后证据：`after/copy_ui_review/共购质量详情_desktop.png`。

### COPY-25 · P2 · 质量去向说明 · FIXED

原文：每一行在每个视图中仅归入一个主要原因，各视图的纳入与排除之和均等于原始行数。

处置：改写。改后：以订单/商品核查范围说明去向，保留原始行、订单和金额差异。

源码：`frontend/src/components/QualityReport.tsx`。前证据：`before/ux_analysis_paths/I_quality_scope`；后证据：`after/ux_analysis_paths/I_quality_scope.png / I_RF.txt`。

### COPY-26 · P2 · 质量金额缺失说明 · FIXED

原文：金额不完整客户未进入 RFM 视图，RF 仍保留符合条件的客户。

处置：改写。改后：客户购买金额记录不足时无法可靠计算购买金额分组，请核对金额或使用最近购买与频次。

源码：`frontend/src/components/QualityReport.tsx / backend/app/quality.py`。前证据：`before/ux_analysis_paths/I_RFM`；后证据：`after/ux_analysis_paths/I_quality_scope.png / I_RF.txt`。

### COPY-27 · P1 · 已确认字段时间口径 · FIXED

原文：ISO / Excel 日期；%Y-%m-%d；Europe/London

处置：改写。改后：日期和时区显示中文业务名称；原保存格式值不变。

源码：`frontend/src/components/DataWorkspace.tsx`。前证据：`before/ux_help_final/results.json`；后证据：`after/ux_input_paths/C_xlsx_mapping.png`。

### COPY-28 · P2 · 时间格式选项 · FIXED

原文：ISO 日期 / Excel 日期；UTC；Excel日期按ISO/Excel选项读取。

处置：改写。改后：表格日期 / 标准日期时间；世界标准时间（UTC）。

源码：`frontend/src/components/MappingEditor.tsx / frontend/src/helpContent.ts`。前证据：`before/ux_input_paths/C_daily_mapping`；后证据：`after/ux_input_paths/C_xlsx_mapping.png`。

### COPY-29 · P2 · 导出分类金额附件 · FIXED

原文：分类配置 SHA-256:

处置：移动。改后：报告复核信息（点击展开），保留相同分类配置SHA-256；金额分项仍直接显示。

源码：`backend/app/retail_export.py`。前证据：`before/ux_candidate_journey/report.html`；后证据：`after/copy_ui_review/export_proof_unchanged.png`。

### COPY-30 · P2 · 处理状态 · FIXED

原文：正在检查；检查完成；客户分群已完成，请查看群体画像和诊断。

处置：改写。改后：正在处理、处理完成、客户分群已完成，请查看购买习惯与分组质量。

源码：`frontend/src/quality.ts / backend/app/task_runner.py`。前证据：`before/ux_analysis_paths/I_RFM`；后证据：`after/ux_analysis_paths/I_quality_scope.png / I_RF.txt`。

### COPY-31 · P1 · AI失败原因说明 · FIXED

原文：AI 暂时无法回答。可以查看商品详情和对应依据，月报计算结果不受影响。

处置：改写。改后：超时、不可用、未通过核对分别说明原因，仍可核对月报；不暴露异常栈。

源码：`backend/app/retail_api.py / backend/app/field_assistant.py`。前证据：`before/copy_faults/timeout`；后证据：`after/copy_faults/timeout.png`。

### COPY-32 · P1 · 非经营请求 · FIXED

原文：Q10、Q11：AI 暂时无法回答。可以查看商品详情和对应依据，月报计算结果不受影响。
Q12：销售记录、库存和到货时间需要核对；核对后决定是否补货。

处置：功能修复。改后：销售助手用于解释销售数据，不能提供内部指令、服务器信息或执行开发操作。你可以询问本月销售情况或商品变化。

源码：`backend/app/retail_api.py / backend/app/field_assistant.py`。前证据：`before/copy_ai_questions/Q10`；后证据：`after/copy_ai_questions/Q10.png`。

