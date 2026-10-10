# 操作提示真实验收报告

执行日期：2026-10-10至11（北京时间）。初次完整审查→独立审查commit `6c82ab2616104e8842052b99e11b1ea426f9a40d`→实现→真实浏览器复测，严格遵循顺序。当前运行代码候选 `a673a440697bc4d75acde620b718cbe548379ca4`，0.6.2/schema5/sales-v2.2.0。最终GitHub发布与从实际main的干净复验收据另保存于交付工作区；本报告不冒填尚未发布SHA。

## 结果与口径

37个主浏览器验收组PASS，0个未解决FAIL，3个NOT_RUN、1个BLOCKED。另有类型/构建、3条帮助内容合同单测、pytest60执行案例加6subtests、Ruff、公开输入再生成5类验证PASS。pytest含继承重复案例，不能解释为60种独立业务需求。42个帮助主题逐个点击/键盘打开关闭；24个P0均有处理与复测对应，见 [逐项处置](verification/ux_guidance/issue_disposition.csv)。首次失败与中间回归失败仍保留；这里统计修复后的最终结果，不删除失败记录。

全站流程覆盖A–J：项目创建/切换与空项目，CSV/XLSX/编码/分隔符/工作表/预览/未知字段，字段与数量金额/币种/时区/订单/状态，记录分类/金额/覆盖/重复/追加替换，月报/对比/历史刷新，商品搜索与原始记录/异常/预测/备注，库存/到货/包装计算，真实CPU字段解释与销售问答/澄清/限制/不可用/超时，RF/RFM/共购，导出/浏览器打印PDF、真实排队取消与网络失败恢复。

## 环境与数据

Ubuntu24.04 CPU、Python3.12、Node24.21、Chromium/Playwright、单Worker；线程按既有2线程约束。Web仅回环18084，故障测试仅独立18085/18086，模型复用回环18082。浏览器profile/缓存/截图在个人隔离工作区，Windows产物只在D盘。正式共享源码、数据库及服务未部署或重启。完整数据来源、派生口径及SHA见 [输入manifest](verification/ux_guidance/after/context/manifest.json)。公开Online Retail parquet SHA `c0a6b6d27defeae17ba087e2a9e986f9cb2124682cb32534823f89ebf748d293`；原XLSX SHA `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`。分类是公开测试的明确假设，不代表商户确认。

最终候选完整新导入：项目`cf5cda48-313b-46fd-842e-1a9e13efef74`，V`fe650b33-3330-409e-8107-5e23d1b573c0`，run`a15cc731-37dc-4815-bfcf-a59863dcfc40`；输入3005行，实物商品2863种，销量626765原始单位，按确认口径销售额1105884.75GBP。单月汇总无每日预测是正确能力限制。真实CPU回答ai_used=true/model_inference，evidence_id与该run及分类hash匹配；HTML/CSV/JSON下载、真实浏览器file页打印A4 PDF、390px月报与三浏览会话PASS。此完整流在c34625a执行；最后唯一运行代码变更是帮助Tab焦点，a673a44已全42主题复测，发布后还须从实际main完整新导入复验。

原始明细核查使用被冻结旧run`2b78c6a3-98f1-4d46-b308-4651224f5d96`（本轮实际UI查看，非声称重新计算旧run）。商品23084的七天预测1495.75，模拟当时可售10、确定到货7、备用3、每包装6，程序返回1482原始单位；历史库存日期提示2011-11-01，明确禁止填写今天库存。模拟库存不是实盘库存。

本轮真实新质量run `a8d57bd7-1d09-4d95-a85b-4473b9dbac49`，RF`02b2076c-cb3d-4690-b109-b19a1b9606ba`，RFM`49a8b3b1-f13c-49f0-9649-d36fd4d1efb2`；Groceries质量`bec53404-4a72-4ce7-a06f-c3f6b5f77fad`，共购`5450dfb7-2836-4705-b15e-87a5e7e4a07c`。共购905规则，训练5901/验证1967/测试1967；测试推荐表现未优于流行度基线，不能宣传经营提升。订单金额不完整客户范围人工选择后才运行RFM。

## 实际命令与证据

所有浏览器命令要求预先设置PLAYWRIGHT_MODULE、PLAYWRIGHT_BROWSERS_PATH、SALES_BASE为本人隔离Web、SALES_EVIDENCE_DIR和SALES_BROWSER_PROFILE到隔离目录、RETAIL_TEST_ROOT到公开派生fixture目录，正确字体/系统库路径。脚本含明确隔离fixture ID，禁止指向正式库。质量/任务脚本会在隔离库创建运行和备注；原始输入只读。

