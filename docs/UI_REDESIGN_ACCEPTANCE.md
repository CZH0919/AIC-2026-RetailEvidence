# 商业化 UI 全站验收

2026-10-19，开发可用性自查。用户已确认三类样板及减少常驻小字的方向，并授权推广全站。没有将模型操作称为真实商户研究。

## 版本、范围与收据

- 基线 main：160a90c47b6f2a675386355cc283fb869e85334a；样板批准版本40ad43cdbb2d2b03b293761257661fcb0b497d38。
- 先提交基线/官方研究7038658，再做样板；全站补充28张改前截图及批准记录独立提交6df42a8，再提交共享样式bb5b539、8组件展示c0ab33af14c666e375055c0f6bb7a331d29888a9、测试e924adc及后续测试截图修正/文档。产品文件此后未改。
- 分支feature/commercial-ui-refresh；应用仍0.6.3/schema5/sales-v2.2.0。本轮不改业务版本、后端、API、数据库、路由、算法、模型提示、依赖或导出模板。
- TASK为个人隔离 updates/ui_refresh_20261019_01；baseline18100、已批准样板18101、全站候选18103各自state/storage；模型18102。AIC_Project及共享服务完全不参与写入。
- 本文记录候选实际测试。候选启动脚本的AIC_SOURCE_COMMIT仍40ad，不能将该运行元数据误当成产品修改不存在；产品按精确文件哈希和展示允许清单对应c0ab33a。发布后必须从实际origin/main干净检出再测，运行元数据、构建文件哈希与最终SHA由TASK/final-main/evidence/release_receipt.json及Windows evidence/final-main/记录；未取得该收据不能认定最终发布完成。
- Windows所有主动输出D盘；缓存/profile/TMP在D或远端个人目录。无C盘批准例外，无全局配置/系统安装/sudo。无法保证操作系统或Codex后台零写入。

## 数据与确定性结果

青禾便利店完全模拟包01_完整交易明细_2026-04至09.csv，SHA256 e34d6cf870876e2baff8af00e45a74e70cea5a5a228f603fad21f30258425923；17,641行、8,700订单、240模拟客户、12商品。另有同源XLSX及合成GB18030/双工作表错误边界文件。不是实际商户数据或收益证明。

固定项目8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a，版本079c4221-28b1-460c-9df2-be174312d824，run35cf3631-064c-4a90-a845-b06485eb9a3e（2026-09）。新CSV完整流程项目689c6594-396e-4c17-91cb-fef7dbf19089、版本86ec2cc2-5a56-4f48-b46d-9408de893366、run29815fdb-7c67-4cf0-81f5-963014ca45d4。XLSX使用独立新项目，原始ID见whole_xlsx.json。

9月66,434.40 CNY /10,640件/1,326单/12实物商品；8月70,402.60/11,276。P006七天177、MAE42.25；库存10、到货7、备用3、包装6，结果168。RF、RFM和共购publishable=true。真实CPU问答ai_used=true、mode=model_inference、evidence_id匹配冻结run/分类。

17项对账PASS：冻结完整result、7种JSON/CSV/manifest、HTML；新报告summary/products/forecast/anomaly/quality/notices完整子树；预测/库存；14次POST/PUT请求的路径、业务字段、次数。仅新实体UUID、捕获时间、项目名创建时间戳可归一化，业务数字与确认字段不能忽略。冻结result SHA256为221fc60b179b6e930f0871a04134afb3a34724029f3b3e8a5835cc67df989f2c。见[机器对账](verification/ui_redesign/whole_equivalence.json)。

## 实际检查结果

不同粒度不相加为一个总测试数。下列浏览器组共50 PASS、0最终FAIL/0BLOCKED；不表示所有可能组合已执行。中间定位失败和重试保留在TASK中。

