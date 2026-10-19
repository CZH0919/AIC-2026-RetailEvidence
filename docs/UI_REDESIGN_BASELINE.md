# 商业化 UI 改版：功能与版本基线

审计日期：2026-10-19（Asia/Shanghai）。状态：**源代码与输入核查已完成；运行和浏览器基线受阻，第一阶段未完成。没有开始 UI 修改。**

本文件不代表现有站点已经通过本轮浏览器验收。2026-10-14 的截图和 PASS 仅是历史参考，不用作本轮改版前截图。恢复后必须补齐实际部署、备份、截图与测试，另行提交完整基线，之后才能修改业务页面。

## 1. 已实际核实的版本

| 对象 | 本轮结果 | 证据 |
|---|---|---|
| 目标仓库 | LSTongXXN/RetailEvidence-Studio；沿用专用 Deploy Key；未使用 GitHub 连接器 | 任务目录 evidence/github_baseline.json |
| GitHub main | `160a90c47b6f2a675386355cc283fb869e85334a`；实际 fetch 和 ls-remote 一致 | 同上 |
| 当前工作分支 | `feature/commercial-ui-refresh`，从 origin/main 新建，无重置或强推 | 同上及本地 Git |
| 应用 | frontend/package.json 0.6.3；React 19.3.0 / TypeScript 7.0.2 / AntD 6.6.5 / Vite 8.3.3 / Router 7.18.4 | 实际源码，不推断当前运行版本 |
| 当前部署、前端构建来源、端口、tmux、远端未提交内容 | **BLOCKED** | 严格 SSH 两次均连接超时，未执行远端检查 |
| schema / 算法实际运行版本 | **BLOCKED**；历史为 schema5 / sales-v2.2.0，不当成本次实测 | 历史记录与当前运行分开 |
| 本轮前端构建、构建大小 | NOT_RUN；本地副本没有 node_modules，依计划在服务器复用既有依赖构建 | 不在 Windows 安装或升级依赖 |

本机源码：`D:/AIC_RetailEvidence_Work/delivery_20261009_01/ui_refresh_20261019_01/source`。远端隔离目录计划：`/home/ubuntu/retailevidence_personal_20261009_01/updates/ui_refresh_20261019_01`，尚未连接验证、未创建。旧演示与共享目录均未修改。

## 2. 运行阻塞与安全边界

`audit/ssh_remote.py` 通过既有 Ed25519 登录身份、D 盘 known_hosts、StrictHostKeyChecking=yes、UpdateHostKeys=no 连接原 IP/22。2026-10-19 两次返回 `ssh: connect to host 43.172.115.244 port 22: Connection timed out`，REMOTE_EXIT=255。日志在本轮 logs/preflight_remote.log、preflight_remote_retry.log。**这不能证明服务器已经关机。**

未修改 SSH/代理/防火墙/安全组，也未关闭主机校验。当前仅服务器恢复可达才能解除运行阻塞。没有对活动数据库进行文件复制、迁移或写入，没有启动/停止共享服务。

进程缓存/临时文件沿用 D 盘 Invoke-InWorkspace.ps1；现有程序和认证只通过正常接口使用，无主动 C 盘写入或例外批准。无法承诺 Windows/Codex 所有后台零写入。

恢复操作顺序：读取远端各工作树 HEAD/status、运行进程 cwd、监听、/api/health 和 /assets/ui-release.json；与当前 main 比对；确认新目录及端口未占用；用 SQLite 在线备份 API 形成一致性独立副本并验证 integrity_check/版本/关键引用；对必要 storage 做限量清单及哈希；建立自己的基线/候选库及运行输出。禁止改共享 AIC_Project、现有个人演示数据库或复用 worker.lock。

## 3. 冻结输入与需要核对的数值

本轮实际读取并重新核算青禾便利店**完全模拟**交易 CSV。SHA-256：`e34d6cf870876e2baff8af00e45a74e70cea5a5a228f603fad21f30258425923`，2,075,257 bytes，17,641 行，8700 订单、240 客户、12 商品，CNY、Asia/Shanghai。输入文件保留在任务根 demo_dataset_20261014_01/数据包，不提交大数据进 Git。