|专项|实际命令|结果组|耗时秒|源码SHA|证据|
|---|---|---:|---:|---|---|
|ux_candidate_journey|`node scripts/ux_candidate_journey.cjs`|1 PASS|46.639|c34625ada72471f0c14a46f63dfddc066d4e208c|[收据](verification/ux_guidance/after/ux_candidate_journey_exit.json)、[日志](verification/ux_guidance/after/logs/after-ux_candidate_journey.log)|
|ux_input_paths|`node scripts/ux_input_paths.cjs`|7 PASS|121.548|14161c3716e0fe6d6e6a7ef58e41b7197f941f6b|[收据](verification/ux_guidance/after/ux_input_paths_exit.json)、[日志](verification/ux_guidance/after/logs/after-ux_input_paths.log)|
|ux_analysis_paths|`node scripts/ux_analysis_paths.cjs`|11 PASS|151.576|c34625ada72471f0c14a46f63dfddc066d4e208c|[收据](verification/ux_guidance/after/ux_analysis_paths_exit.json)、[日志](verification/ux_guidance/after/logs/after-ux_analysis_paths.log)|
|ux_task_paths|`node scripts/ux_task_paths.cjs`|5 PASS|17.040|c34625ada72471f0c14a46f63dfddc066d4e208c|[收据](verification/ux_guidance/after/ux_task_paths_exit.json)、[日志](verification/ux_guidance/after/logs/after-ux_task_paths.log)|
|ux_help_final|`node scripts/ux_help_final.cjs`|11 PASS|112.124|a673a440697bc4d75acde620b718cbe548379ca4|[收据](verification/ux_guidance/after/ux_help_final_exit.json)、[日志](verification/ux_guidance/after/logs/after-ux_help_final.log)|
|ux_ai_unavailable|`node scripts/ux_ai_unavailable.cjs`|1 PASS|2.719|317a2c432b6a1e237d56bee887f3756db1995d27|[收据](verification/ux_guidance/after/ux_ai_unavailable_exit.json)、[日志](verification/ux_guidance/after/logs/after-ux_ai_unavailable.log)|
|ux_ai_timeout|`node scripts/ux_ai_timeout.cjs`|1 PASS|42.672|317a2c432b6a1e237d56bee887f3756db1995d27|[收据](verification/ux_guidance/after/ux_ai_timeout_exit.json)、[日志](verification/ux_guidance/after/logs/after-ux_ai_timeout.log)|

静态与单测实际命令和UTC执行时间保存在 [checks.json](verification/ux_guidance/after/context/checks.json)：`node --test scripts/test_ux_guidance.mjs`、`.venv/bin/python -B -m pytest -p no:cacheprovider scripts/test_sales_v2.py scripts/test_record_classification.py scripts/test_task_safety.py scripts/test_ai_contract.py scripts/test_field_assistant.py -q`、`.venv/bin/ruff check --no-cache backend scripts/test_record_classification.py scripts/test_task_safety.py scripts/test_ai_contract.py scripts/test_field_assistant.py`，前端`npm run build`含tsc --noEmit。再生成输入命令`python scripts/prepare_ux_inputs.py --source <公开parquet> --root <空隔离目录>`，5个CSV SHA完全一致，XLSX因ZIP时间不宣称位级一致。

## 帮助专项验收

11组PASS覆盖：项目键盘/新建草稿；月报与导出嵌套帮助；分类身份、空规则与重复就地阻止；两种映射界面/输入保留/不自动勾选确认；CSV/XLSX读取提示；预测/历史库存/备注草稿；AI示例只填入不发送；更多分析解释；768px与390px无横向溢出；外侧点击/遮罩/标题Escape；全部42主题。打开帮助没有新增POST/PUT，关闭帮助不关闭原表单。Enter、空格、Tab/Shift+Tab、Escape、触发焦点恢复实际断言。简短提示≤10字符，例子、未知数据处理和错误影响在集中内容定义内。

## 失败记录与修复

- 初次输入脚本的导航/严格定位失败保留，修正测试后7组PASS；不是把API成功当页面成功。
- 帮助初次键盘/断点焦点丢失、768px轻提示溢出、最终嵌套Drawer的Tab离开均真实发现并修复；对应失败日志与results在after的attempt目录。最后112.124秒11组PASS。
- 网络失败通过真实浏览器route.abort制造，随后解除并恢复；模型不可用为真实不可达隔离上游，超时为45秒延迟上游触发既有40秒限制。与真实Qwen成功分别记录，未把模板回退当推理。
- 备注两个页面真实409，草稿保留，读取最新文字再手动200保存；被冻结旧月报未改变。

## 未验证与现实限制

3项NOT_RUN：完整600/1200秒分析预算耗尽、真实模型错误引用分支、共享服务重启。已有AI合同单测不等于这些真实分支均通过。真实商户/非开发者研究BLOCKED：没有人参与，不能从模型自查推导用户理解率或经营收益。暂无公网评委入口；没有部署共享正式环境。依赖复用已安装环境，未重装模型或重跑网络安装；干净源码复现与重新安装依赖应区分。测试PDF属于Chromium真实打印，不等于人工打印机测试。
