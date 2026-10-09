# 功能与验收追踪矩阵

2026-10-09；下表为真实已执行候选轮次，不冒充最终main复验。历史记录和本次结果分别记录；完整参数、日期、数据哈希、预期/实际、缺陷处置见acceptance_matrix.csv。37项核心候选PASS、3项外部BLOCKED、1项NOT_RUN、3项旧争议NOT_APPLICABLE。最终发布状态另见ACCEPTANCE_REPORT与release证据。

|测试ID|范围|需求/界面|实际实现文件|历史证据|本次状态|本次证据/缺口|优先级|
|---|---|---|---|---|---|---|---|
|REQ-01|v2.1必需|明细/日汇总/月汇总及字段语义确认 / 数据记录/映射/确认侧栏|data_schemas.py,mapping.py,MappingEditor.tsx,SalesWorkspace.tsx|R1;real_edges_handoff/real_edges.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-02|v2.1必需|完整覆盖/金额/单位/币种/月份确认 / 映射与确认侧栏|mapping.py,retail_schemas.py,retail_engine.py|R1;public_acceptance_handoff/manifest.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-03|v2.1必需|重复导入、追加重叠、替换与版本冻结 / 数据记录/历史月报|data_api.py,import_jobs.py,retail_engine.py|S02;R1|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-04|v2.1必需|检查后生成月报/排队/取消/修改 / 确认侧栏/运行状态|retail_api.py,task_runner.py,SalesWorkspace.tsx|R1;R3|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-05|v2.1必需|2011-10原始数据独立对账 / 月报关键数字|retail_engine.py,accept_sales_public.py|public_acceptance_handoff/acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-06|v2.1必需|日/月派生格式可追溯与同口径对账 / 汇总导入/月报|retail_engine.py,verify_sales_real_edges.py|real_edges_handoff/real_edges.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-07|v2.1必需|退款/取消/整单金额不重计/金额缺失 / 数据检查/金额标签|amounts.py,retail_engine.py|R1;public_acceptance_handoff/acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-08|v2.1必需|首月/缺客户/订单/时间/单价降级 / 月报/能力提示|retail_engine.py,data_schemas.py|real_edges_handoff/real_edges.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-09|v2.1必需|完整商品/待关注集合/五件摘要/最多三行动 / 月报/商品明细|retail_engine.py,SalesWorkspace.tsx|R1;browser_20261009/browser_acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-10|v2.1必需|搜索排序筛选/详情返回/滚动状态 / 商品明细/详情侧栏|SalesWorkspace.tsx,RetailProjectSpace.tsx|R3|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-11|v2.1必需|异常日原始行与来源版本哈希 / 商品详情/原始记录|retail_api.py,retail_engine.py|browser_20261009/browser_acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-12|v2.1必需|人工原因备注与expected_revision冲突 / 商品/行动备注|ProductNote.tsx,retail_api.py,models.py|browser_20261009/browser_acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-13|v2.1必需|七天累计预测/时间切分/目标窗口无泄漏 / 商品详情/依据|sales_mining.py|public_acceptance_handoff/sales_backtests.csv|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-14|v2.1必需|上一周/四周平均/复杂法对照及覆盖分母 / 预测依据/拒绝原因|sales_mining.py,retail_engine.py|R2;public_acceptance_handoff/acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-15|v2.1必需|Isolation Forest/中位数规则/无标签报警 / 异常详情/核对|sales_mining.py|R2;public_acceptance_handoff/acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-16|v2.1必需|库存未知不测算/确认库存时间单位/在途 / 商品详情/库存参考|retail_schemas.py,retail_api.py|R2;browser_20261009/browser_acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-17|v2.1必需|真实CPU AI与evidence/run/版本绑定 / AI侧栏|retail_api.py,retail_engine.py|ai_verification_handoff.json;browser_20261009/browser_acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-18|v2.1必需|数据限制/澄清/模板回退独立分类 / AI侧栏|retail_api.py|ai_verification_handoff.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-19|v2.1必需|自包含HTML/完整CSV/JSON/manifest / 导出侧栏/文件API|retail_export.py,retail_report.html,retail_api.py|public_acceptance_handoff/manifest.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-20|v2.1必需|实际浏览器打印PDF中文分页及附页 / 报告打印|retail_report.html,retail_export.py|browser_20261009/print_check.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-21|v2.1必需|桌面/390px窄屏实际浏览器 / 全部主页面|retail.css,SalesWorkspace.tsx|browser_20261009/browser_acceptance.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-22|v2.1必需|三会话/资源预算/超限失败/恢复 / 任务状态/系统|task_runner.py,task_worker.py,sales_mining.py|S03;R2峰值RSS历史|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-23|v2.1必需|CSV公式注入/HTML转义/路径与归属 / 导出/文件/原始记录API|retail_export.py,retail_api.py,data_api.py|结构交接声明|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|REQ-24|v2.1必需|回环监听与无公网裸露 / 运维|run.sh,main.py,AI启动|R3|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|CLS-01|本轮必修|版本化用户确认的实物/服务/调整/其他/待确认 / 映射/检查/月报|retail_schemas.py,mapping.py,retail_api.py|R3明确未修复|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|CLS-02|本轮必修|已确认运费不预测/异常商品池/补货建议 / 商品/行动/库存|retail_engine.py,sales_mining.py|历史POST/Manual实证|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|CLS-03|本轮必修|正常商品含POST不误杀/人工语义不猜测 / 分类确认|retail_engine.py,mapping.py|未实现|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|CLS-04|本轮必修|金额分项与总额/退款取消/整单不重复 / 月报/审计/导出|retail_engine.py,amounts.py,retail_export.py|历史导出合计相符但未分类|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|CLS-05|本轮必修|项目/版本隔离/旧run报告不变 / 历史报告/依据|retail_api.py,retail_engine.py|原冻结机制交接|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|CLS-06|本轮必修|分类进入AI证据/HTML/CSV/JSON/manifest / AI/导出|retail.ts,retail_api.py,retail_export.py|未实现|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|OLD-01|S01-S06保留|项目创建/切换/隔离 / 项目库|main.py,models.py,ProjectLibrary.tsx|S01|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|OLD-02|S01-S06保留|CSV/XLSX导入与不可变映射 / 数据记录|data_api.py,import_jobs.py,mapping.py|S02|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|OLD-03|S01-S06保留|质量/能力/独立有效视图 / 更多分析/质量|quality.py,quality_api.py|S03_evidence|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|OLD-04|S01-S06保留|持久队列/幂等/取消/恢复/超时 / 运行列表|task_runner.py,task_registry.py,task_worker.py|S03_evidence|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|OLD-05|S01-S06保留|RF/RFM/KMeans候选与拒绝发布 / 更多分析/分群|clustering.py,association.py,QualityWorkspace.tsx|evidence_s04_s06/acceptance_summary.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|OLD-06|S01-S06保留|FP-growth/规则/留出/热门对照 / 更多分析/共购|clustering.py,association.py,QualityWorkspace.tsx|evidence_s04_s06/acceptance_summary.json|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|OLD-07|S01-S06保留|结果探索/历史运行与证据链 / 更多分析/依据|quality_api.py,QualityWorkspace.tsx|S06|PASS|完整最终main的独立复验与远端SHA尚待发布步骤；不是该SHA最终发布证明|P0|
|SCOPE-01|待团队裁决|字段AI辅助确认的v2.1边界 / 映射辅助|clustering.py,association.py,QualityWorkspace.tsx|v2.1第7节;旧S07|NOT_APPLICABLE|先核对v2.1文字与实际能力，不假称完整AI映射已交付|P1|
|SCOPE-02|旧S07待团队裁决|自然语言任务操作与其他旧AI设想 / 未确认|clustering.py,association.py,QualityWorkspace.tsx|旧S07明确未完成|NOT_APPLICABLE|不自动新增到v2.1主线|P2|
|SCOPE-03|旧S08-S09待团队裁决|其他旧交付/运营设想 / 未确认|clustering.py,association.py,QualityWorkspace.tsx|v2.1与旧阶段对照|NOT_APPLICABLE|技术交接不等于全部旧要求完成|P2|
|HUMAN-01|外部人工验收|非开发者按README独立操作 / 实际系统|不适用|R3明确待办|BLOCKED|没有真实参与者，不由模型冒充|P1|
|HUMAN-02|外部人工验收|真实商户/异常真值/收益反馈 / 实际商户|不适用|KNOWN_LIMITATIONS待最终整理|BLOCKED|不能以公开批发数据代替小店收益|P1|
|PUB-01|外部发布条件|评委HTTPS入口/鉴权/可用性 / 部署|待批准|无公网授权|BLOCKED|隧道不等于公开成果链接；不擅自部署|P1|
|PUB-02|外部发布条件|比赛规则/材料/视频/人工提交 / 赛事平台|不适用|本地旧赛事附件未查最新官方|NOT_RUN|未录视频/未提交；期限不得未经官方核实引用|P1|