本轮 csv + Decimal 独立计算，按订单检查每个重复总额等于该订单行金额之和：全量及六个月 **7 项 PASS**。收据：`verification/ui_redesign/frozen_input_check.json`。这是输入基线，尚非当前应用结果。

| 输入范围 | 销售额（元） | 数量（件） | 订单数 |
|---|---:|---:|---:|
| 2026-04—09 | 416263.10 | 66607 | 8700 |
| 2026-08 | 70402.60 | 11276 | 1397 |
| 2026-09 | 66434.40 | 10640 | 1326 |

适用后续样板的数据：同包 XLSX（二选一，不和同CSV重复导入）、日汇总、8/9月独立月汇总、边界数据中的费用/人工未知/POST实物、缺字段、错误工作表。每个异常场景使用独立项目。

历史演示定位线索：项目 `8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a`；9月 run `35cf3631-064c-4a90-a845-b06485eb9a3e`；版本 `079c4221-28b1-460c-9df2-be174312d824`。这些仅从旧收据读取，必须从本轮一致性备份和 API 再核实。不得把 18095 端口本身当作版本证据。

历史 P006 七天参考177、手填库存10/到货7/备用3/包装6对应168，仅作为重跑预期，当前应用尚未复验。库存日期必须与历史预测区间一致，不能把今天库存填入旧预测。

## 4. 功能保护矩阵

下表是对当前 main 源码逐入口清点；所有新入口计划保留原位，不变更导航和步骤。每项具体用例、原/新入口和状态另存 `UI_REDESIGN_PROTECTION_MATRIX.csv`。基线 BLOCKED 与改后 NOT_RUN 分开。

