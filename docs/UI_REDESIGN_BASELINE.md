# 商业化 UI 改版：功能与版本基线

日期：2026-10-19。**运行基线已恢复并实测；尚未修改 UI。** 初次 SSH 超时保留在提交82e1ad5及 connectivity.json，不作为当前阻塞。所有结果是开发自查，不是真实商户研究。

## 1. 版本、运行及隔离

- GitHub main 实际 fetch/ls-remote：`160a90c47b6f2a675386355cc283fb869e85334a`。应用0.6.3 / schema5 / sales-v2.2.0；React19.3.0、TS7.0.2、AntD6.6.5、Vite8.3.3、Router7.18.4。
- 本机 D:/AIC_RetailEvidence_Work/delivery_20261009_01/ui_refresh_20261019_01/source，分支 feature/commercial-ui-refresh；原 history/authors/tags/upstream 保留。只使用专用 Deploy Key，未推送本轮分支或合并main。
- 远端任务 `/home/ubuntu/retailevidence_personal_20261009_01/updates/ui_refresh_20261019_01`（下称 TASK）。baseline/source 是160a90c无硬链接Git克隆，原 verified-main 干净；candidate 使用独立数据库/存储。共享 AIC_Project 无可核实 Git HEAD，本轮没有改写它。
- 服务器刚开机时无旧 Web/AI/tmux；18088/18089/18094无服务。本轮只创建 re-ui-base / re-ui-ai，分别监听127.0.0.1:18100 /18102。候选预留18101，未替换旧演示、未修改共享服务。端口不作为版本证据，构建收据位于 dist/assets/ui-release.json。
- Web启动：`bash TASK/start_baseline.sh`；AI：`bash TASK/start_ai.sh`。不要与现有tmux重复启动。只停止本任务时可 `tmux kill-session -t re-ui-base` / `-t re-ui-ai`，不影响原演示数据库。
- 依赖只读复用既有venv，前端node_modules复制到TASK；模型只读引用已有Qwen2.5-1.5B GGUF。CPU模型4线程、上下文2048、并发1；数值库线程2；不安装/升级系统依赖。
- 缓存、profile、TMP、输出均TASK或D盘，未主动写C盘。SSH仍D盘已授权信任+StrictHostKeyChecking=yes；没有修改全局配置。不能保证OS/Codex背景零写入。

## 2. 一致性备份与可回滚基线

SQLite 在线备份API形成 TASK/backups/demo_consistent.sqlite3，SHA256 `ed80dd6e7d8e3d1bbea02df340510c530bce26e93d00854903457300a2501e60`。integrity_check=ok，foreign_key_check=[]，user_version=5，八张表可读取。未单独复制活动主库冒充备份；原库不变。本轮浏览器新建任务只写baseline独立恢复库。

源码全历史bundle TASK/backups/source_before.bundle，SHA256 `61152233bad99a1593cff5d6f644df32e2fb40b5381abe381f8507d6fa4d7417`。必要模拟storage仅46,435,951字节，未复制模型/无关真实数据。恢复方法：在新任务目录用sqlite3 backup API从该备份恢复至独立state，复制对应模拟storage，git从bundle检出160a90c，设置独立STATE/STORAGE/STATIC路径和空闲回环端口。验证见 verification/ui_redesign/baseline_setup.json。

构建实际执行 `npm run build -- --configLoader runner`（包含tsc --noEmit），PASS；dist总1,289,070 bytes。既有data chunk约1MB触发500kB警告，记录为既有构建提示，不通过删功能降体积。

## 3. 冻结数据、报告与确定性基线

完全模拟青禾CSV：SHA256 `e34d6cf870876e2baff8af00e45a74e70cea5a5a228f603fad21f30258425923`，17,641行/8700订单/240模拟客户/12实物商品，2026-04—09，CNY/Asia-Shanghai。独立csv+Decimal全量及六个月7PASS；每单重复总额仅计一次。

|范围|金额CNY|数量|订单|
|---|---:|---:|---:|
|全量|416263.10|66607|8700|
|8月|70402.60|11276|1397|
|9月|66434.40|10640|1326|

同数据CSV和XLSX新项目实际上传→映射→分类→月报，9月数值与上表相符。CSV项目 `5b289dba-c261-438d-8c2d-5a6548729771`、版本 `0288ff9f-0014-4531-8727-340a43fc9ed8`、run `e35a597d-4380-4506-93c5-befcf4db0d10`；XLSX IDs在 baseline_xlsx.json。

