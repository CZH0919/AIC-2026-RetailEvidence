# 商业化 UI 三类样板验收

日期2026-10-19。**本文件为三类真实样板的工程验收，视觉方向待用户确认；全站推广/合并main/替换旧演示尚未执行。** 这是开发可用性自查，不是真实商户研究。

## 版本和实际环境

- 已核main：160a90c47b6f2a675386355cc283fb869e85334a，0.6.3/schema5/sales-v2.2.0。
- 基线与研究独立提交：7038658a9f200ec9e62b56ff08ab5d02549484e7，先于任何UI修改。
- 样板批次：ac3ba2e共享样式；eedefff样板布局；491c10f保护测试兼容修正；7b61d848fb5438c49422a2b5687354d1825697f9最终CSS样板。版本号保持0.6.3，以SHA识别候选，不打稳定tag。
- 分支feature/commercial-ui-refresh。最终文档提交不改变该样板frontend/backend树；远端分支SHA和干净检出复测收据由交付后实际fetch/验证生成（TASK/evidence/final_verification.json），不能仅凭文档文字判断成功。
- TASK=/home/ubuntu/retailevidence_personal_20261009_01/updates/ui_refresh_20261019_01。baseline/source和candidate/source、state/storage/profile完全隔离；Web回环18100/18101，CPU AI18102。未改共享正式源码/库/服务或旧演示。
- Node24.21.0/Python3.12、既有venv及Playwright Chromium headless_shell1234。所有可变输出TASK；Windows仅D盘Git/文档/证据/隧道，StrictHostKeyChecking=yes，无主动C写入或获批例外。

## 已执行的功能检查

所有用例使用同SHA模拟CSV/XLSX，CNY；数据来源和独立Decimal基线见BASELINE。下表不同粒度不相加成一个“总通过数”。

|编号/源码版本|执行内容|结果|证据|
|---|---|---|---|
|B01/160a90c|原版tsc+Vite、76后端专项+6子测试、CSV9组、XLSX3组、guards6组|PASS|baseline_*.json及BASELINE|
|T01/7b61d84|npm run build -- --configLoader runner，tsc --noEmit+Vite|PASS|candidate_build.txt、candidate_build_manifest.json|
|T02/7b61d84|node --test scripts/ui_redesign/test_presentation_contract.cjs scripts/test_ux_guidance.mjs|6 PASS、0FAIL/0skip|candidate_contract.txt|
|T03/491c10f（之后只改CSS）|同六个pytest文件同参数、独立unit库|76 PASS+6子测试，12.97s，既有httpx警告1|candidate_pytest.txt|
|T04/491c10f（之后只改CSS）|CSV新建→上传→13映射+口径确认→分类/范围→检查/月报→商品异常来源/备注回读→库存计算→真实CPU AI→HTML/CSV/JSON/PDF→质量/RF/RFM/共购|9组PASS，未捕获错误0|candidate_csv.json；TASK/candidate/evidence/clean|
|T05/491c10f（之后只改CSS）|独立XLSX新项目，实际生成月报并导出JSON回读|3组PASS|candidate_xlsx.json|
|T06/7b61d84|历史8/9月切换/刷新/back/forward/复制URL、月汇总受限、商品搜索/无结果/排序筛选/详情返回、帮助Enter/Space/Tab/Escape/焦点、映射草稿保留、404和隔离网络故障恢复|6组PASS|candidate_guards.json|
|T07/491c10f（之后只改CSS）|1440/390 × 初次/预先打开依据，商品→计算依据→帮助→Esc逐层、库存/备注/问题草稿、真实问答、导出回读|4组合PASS，焦点与elementFromPoint命中均正确|candidate_drawers.json；TASK/logs/candidate_drawers.log|
|T08/7b61d84|1440/768/390分类可见标签、下拉不越界、帮助不清空字段、不自动确认/提交、未检查生成禁用|3组PASS|candidate_prototype.json|
|T09/7b61d84|720×500 CSS视口，等效1440×1000桌面200%布局空间，无页面溢出|PASS（等效布局）；原生浏览器200% NOT_RUN|candidate_prototype.json，不能把DPR或小视口称为原生缩放|
|T10/7b61d84|1440/1280/768/390 × 月报/商品/详情/分类正常/分类错误，同报告截图与页面溢出|20/20 PASS结构；逐张视觉复核，局部宽表可横滚|after_screenshots.json、screenshot_manifest.json；BEFORE_AFTER|
|T11/491c10f，7b61d84未改JS/业务|同冻结run完整JSON+七种导出解析+HTML，独立新run业务子树/库存/请求字段和次数|17 PASS|equivalence.json；最终干净检出会再核对冻结result|