| 编号 | 页面/能力 | 原入口、字段与动作 | 保留的数据和规则 | 对应源码（frontend/src 下，另注除外） | 基线 / 改后 |
|---|---|---|---|---|---|
| UI-01 | 项目库与店铺 | /projects；新建项目、编辑店铺、搜索项目、分页、最近访问、空项目引导 | 保留名称/说明/颜色校验、250ms搜索与12项分页、切换项目清理范围 | pages/ProjectLibrary.tsx；pages/RetailProjectSpace.tsx；components/ProjectEditor.tsx | BLOCKED / NOT_RUN |
| UI-02 | CSV读取与草稿 | 数据记录→导入数据→选择文件→读取设置→字段与口径；保存/继续/放弃草稿 | 文件大小/类型限制、编码/分隔符、原始行、preview_token、busy防重复和关闭限制 | components/ImportEditor.tsx；components/DataWorkspace.tsx；data.ts | BLOCKED / NOT_RUN |
| UI-03 | XLSX与输入形状 | 同一导入抽屉：工作表、多表、普通逐行/购物篮长表/商品列表 | 只有同表头和顺序才合并；不制造客户/金额/时间；不改变步骤顺序 | components/ImportEditor.tsx；components/DataPreview.tsx | BLOCKED / NOT_RUN |
| UI-04 | 字段与金额口径 | 字段对应13项；记录粒度/月、订单边界、金额、数量单位、币种、时间格式、时区、状态 | 同列不得映射多个含义；未知留空；修改清除confirmed；订单总额每单一次；确认前按钮禁用 | components/MappingEditor.tsx；data.ts | BLOCKED / NOT_RUN |
| UI-05 | 记录分类 | 生成月报设置→确认记录类型、金额口径、精确规则、依据与版本确认 | 实物/费用/调整/其他/待确认；金额独立；空值/重复规则校验；不得降低确认门槛 | components/ClassificationEditor.tsx；components/SalesWorkspace.tsx | BLOCKED / NOT_RUN |
| UI-06 | 质量与范围 | 月报设置及更多分析→质量：重复候选、完整范围、重叠、取消/退货、排除原因 | 策略与scope键/默认值、版本/映射归属、来源行证据、终态含义与计数 | components/QualityWorkspace.tsx；components/QualityReport.tsx；quality.ts | BLOCKED / NOT_RUN |
| UI-07 | 月报与任务 | 销售月报→生成、取消、历史选择、复制链接、查看依据 | 月份、run参数、幂等/禁用、完整/不完整月份、未知与零区别、刷新前进后退 | components/SalesWorkspace.tsx；pages/RetailProjectSpace.tsx；retail.ts | BLOCKED / NOT_RUN |
| UI-08 | 商品列表 | 商品明细：搜索、筛选、排序、分页、名称与状态、详情入口 | 保留全部列/数值/精度/单位/无结果；表格可比较；返回后的筛选/页码/滚动 | components/SalesWorkspace.tsx；retail.ts | BLOCKED / NOT_RUN |
| UI-09 | 商品依据和备注 | 商品抽屉→每日走势、异常日期、来源行、计算依据、备注与原因 | actual/reference、无标签警告、source_row_id/run/版本归属、expected_revision冲突保留草稿 | components/ProductNote.tsx；components/SalesWorkspace.tsx；overlayLayers.ts | BLOCKED / NOT_RUN |
| UI-10 | 预测与库存 | 商品详情→七天参考、历史误差、可售库存/到货/到货日/备用/包装/确认、计算 | 预测门槛、历史日期、未确认不可计算；所有字段值/单位/上取整规则与拒绝状态 | components/SalesWorkspace.tsx；retail.ts | BLOCKED / NOT_RUN |
| UI-11 | AI辅助 | 字段解释、问问销售助手/这件商品、示例、复合问题、核对本次月报依据 | 真实模型/模板/澄清/受限分开；evidence_id/run；等待/超时；问题草稿保留 | components/FieldAssistant.tsx；components/SalesWorkspace.tsx；productCopy.ts | BLOCKED / NOT_RUN |
| UI-12 | 更多分析 | 更多分析→质量能力→RF/RFM与共购设置、结果、任务、来源依据 | 默认参数/阈值、数据能力、发布门槛、规则与因果限制、取消及终态 | components/QualityWorkspace.tsx；components/QualityReport.tsx；quality.ts | BLOCKED / NOT_RUN |
| UI-13 | 导出与打印 | 导出月报→HTML、CSV、JSON、完整数据/附页选项、浏览器打印PDF | 来源版本、run、金额/币种/完整商品/审计数值、转义与公式防护、旧报告不可变 | components/SalesWorkspace.tsx；retail.ts；backend/app/retail_export.py（只保护，不修改） | BLOCKED / NOT_RUN |
| UI-14 | 帮助与可访问性 | 各页面现有42主题、Popover/Drawer、导航抽屉、Select/Modal、焦点与关闭 | htmlType=button、Enter/空格/Tab/Escape、关闭焦点返回、库存/备注/映射草稿；1000/1100/1200/1300层级 | components/HelpHint.tsx；helpContent.ts；help.css；overlayLayers.ts | BLOCKED / NOT_RUN |
| UI-15 | 系统状态 | 空/加载/受限/禁用/无结果/失败/取消/完成/权限异常与重试 | 文字状态不隐藏、不仅靠颜色；401/403/404/409等按当前真实行为解释 | components/States.tsx；api.ts；各任务组件 | BLOCKED / NOT_RUN |

## 5. 请求、状态及数据合同

