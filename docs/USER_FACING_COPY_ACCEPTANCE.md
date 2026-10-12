# 用户可见文案实际验收（2026-10-12）

## 版本与顺序

实际fetch的基线main530791b5e12d76ce4ffe5d8f48d09753118a80b2（0.6.2）。先在个人隔离环境完整真实Chromium操作，独立原始审计commit511e810，再实现并复测。实现候选ae6b4d134e71d8c2079a04c760b00a5445ebec28（0.6.3/schema5/sales-v2.2.0）；最终发布SHA和从origin/main检出证据由交付目录release_verification.json记录，不能伪造文档自身SHA。正式共享项目未部署。

## 本轮实际结果

16个检查区域：项目/空态、CSV/XLSX/编码与工作表、映射与字段助手、分类与金额、质量、月报与比较、商品/行动、异常/原始行/备注、预测/库存、销售助手、RF/RFM、共购、历史/任务、各格式导出、42帮助/站内指南、失败/加载/限制。

| 测试 | 实际状态 | 本轮证据 |
|---|---|---|
| 完整新用户导入至AI及全部导出 | PASS | after/ux_candidate_journey/browser_import_acceptance.json |
| CSV编码/XLSX工作表、缺字段、两月追加/比较/历史刷新、日汇总、768/390px（7组） | PASS | after/ux_input_paths/results.json |
| 原交易日趋势、异常原始记录、库存、AI澄清、质量、新RF/RFM/Groceries共购及网络失败（11组） | PASS | after/ux_analysis_paths/results.json |
| 排队/运行取消、真实备注409及恢复、旧报告不变（5组） | PASS | after/ux_task_paths/results.json |
| 42主题全部打开关闭、键盘焦点、表单不丢、无额外提交、三宽度（11组） | PASS | after/ux_help_final/results.json |
| 12固定问题实际浏览器问答（最新修复） | PASS | after/ai_questions.json、copy_ai_questions/Q01–Q12截图 |
| 诱导性商品名与列名、原文/3件/18CNY不丢失、真实字段与商品模型回答 | PASS | after/copy_injection/results.json |
| 正常推理成功后再遇网络失败，不沿用成功标签 | PASS | after/copy_status/results.json |
| 6个受控模型HTTP故障，不可用/超时40秒/坏JSON/错误引用/内部自述/多余字段 | PASS | after/logs/after-copy_faults.log与copy_faults截图 |
| RF/共购质量详情、键盘Enter及390px；HTML复核SHA仍相同（3组） | PASS | after/copy_ui_review/results.json |
| Python76执行案例+6子测试 | PASS | after/checks_final.json与logs/checks-final-pytest.log |
| 帮助3内容合同测试、受影响范围Ruff、类型检查与Vite构建 | PASS | after/checks_fixed.json、checks.json与对应logs |
| 9核心算法/数据/数据库源码未改变 | PASS | after/business_sources_unchanged.json |
| 浏览器实际打印PDF中文两页、首页摘要/分类附页 | PASS | after/pdf_visual_receipt.json；真实渲染图片与PDF在D盘交付证据 |
| 全scripts Ruff扫描 | FAIL（132条继承格式问题） | checks-ruff-baseline.log在未修改530791同样复现；本次新增3条已修复 |
| 实际耗尽分析600/1200秒预算 | NOT_RUN | 无界等待不属于本轮操作预算；没有用短模型超时替代 |
| 共享服务重启恢复 | NOT_RUN | 禁止为文案任务中断队友服务；真实隔离任务安全单测保留 |
| 重新从网络安装全部依赖 | NOT_RUN | 本轮复用已装环境；干净源码检出与构建另行验证 |
| 真人商户研究 | BLOCKED | 无实际真人参与，不把Codex自查称用户研究 |

主全站35操作组（1+7+11+5+11）前后各执行；额外12问题+诱导+连续错误+6故障+3详情专项分别记录，不能全部加总为独立需求数量。受控故障不是模型自然产生的案例。完整证据保存在本轮隔离目录evidence/before、after、after_overview；选定公开测试证据在此仓库。

## 真实值与来源