专项命令同BASELINE第5节。浏览器脚本在scripts/ui_redesign；原抽屉脚本scripts/browser_sales_drawers.cjs。RETAIL_TEST_ROOT指定独立root（必须含data模拟包路径），RETAIL_BASE_URL指定回环端口，PLAYWRIGHT_MODULE/BROWSERS_PATH/LD_LIBRARY_PATH/fontconfig沿用既有安装，TMP/XDG/HOME均TASK。不要在共享生产目录执行写入脚本。

**关键实际值**：9月金额66,434.40，销量10,640，订单1326，12实物商品；8月70,402.60/11,276。P006七天参考177、历史MAE42.25，库存10/到货7/备用3/包装6对应168。AI ai_used=true/mode=model_inference，evidence_id与run+classification SHA一致。共购及RF/RFM publishable=true。数字为模拟数据测试结果，不代表经营收益。

新CSV项目0a73b36c-3ea9-4cb5-891d-80dde2f86254，run78f14f3f-73d3-46d7-b456-eba79864dff7；固定前后报告仍为项目8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a/run35cf3631-064c-4a90-a845-b06485eb9a3e。

请求比较：原/新各14次POST/PUT，路径、字段、次数一致；只白名单归一化新实体UUID、捕获时间和项目名生成时间戳。所有金额/销量/币种/日期/规则/确认/参数均保留。冻结同run不归一化，完整result规范化SHA256为221fc60b179b6e930f0871a04134afb3a34724029f3b3e8a5835cc67df989f2c。

## 视觉变化与保护

修改仅四个产品文件：main.tsx主题/样式导入；commercial-ui.css明确作用域；SalesWorkspace.tsx数值align与两抽屉class；ClassificationEditor.tsx可见标签、规则标题/class取代内联边框。控件key/value/onChange/顺序/校验/确认/默认值保持，后端、API、路由、算法、模型提示、依赖、图表和帮助合同零差异。

减少页头空白，品牌青绿替代无关蓝链接，同类指标去无语义红黄线并组合为中性表面；数字右齐/等宽、单位不拆，768宽度指标重排；商品表保留全列，说明列最小宽度以避免窄屏行高过大；分类双列在390变单列，标签持续可见；商品详情分组与七天参考留出间距。风险、金额口径分项和解释原位保留。无新增字体/图片CDN/库/装饰资源。

最终样板dist 1,295,090 bytes，原1,289,070，增加6,020 bytes（约0.47%）；没有新增依赖。既有约1MB data chunk警告保留，未降低阈值。所有新语义文本仍静态确定性帮助，不额外调用AI。

## 失败记录、限制和待办

- 首次SSH超时已解除，历史失败收据保留。
- 首次guards文字定位同时命中SVG title和说明，修正定位后通过；初次分类截图fixture残留规则，before_v2重拍。
- 初次新保护测试假定TypeScript旧JS API，现有TS7仅原生工具包；改成无外部依赖、严格展示允许清单后6PASS。未升级/安装依赖、未放宽业务断言。
- 首次共享样式浏览器导航抢在新服务启动前失败；health就绪后6组通过，启动竞态日志保留。没有删失败日志、伪称这些首次成功。
- **未解决新增功能回归：已覆盖检查中0；未覆盖项仍NOT_RUN。** 未逐一测试42帮助主题、所有草稿/错误编码/工作表组合、>20商品分页、浏览器409/任务取消/超时/权限/AI回退全组合、极长名/超大金额全组合、原生桌面200%及PDF逐页视觉检查。不得因此称全站最终验收通过。
- 现有环境没有完整Chrome和PDF渲染工具；没有为了验收安装系统依赖或改C盘。实际浏览器打印PDF已执行，但PDF逐页中文/分页视觉复核仍NOT_RUN；导出HTML及JSON/CSV值已核对。方向确认后补齐完整矩阵。
- 用户审美确认 PENDING；全站推广/合并main/稳定发布 NOT_RUN；正式部署/公开服务 NOT_APPLICABLE于此检查点。原演示不变。

## 预览与回滚

本机隧道已实测：基线 http://127.0.0.1:18110 ，样板 http://127.0.0.1:18111 。相同固定run入口见BEFORE_AFTER。它们只对当前Windows本机有效，非公开评委链接。

TASK/start_baseline.sh、start_candidate.sh分别对应本任务服务，受控最终干净检出可能使用start_verified.sh，实际运行路径/提交以 /assets/ui-release.json 和最终收据为准。查看tmux list-sessions/对应log，避免重复启动。回滚仅停本任务re-ui-preview，直接查看18110原版或以160a90c构建重开独立预览；无需恢复业务数据库。不要停止/改写共享正式服务。最终交付后再回读隧道manifest确认SHA。