样板固定旧项目 `8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a` / 版本 `079c4221-28b1-460c-9df2-be174312d824` / run `35cf3631-064c-4a90-a845-b06485eb9a3e`。本轮API重新核对amount=66434.4；完整result保存于 TASK/baseline/evidence/before_v2/frozen_run.json。前后比较必须使用此同run，不修改旧报告。

P006七天参考177件；同预测期间库存10、确定到货7（2026-10-01）、备用3、包装6，实际备货参考168；备注保存回读、异常日来源记录、AI evidence_id与当前run相符，ai_used=true。历史日期库存用于模拟，不填今天库存制造结论。

## 4. 功能保护矩阵

下表是对当前 main 源码逐入口清点；所有新入口计划保留原位，不变更导航和步骤。每项具体用例、原/新入口和状态另存 `UI_REDESIGN_PROTECTION_MATRIX.csv`。表中 PASS 仅表示下文列明的已覆盖主流程，未覆盖细项仍为 NOT_RUN。

| 编号 | 页面/能力 | 原入口、字段与动作 | 保留的数据和规则 | 对应源码（frontend/src 下，另注除外） | 基线 / 改后 |
|---|---|---|---|---|---|
| UI-01 | 项目库与店铺 | /projects；新建项目、编辑店铺、搜索项目、分页、最近访问、空项目引导 | 保留名称/说明/颜色校验、250ms搜索与12项分页、切换项目清理范围 | pages/ProjectLibrary.tsx；pages/RetailProjectSpace.tsx；components/ProjectEditor.tsx | PASS（主流程） / NOT_RUN |
| UI-02 | CSV读取与草稿 | 数据记录→导入数据→选择文件→读取设置→字段与口径；保存/继续/放弃草稿 | 文件大小/类型限制、编码/分隔符、原始行、preview_token、busy防重复和关闭限制 | components/ImportEditor.tsx；components/DataWorkspace.tsx；data.ts | PASS（主流程） / NOT_RUN |
| UI-03 | XLSX与输入形状 | 同一导入抽屉：工作表、多表、普通逐行/购物篮长表/商品列表 | 只有同表头和顺序才合并；不制造客户/金额/时间；不改变步骤顺序 | components/ImportEditor.tsx；components/DataPreview.tsx | PASS（主流程） / NOT_RUN |
| UI-04 | 字段与金额口径 | 字段对应13项；记录粒度/月、订单边界、金额、数量单位、币种、时间格式、时区、状态 | 同列不得映射多个含义；未知留空；修改清除confirmed；订单总额每单一次；确认前按钮禁用 | components/MappingEditor.tsx；data.ts | PASS（主流程） / NOT_RUN |
| UI-05 | 记录分类 | 生成月报设置→确认记录类型、金额口径、精确规则、依据与版本确认 | 实物/费用/调整/其他/待确认；金额独立；空值/重复规则校验；不得降低确认门槛 | components/ClassificationEditor.tsx；components/SalesWorkspace.tsx | PASS（主流程） / NOT_RUN |
| UI-06 | 质量与范围 | 月报设置及更多分析→质量：重复候选、完整范围、重叠、取消/退货、排除原因 | 策略与scope键/默认值、版本/映射归属、来源行证据、终态含义与计数 | components/QualityWorkspace.tsx；components/QualityReport.tsx；quality.ts | PASS（主流程） / NOT_RUN |
| UI-07 | 月报与任务 | 销售月报→生成、取消、历史选择、复制链接、查看依据 | 月份、run参数、幂等/禁用、完整/不完整月份、未知与零区别、刷新前进后退 | components/SalesWorkspace.tsx；pages/RetailProjectSpace.tsx；retail.ts | PASS（主流程） / NOT_RUN |
| UI-08 | 商品列表 | 商品明细：搜索、筛选、排序、分页、名称与状态、详情入口 | 保留全部列/数值/精度/单位/无结果；表格可比较；返回后的筛选/页码/滚动 | components/SalesWorkspace.tsx；retail.ts | PASS（主流程） / NOT_RUN |
| UI-09 | 商品依据和备注 | 商品抽屉→每日走势、异常日期、来源行、计算依据、备注与原因 | actual/reference、无标签警告、source_row_id/run/版本归属、expected_revision冲突保留草稿 | components/ProductNote.tsx；components/SalesWorkspace.tsx；overlayLayers.ts | PASS（主流程） / NOT_RUN |
| UI-10 | 预测与库存 | 商品详情→七天参考、历史误差、可售库存/到货/到货日/备用/包装/确认、计算 | 预测门槛、历史日期、未确认不可计算；所有字段值/单位/上取整规则与拒绝状态 | components/SalesWorkspace.tsx；retail.ts | PASS（主流程） / NOT_RUN |
| UI-11 | AI辅助 | 字段解释、问问销售助手/这件商品、示例、复合问题、核对本次月报依据 | 真实模型/模板/澄清/受限分开；evidence_id/run；等待/超时；问题草稿保留 | components/FieldAssistant.tsx；components/SalesWorkspace.tsx；productCopy.ts | PASS（主流程） / NOT_RUN |
| UI-12 | 更多分析 | 更多分析→质量能力→RF/RFM与共购设置、结果、任务、来源依据 | 默认参数/阈值、数据能力、发布门槛、规则与因果限制、取消及终态 | components/QualityWorkspace.tsx；components/QualityReport.tsx；quality.ts | PASS（主流程） / NOT_RUN |
| UI-13 | 导出与打印 | 导出月报→HTML、CSV、JSON、完整数据/附页选项、浏览器打印PDF | 来源版本、run、金额/币种/完整商品/审计数值、转义与公式防护、旧报告不可变 | components/SalesWorkspace.tsx；retail.ts；backend/app/retail_export.py（只保护，不修改） | PASS（主流程） / NOT_RUN |
| UI-14 | 帮助与可访问性 | 各页面现有42主题、Popover/Drawer、导航抽屉、Select/Modal、焦点与关闭 | htmlType=button、Enter/空格/Tab/Escape、关闭焦点返回、库存/备注/映射草稿；1000/1100/1200/1300层级 | components/HelpHint.tsx；helpContent.ts；help.css；overlayLayers.ts | PASS（主流程） / NOT_RUN |
| UI-15 | 系统状态 | 空/加载/受限/禁用/无结果/失败/取消/完成/权限异常与重试 | 文字状态不隐藏、不仅靠颜色；401/403/404/409等按当前真实行为解释 | components/States.tsx；api.ts；各任务组件 | PASS（主流程） / NOT_RUN |