公开Online Retail派生月汇总monthly_with_types.csv3005行，本次最终新上传project68373f12-8de9-4077-9bce-2336db067996/versionf52fa843-2b8b-4236-863f-82e71c92f25f/run9ef1e0fb-0c74-4d51-8552-f6dd46cf1d10。按用户确认分类统计2011-10实物销量626765、计入金额1105884.75GBP、2863商品；2998条实物、3条费用、1条人工调整、3条其他，排除费用26681.09/人工21548.67/其他79.72。原始行与金额分项不删除。

原交易fixture的月报run2b78c6a3-98f1-4d46-b308-4651224f5d96是在旧版本生成，**本轮重新打开并验证操作**，不冒称重新计算全部预测评测。23084七天参考1495.75原商品单位（2011-11-01至07），过去四周方法、历史MAE291.42；库存10/确定到货7/备用3/包装6实测参考1482。旧报告逐hash不变。新RF23fdb451、新RFM8b424c16、共购1ac96ab8本轮实际运行；Groceries9835篮/905规则，测试1967篮中1525可评，命中25.0%低于热门方法27.3%，限制未隐藏。

## AI内容核查

Q01真实模型介绍本月，绑定626765/1105884.75；Q02按冻结变化解释值得关注，不猜库存；Q03缺成本不能算利润；Q04缺具体日期先澄清；Q05–07同时给实际预测/方法/误差/库存限制；Q08条件式客户要求，不照抄用户“没有客户”假设；Q09正确支持度与提升度；Q10–12只拒绝内部指令/服务器/开发请求并指明服务范围。1问真实推理，其余明确为程序依据、使用说明、澄清或范围限制；没有对全部问题拒答。字段、正常月报、正常商品在其他完整流程也真实推理。

改前Q02库存猜测、Q05预测方法错误来自真实CPU模型；内部自述/extra_fields来自受控HTTP夹具，不能混称真实生成。改后整条拒绝，不截取、删除关键词或放宽证据/数字门槛。初cf4候选Q01坏JSON被拒的失败尝试仍在logs/after-copy_ai_questions.log；ae6改为本问题相关证据及短提示后真实重跑PASS。诱导源数据原文保留且不执行。

## 命令、环境与复核

远端个人updates/copy_cleanup_20261012_01，Python3.12，Node24.21，Chromium Playwright已装；模型Qwen2.5-1.5B Q4/llama-b11429 CPU4线程，ctx2048/单并发，回环18089；Web单Worker回环18088，独立SQLite/schema5。全部缓存/profile/日志在个人目录，Windows证据D盘。命令：

```bash
export PYTHONPATH="$PWD/backend"
.venv/bin/python -B -m pytest scripts/test_user_facing_copy.py scripts/test_ai_contract.py scripts/test_field_assistant.py scripts/test_sales_v2.py scripts/test_record_classification.py scripts/test_task_safety.py scripts/test_backup_safety.py --basetemp ../tmp/pytest-final-copy -q
.venv/bin/ruff check backend scripts/test_user_facing_copy.py
node --experimental-strip-types --test scripts/test_ux_guidance.mjs
cd frontend && npm run build
```

浏览器执行的是本轮u/scripts/run_before.py、run_after.py、run_overview.py及run_faults.py（参数和退出记录见机器JSON）；主要脚本在scripts/copy_*.cjs与既有ux_*.cjs，显式设置个人APP_BASE/UX_ROOT/UX_SOURCE/PLAYWRIGHT_MODULE及浏览器/cache变量，不能用默认正式8000来重跑。完整可执行隔离runner已保存于个人目录，不将内部绝对路径灌进用户帮助。

全部32审计项FIXED，本轮未发现未处理的产品内部自言自语；这不保证未来每次模型都能合法回答，非法回答仍如实标明。原用户商品名/项目名中的测试词是原始数据，不能错误清洗。继承脚本lint FAIL和上表未运行项单列，没有降低算法阈值或掩盖限制。

## 共享资产差异（不能用旧快照冒称未变）

本轮只读复核发现共享0.5.0与10月9日快照有25项源码差异、8表数据差异；所检查源码mtime均早于本任务2026-10-12T10:57:24Z开始。共享没有Git，本轮以实际GitHub main0.6.2为开发基线。队友此前改动原样保留，本任务未写共享源码/库、未部署/重启共享服务；不能声称全服务器与历史快照相同。证据formal_changes_vs_historical.json及formal_recheck.json。仓库main发布与共享部署是两件事。