|测试/命令|实际验证|结果与证据|
|---|---|---|
|npm run build -- --configLoader runner|TypeScript类型检查及Vite构建|PASS；whole_build.txt|
|node --test scripts/ui_redesign/test_presentation_contract.cjs scripts/ui_redesign/test_report_guidance.cjs scripts/ui_redesign/test_whole_presentation.cjs scripts/test_ux_guidance.mjs|17项，包括以40ad为基线的49项精确展示编辑白名单，重建完整8组件比较；路由/业务键/校验/后端不变|17 PASS；whole_contracts.txt|
|.venv/bin/python -B -m pytest -p no:cacheprovider scripts/test_sales_v2.py scripts/test_record_classification.py scripts/test_task_safety.py scripts/test_ai_contract.py scripts/test_field_assistant.py scripts/test_user_facing_copy.py -q|独立unit库，单任务/分类/历史报告/AI合同等|76 PASS+6subtests，12.58s；whole_pytest.txt；既有httpx弃用警告1|
|browser_e2e.cjs|新建、CSV真实上传、13字段及口径、分类/范围、月报、商品/异常/原始行、备注回读、库存168、真实CPU AI、HTML/CSV/JSON/PDF、质量、RF/RFM/共购|9组PASS；whole_csv.json；规范原证据whole-site/csv/evidence/clean|
|browser_xlsx.cjs|真实XLSX导入、月报、JSON下载回读|3组PASS；whole_xlsx.json|
|browser_ui_guards.cjs|8/9月切换刷新/前进后退/复制run地址、月汇总无日趋势、商品搜索排序筛选无结果/返回、帮助/草稿、真实无效报告及隔离网络故障重试|6组PASS；whole_browser_suite.json及TASK日志|
|browser_prototype.cjs|1440/768/390分类标签、下拉边界、未确认禁用、帮助不提交/不丢草稿、720布局|4组PASS；whole_browser_prototype.txt；720仅布局等效，真正缩放见下|
|browser_copy_density.cjs|1440/390固定说明进入帮助、按需展开、键盘、不触发POST、未知风险直接显示及导出值一致|6组PASS；whole_browser_copy_density.txt|
|browser_whole_interactions.cjs|项目必填/编辑PATCH回读/搜索分页、原始预览/版本、真实草稿保存继续、字段AI展开不丢输入、质量五视图/范围/过程、真实双会话备注409保留草稿、三会话只读|6组PASS；whole_whole-interactions_results.json；其中21种帮助逐项Enter/Tab/Esc/焦点/不提交|
|browser_native_zoom.cjs|独立完整Chromium用chrome.tabs.setZoom/getZoom=2，1440外窗/720CSS视口/DPR2；项目/月报/帮助/商品/字段/质量7状态|7组PASS；whole_native_zoom.json；真实缩放非CSS或DPR模拟|
|browser_edge_ui.cjs|TXT拒绝、错误编码422→GB18030恢复、错误分隔符恢复、真实放弃草稿DELETE回读、多表头不一致422→正确工作表、全部导出选项与附页打印、隔离AI503/超时/模板状态|5组PASS；whole_edge-ui_results.json。AI错误为隔离故障注入，不冒充真实模型成功|
|scripts/browser_sales_drawers.cjs|1440/390 × 首次/先开依据，商品/依据/帮助实际层级、命中测试、焦点、库存/备注/问题草稿、真实AI及导出|4组PASS；whole_after_18103.json|

浏览器环境：RETAIL_TEST_ROOT显式个人测试根；RETAIL_BASE_URL=http://127.0.0.1:18103；PLAYWRIGHT_MODULE/BROWSERS_PATH/LD_LIBRARY_PATH/fontconfig指向已有个人runtime，HOME/TMP/XDG全部个人目录，OMP/BLAS线程2。正常流程不使用Mock。CSV与XLSX必须用不同RETAIL_TEST_ROOT，脚本run_import_regression.py已固化顺序与分目录，避免同名证据覆盖。