## 5. 本轮实际执行与未覆盖范围

|测试组|实际结果|证据（TASK下）|
|---|---|---|
|静态/类型/构建|PASS，tsc+Vite|logs/baseline_build.log；evidence/baseline_build_manifest.json|
|后端专项|76 passed +6 subtests，14.95秒；1个既有httpx弃用警告|logs/baseline_pytest.log|
|CSV完整真实浏览器|9组PASS，页面未捕获错误0；导入/确认/分类/月报/商品异常备注/库存/真实CPU AI/导出打印/质量/RF/RFM/共购|baseline/evidence/clean/browser_results.json、requests.json及对应API回读和PDF|
|XLSX真实浏览器|3组PASS，新项目完整导入并生成/JSON金额核对|baseline-xlsx/evidence/clean/browser_results.json|
|交互补充|6组PASS：历史切换/刷新/back/forward/复制URL、月汇总受限、商品搜索排序筛选返回、帮助键盘焦点、映射草稿、404与隔离网络故障恢复|baseline/evidence/guards/results.json；logs/baseline_guards_retry.log|
|同报告截图|20/20 PASS结构检查；1440/1280/768/390，各月报/商品表/详情/分类正常/分类空规则错误；无页面横溢出|baseline/evidence/before_v2/results.json、同名png/txt|
|帮助内容合同|3PASS|verification/ui_redesign/help_contract.txt|
|输入独立核算|7PASS|verification/ui_redesign/frozen_input_check.json|

pytest实际命令：`PYTHONPATH=backend:scripts .venv/bin/python -B -m pytest -q scripts/test_sales_v2.py scripts/test_record_classification.py scripts/test_task_safety.py scripts/test_ai_contract.py scripts/test_field_assistant.py scripts/test_user_facing_copy.py --basetemp TASK/tmp/pytest-base`。环境AIC_STATE_DIR/AIC_STORAGE_DIR指向TASK/unit，线程上限和缓存见启动脚本。

真实浏览器为现有Playwright Chromium headless shell1234，独立profile在TASK；不是Mock。脚本位于 scripts/ui_redesign/，RETAIL_TEST_ROOT含data软链接至模拟包、RETAIL_BASE_URL指定隔离端口、PLAYWRIGHT_MODULE指定现有模块，浏览器/库/fontconfig使用现有browser-runtime，全部可变输出在TASK。请求保存JSON业务字段，不保存认证头。