- api.ts、data.ts、retail.ts、quality.ts 的端点、请求键、超时保持；保存映射带 preview_token、mapping；修订带 expected_revision；月报带 sources/version_id/mapping_revision、classifications、month、merge_mode、duplicates、coverage 和 idempotency_key；备注带 item_id/day/reason/note/expected_revision。不得通过外观修改增加提交次数。
- 分类编辑任何变动清除 confirmed，校验规则/依据后才能确认；字段同列禁用重复匹配，记录粒度变化的现有字段重置逻辑保持。
- 原报告 result、产品全部条目、预测记录、分类分项、排除计数及导出解析内容按同一 run 比较。只能白名单归一化新项目/version/run UUID、生成时间与幂等键；金额、数量、来源哈希、月份、状态不允许归一化忽略。
- 记录 query、页码、排序、滚动、月份和备注/库存草稿；不调整业务组件 key、挂载层级或重挂载条件。
- 帮助为本地确定性内容，42主题；不调用 AI。overlayLayers 商品1000、助手1100、依据1200、帮助1300，必须保留，包含曾先打开依据的顺序。
- AI 自然语言不逐字比对，核对数值、evidence/run/来源、ai_used、真实推理与回退分类。至少一次当前 CPU 问答尚未执行。

`verification/ui_redesign/code_contract_baseline.json` 保存原始 Git blob 哈希、backend 树清单哈希，用于后续审查不可修改的 API/业务/依赖/帮助合同；不能凭静态哈希替代行为测试。

## 6. 样式与风险清点（静态源码事实）

- main.tsx 已有 ConfigProvider + AntD App 上下文；token：青绿 #087f73、正文14、控件40、圆角8。不升级 AntD，不切换成其他组件库。
- styles.css 涵盖侧栏、项目、导入、质量；retail.css 为销售页并含 .workspace 白底覆盖；analysis.css/help.css 独立。多处 minified 单行，不进行顺带大规模格式化。
- Shell 侧栏216、topbar68、main 左右38；项目标题在 retail.css 覆盖为26；项目库标题34。是否显得松散需本轮截图确认，不能只凭 CSS 认定页面缺陷。
- 月报已使用分隔线而非全站高阴影卡片；不得机械去卡片。指标有三种彩色左边线；可以在样板比较中评估收敛为统一强调色。
- ClassificationEditor 默认及规则采用内联宽度/边框；后续若改用明确class应只替换展示props，不移动控件、不改onChange/默认值/校验。
- SalesChart 实际为 Canvas + ResizeObserver + 可展开原始点数据（不是图表库/SVG）；保留所有 points/null/date/坐标/点击语义，样板优先只动容器样式。
- HelpHint、Drawer、Select 等 portal 在根节点之外。不能仅在 .sales-workspace 作用域改完就宣布弹层一致；需主题公开token、明确class与现有z-index验收。
- 旧 CSS 有 .ant-drawer-body padding !important 等规则；本轮不得继续叠加 !important 或全局通配符强压，先核对实际计算样式。

## 7. 本轮实际检查与既有问题

- `node --test scripts/test_ux_guidance.mjs`：3 PASS / 0 FAIL / 0 skipped，Node v24.14.0；日志 `verification/ui_redesign/help_contract.txt`。这是原帮助内容合同，不是浏览器可用性验证。
- 输入全量及六个月独立核算：7 PASS，见上。当前已执行测试合计10 PASS，0 FAIL；远端与浏览器检查另行 BLOCKED，改后测试 NOT_RUN。
- 旧全 scripts Ruff 132项问题见原交接记录；本轮没有执行，不能称已复现或已修复。新回归数量当前不可判断。
- 无本轮逐页页面、桌面/窄屏截图、HAR、AI/导出、实际构建体积或 PDF；**不得用历史文件充数**。

## 8. 恢复后必须补齐的基线

在未改 UI 的 main 上完成：完整导入CSV/XLSX→字段/分类→检查→月报→商品/异常/备注/库存→真实AI→HTML/CSV/JSON/PDF；单月/多月/月汇总、历史URL状态、RF/RFM/共购及关键失败。固定输入及参数保存请求与回读结果。

截图清单：销售月报、商品列表、商品详情、字段/分类表单，1440/1280/768/390px及200%缩放；正常与至少受限/错误一例；每张记录 source SHA、构建hash、项目/version/run、月份、视口和浏览器版本。改后按相同输入/报告/视口逐张复核。

独立 commit 保存本文件实际基线及 UI_REDESIGN_DIRECTION 后才能做样板。三类样板通过后等待用户审美确认；不得把三页或自动化检查当作全站交付。