## 视觉、打印和体积

- 补充全站28张前+28张后，覆盖项目/编辑/空态/上传/解析/映射/已保存数据/质量及RF/RFM/共购，1440/1280/768/390；原样板另有20对和说明收纳4张。对比全部缩略图并查看关键原图/质量长页分段；未以截图文件存在替代人工查看。
- 真正200%截图第一次被Playwright裁成半个视口、抽屉动画未完成。保留初次图片，改用CDP原生视口捕获并等待绘制稳定后重跑7项，完整1440×913截图再视觉检查。此为证据采集修正，未改产品或放宽断言。
- 宽表在明确容器横滚，页面主体无意外横滚；语义风险文字和金额、单位、零与未知区分保留。下拉/帮助/商品/依据叠层可点击，未添加全局z-index覆盖。
- 真实浏览器HTML打印默认PDF2页、全关注商品附页PDF3页；在Windows用已安装pypdfium2渲染逐页查看并提取中文文本，金额/数量/12商品核对。默认第2页和附页末页有现有留白，导出样式不在本次修改范围。
- 构建无新增依赖/字体/CDN/动画。体积以最终收据逐文件清单比较；约1MB data chunk的既有Vite警告保留，未降低阈值。测试用完整Chrome与12个缺失浏览器库仅下载/解包到个人目录，无sudo或系统安装，与产品依赖无关。

## 保护矩阵、问题和未运行项

[逐项保护矩阵](UI_REDESIGN_PROTECTION_MATRIX.csv)关联15能力组、具体入口/字段及证据。新解释采用原生details或既有HelpHint，子内容持续挂载，不改组件key/请求/确认条件。8组件加CSS的本次改动与已批准销售页/分类样板分批提交。

已覆盖检查未发现新增未解决功能回归。初次合同白名单重建、异步分页/抽屉关闭定位、帮助定位背景inert、原生Chrome缺库/短Unix socket路径、截图裁切和第一次CSV/XLSX同名证据覆盖均有原记录；修正测试工具后重跑，不删除断言/冻结输入。规范CSV已独立完整重跑，原混合目录仅XLSX结果可用，不能用其覆盖后的requests充作CSV请求证据。

|范围|状态|说明|
|---|---|---|
|>20商品实际翻第2页、极长商品名/超大金额全部组合|NOT_RUN|本包12商品；项目分页已实际通过，不混同商品分页|
|42帮助主题每个都在全部视口执行所有键盘组合|NOT_RUN|21主题本轮系统检查，其他重点帮助在既有销售/抽屉套件中覆盖；静态内容合同覆盖全部，不能声称浏览器穷尽|
|真实排队/超时/取消/重启恢复每种浏览器状态、完整权限异常矩阵|NOT_RUN|本轮真实任务完成/错误恢复和后端任务测试通过；未进行共享服务重启或无界压测；故障注入单列|
|本轮全项目Ruff|NOT_RUN|未改Python产品；历史全scripts132格式问题见文案验收，不能标为本轮PASS|
|真实商户或独立非开发者研究|NOT_RUN|本轮为开发自查|
|替换现有演示/共享正式部署/公网开放|NOT_APPLICABLE|用户要求另行批准；本轮仅独立预览与仓库代码|

## 发布、查看和回滚

最终从GitHub实际main重新fetch、干净检出构建并做完整CSV/AI/导出及关键烟测；收据明确最终SHA、构建哈希、run ID、测试状态和端口。独立全站预览拟用本机18113→服务器127.0.0.1:18104，必须以实际收据/HTTP构建标识为准，未启动时不得声称可用。固定项目/run同上。

旧的已批准样板本机18111→18101和原版18110→18100保持。回滚直接访问原入口，或仅停止新建re-ui-final并用已验证40ad构建另开独立端口；不需要还原业务数据库，不停止队友服务。源码变更需要Git revert普通提交，禁止强推或重写历史。