**NOT_RUN细项**：逐一42个帮助主题全覆盖、真实浏览器原生200%缩放（机器只有headless shell）、项目编辑/多页项目分页、错误编码/多工作表组合/所有草稿恢复、所有金额/缺字段组合的UI、浏览器409/取消/超时/权限状态全组合、>20商品跨页、全部AI歧义/回退组合。专项单测包含部分规则保护，不能当作这些UI已经执行。三页样板后补充受影响部分，方向批准后全站阶段继续矩阵验收。

测试修正：guards首次因getByText同时匹配SVG title与说明文字失败，改为语义说明定位后6组全部通过，原日志保留。第一版分类截图fixture未清除既有规则，正常态误含空规则；修正fixture后before_v2重新20张，旧before保留而不作为对照。均不是产品业务错误。

## 6. 页面视觉问题与保护合同

实际查看本轮1440商品/分类、390详情、768月报以及此前1440月报/详情、390月报截图：①项目标题到工作区冗余垂直间距；②指标三种彩线没有不同风险含义；③数值列左齐难比较；④分类规则无持续可见标签且纵向堆叠；⑤768指标单位被拆开；⑥详情标题、参考值和帮助并列拥挤。没有发现支持全站充满机器人/渐变的证据，品牌/导航/表格保留。

请求与业务合同：api.ts/data.ts/retail.ts/quality.ts端点、请求键、超时和confirm条件不改；记录expected_revision、来源version/hash、金额/数量/币种/排除计数/预测/库存结果。只允许新建实体UUID/创建时间/幂等键白名单归一化，不能忽略业务字段。SalesChart Canvas的points/null/日期/坐标不改。旧报告不可变。

样式风险：main.tsx ConfigProvider+App已存在；styles.css有minified全局规则，retail.css覆盖workspace；analysis/help独立。只用公开token、明确class、局部CSS；不升级依赖/重写状态层。classification仅替换展示属性/补标签，保留控件key/value/onChange/顺序/默认值。HelpHint与42主题不变，z-index商品1000/助手1100/依据1200/帮助1300保持。

既有问题：本轮768指标单位换行需视觉修复；data chunk警告；旧Ruff132问题仅历史记录未重跑。没有把它们算作新增回归。没有修改后端/算法/导出模板。

## 7. 下一检查点

本报告和方向研究必须独立提交，再做三类样板；同冻结run/视口前后对比并回归。样板通过后提供新端口预览，等待用户审美确认，不合并main、不替换原演示、不推广全站、不宣称最终交付。


## 用户样板反馈：说明按需展开（2026-10-19）

本轮针对常驻解释过多的反馈已实施并复测，详见[说明收纳修订及真实截图](UI_REDESIGN_COPY_REFINEMENT.md)。9项前端检查和16组浏览器检查通过。仅两条固定说明转入帮助，动态风险直接显示；其余表格与依据可点击展开。仍未获得全站视觉批准，main及共享正式部署不变。


## 全站扩展基线（2026-10-19，用户确认后）

- 用户已明确确认三类样板及说明按需展开的方向，授权推广全站。原始研究与基线独立提交仍为 7038658；本次补充基线使用 40ad43cdbb2d2b03b293761257661fcb0b497d38。
- 远端 whole-site/source、独立在线备份数据库和 storage；新增回环 18103，保留 18100/18101 以及共享正式目录。前端 build/TypeScript 通过。
- 新增真实浏览器基线：项目库、创建弹窗、空项目、上传、读取、映射、数据记录、质量/分群/共购，共 28 张截图，1440/1280/768/390 视口；证据 whole-site/evidence/whole-before/results.json，测试脚本 scripts/ui_redesign/browser_whole_capture.cjs。
- 冻结青禾模拟数据和原演示报告不变；新增空项目 3ca4307c-1147-4706-9251-9d39a8193387，仅用于本轮导入草稿。没有将模拟店铺认定为真实用户研究。
- 已观察到：项目库重复流程及无说明的默认文案、上传页空白和装饰占比过大、字段帮助占独立行、质量页重复说明与过程日志常驻。保留字段样例、确认项、限制原因和统计计数；使用明确作用域样式与少量原生展开容器整理。
- 基线首次尝试因 Ant Design 的“取 消”空格导致脚本定位失败，证据保存在 capture-attempt-*；按语义正则定位重试后 28/28 完成、无页面溢出和脚本错误。未删除失败证据。
