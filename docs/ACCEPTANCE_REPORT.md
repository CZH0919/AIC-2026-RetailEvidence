# 本轮实际验收报告

2026-10-10 更新：0.6.1 F01/F02 反馈修复与本轮真实验证见 [FEEDBACK_20261010](FEEDBACK_20261010.md)。个人当前隔离库位于 updates/review_20261010_01/state，源码为该目录 source；下方 2026-10-09 路径/run 为历史。正式目录未部署。本轮 candidate SHA d8f19452b5c89989f306f239ea20bb4d08ad629c，实际发布/最终运行收据另存个人工作区 evidence/feedback_20261010/release.json。

2026-10-09；Ubuntu24.04/8CPU/约30GB RAM/Python3.12.3/Node24.21.0。当前已验收代码候选 `bb8b645d19abd6422f47f6682a21a9f55b3124a6`，应用0.6.0/schema5/sales-v2.2.0。GitHub最终main提交的发布/fetch/实际运行收据另在个人工作区 `evidence/release_verification.json`；本文件不把候选SHA当作已发布SHA。正式共享项目没有部署。

|本轮检查|实际结果|可核对证据|
|---|---|---|
|销售分类26、真实子进程任务7、模拟月报AI7、模拟字段AI7|47 PASS，6子测试不重复计数；1依赖弃用提示|verification/final_candidate/checks.json；外部logs/final-fields-round.log|
|SQLite在线备份机制/独立恢复/WAL/禁止覆盖/FK失败|7 PASS，人工夹具；生产当前在线备份另见BASELINE_AUDIT|外部logs/final_backup.log、backup-static-tests-pass.log|
|HTTP导入/项目隔离/版本/幂等/旧RF/RFM/FP-growth/路径/历史AI保护|完整20 PASS，9fe8c11；后续只读核对旧算法源码保留|外部logs/api-regression-candidate-three.log；最终main将独立重跑|
|独立Git检出/47依赖安装/npm94包/空schema5启动/Ruff/tsc/Vite|PASS；初始化4349758，当前代码47测试/build已重跑|verification/final_candidate/clean_install.json、checks.json|
|原始541909行XLSX独立计算/固定切分/金额分项/所有导出|PASS，最新完整run `2b370640-6702-4fdf-9eb7-abe0a69142c9`|verification/final_candidate/public_acceptance.json、independent_xlsx.json、public_manifest.json|
|浏览器上传/预览字段AI/应用仍未确认/4类规则/检查/月报/商品/备注/月报AI/导出/390px/3会话|PASS，run `e519806f-37e1-4d0c-a9ab-2b6fd138e1ed`|verification/final_candidate/browser_import.json；真实截图与PDF|
|完整明细表/5摘要/3行动/异常日3原始行/备注409/库存未知限制/真实AI/打印|PASS，2863商品、1865待关注|verification/final_candidate/browser_full.json、full_print.pdf|
|排序/分页2/返回滚动300/搜索/映射取消/任务取消/旧报告不改|PASS，取消run `b37f5f95-ebe9-4154-bc86-6fe0b6a2a10f`|verification/final_candidate/browser_more.json|
|中文PDF默认摘要一页、分类附页一页|两个真实PDF各2页，实际渲染视觉PASS（Codex，不冒充真人）|verification/final_candidate/print_check.json|
|正式源码/mtime/新增文件及8表内容相对备份|89文件/8表无变化，schema5|verification/final_candidate/formal_recheck.json|

真实原始文件SHA `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`。2011-10全类型628438/1154194.23GBP；公开数据**验收假定**（不是商户会计确认）下，实物626765/1105884.75GBP/2863商品。运费406/26681.09、人工1263/21548.67、其他4/79.72；按分项与来源金额核对。旧派生差额307/785.07是同单冲突过滤差异，已独立计算，没有改冻结数据来美化结果。日/月派生来自同一实际原始文件，人工样例只用于边界。

验证截点2011-09-20/09-27/10-04，独立测试10-11/10-18/10-25。复杂法MAE90.576004、WAPE93.096754%；四周平均MAE63.629083、WAPE65.399894%，选择四周平均。eligible1321/tested1000/published382，历史候选1061/resource excluded61。异常train270990/test93341/flag2106/simple10473，无标签准确率NOT_APPLICABLE。算法任务单Worker、数值线程2；AI本轮4CPU线程/2048上下文/单并发；模型只读，无GPU。实际资源与监听采样见resources.json；生产预算未降低。

最新候选检查run029558f5-c9e3-42f5-8375-bf464db640e5约49.22秒，完整run2b370640-6702-4fdf-9eb7-abe0a69142c9约63.29秒。字段和月报CPU AI_used=true，preview_token/evidence_id或run/classification SHA绑定；数字由程序填入。模拟传输契约与真实推理证据明确分开，不把模板回退标为成功。

保留的本轮失败：首次浏览器缺动态库、npm空配置重复加载、错误质量夹具与选择器已修正并重跑；4349758真实明细模型说“确保准确的进货需求”被守卫拒绝，65a29b4提示示例含未绑定时间数字使月汇总AI被拒绝。未放宽数值/因果规则；prompt v5分别在明细/月汇总真实CPU重跑通过。字段理解按最新v2.1第7节补齐，旧S07更广自主映射/自然语言任务不冒称完成。失败日志保留在外部个人logs/，不是删除后标全通过。

完整45行需求矩阵：38 PASS/0未解决FAIL/3 BLOCKED/1 NOT_RUN/3 NOT_APPLICABLE。历史证据、各候选SHA、真实数据与命令分别记录在acceptance_matrix.csv。真人独立操作、真实商户反馈、公开HTTPS/鉴权为BLOCKED；录制视频/官方赛事核查/平台提交NOT_RUN，旧争议范围N/A仅表示不计本轮主线，不表示旧要求实现。

已具备私有托管授权，专用Deploy Key身份精确LSTongXXN/RetailEvidence-Studio；非目标连接器未使用。正式部署、公开仓库和数据库危险迁移均未批准/未执行。最终发布应仅在上述证据核实后push main，再fetch核对SHA，从实际远端提交重新安装/构建/运行关键流程；该收据不由本报告预先宣称PASS。
