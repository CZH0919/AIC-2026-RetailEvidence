# 0.7.1 系统复查验收记录

执行日期：2026-10-23。基线为 `7b225be22ccdba811e9bdfd8c0610aca82083915`（0.7.0 / schema 6 / sales-v2.2.0），工作分支为 `feature/system-polish`。本轮修复版本 0.7.1，schema 和销售算法标识不变。

**本文件当前记录候选工作树的真实测试。最终提交、GitHub main 及干净检出复验尚未在本文件确认，状态为 NOT_RUN。** 候选日志中出现的基线 HEAD 不能作为最终源码 SHA。完成发布核验后，应根据 `evidence/release.json` 的实际提交和日志更新，不能仅修改本段文字宣布通过。

## 1. 环境、证据与版本边界

以下证据路径相对远端隔离任务根目录 `/home/ubuntu/retailevidence_personal_20261009_01/updates/system_polish_20261023_01`，文中以 `$TASK` 表示。Windows 归档根目录为 `D:\AIC_RetailEvidence_Work\delivery_20261009_01\system_polish_20261023_01`；本地仅归档部分截图和无凭据证据，不把浏览器 profile、cookie 或活动数据库提交 Git。

- Ubuntu CPU 环境，复用已安装 Python 3.12、Node 24.21.0、Chromium/Playwright 与 CPU 模型运行库；无新系统依赖、外部字体或图片。
- 原有登录演示服务 18108 保留。18109 最初运行基线；专项复测前已更新为本轮候选后端和静态构建，只重启自己的隔离进程，继续使用隔离基线测试库。18110 为另一候选服务和独立测试库。端口不能单独证明源码版本。
- 主流程在 18110 实际注册新账号完成；专项 `after_focused4` 在更新后的 18109 复用基线浏览器账号和冻结报告；补充 XLSX/月汇总在 18110 新账号执行。
- SQLite 一致性备份已核验 `integrity_check=ok`、0 外键错误、12 张表，清单位于 `backup/manifest.json`。未覆盖共享正式项目或其数据库。
- 本轮主动本地写入限定 D/E 工作区；远端 profile、缓存、临时文件和产物均在个人任务目录。未批准或执行 C 盘项目写入；无法保证 Windows/Codex 自身后台零写入。

## 2. 候选测试汇总

各行统计单位不同，不能把单测、子测试和浏览器步骤相加声称覆盖了同等数量的功能。最后一轮相关测试均通过，早期失败记录继续保留。

| 测试 | 实际结果 | 可核查证据 |
|---|---|---|
| 后台完整 pytest | PASS：96 tests + 6 subtests；31.44 秒 | `evidence/latest_pytest.txt` |
| 后台 Ruff | PASS | `candidate/evidence/ruff.txt` |
| 前端 Node 合同/异步状态/帮助测试 | PASS：15，0 fail / skipped | `evidence/latest_frontend_tests.txt` |
| TypeScript 与生产构建 | PASS；重连键盘修复后重新构建 | `evidence/focus_fix_build.txt` |
| 真实注册及业务主流程 | PASS：12 组 | `candidate/evidence/full_browser.log`；`candidate/full_browser/evidence/clean/browser_results.json` |
| 真实浏览器专项 | PASS：12 组，0 pageErrors | `evidence/after_focused4.log`；`after_focused4/evidence/system-polish/results.json` |
| XLSX/月汇总补充导入 | PASS：4 组，0 pageerror | `candidate/browser_import_modes_attempt4/evidence/results.json` |
| 窄屏抽屉稳定性补测 | PASS：1 组；390×844，x=0、width=390 | `candidate/browser_import_modes_attempt4/evidence/resize_retest.json` |
| 冻结业务结果及商品 CSV 对账 | PASS：13 项 | `evidence/deterministic_comparison.json`；可重复脚本收据 `evidence/deterministic_comparison_replayed.json` |
| 最终提交/远端 main 一致性与干净复验 | NOT_RUN：由后续发布核验更新 | 预定收据 `evidence/release.json`，当前不得视为已通过证据 |

后台日志有一项 Starlette TestClient/httpx 弃用警告；构建仍有约 1 MB 的既有 data 分块体积警告。本轮未升级依赖或通过关闭警告降低标准。最后候选构建 CSS 60.94 kB、主 index JS 129.60 kB、SalesWorkspace JS 78.69 kB，具体散列见构建日志。

主流程候选项目为 `15b0d7b3-8357-45f4-b142-04c71f733b6d`，月报 run 为 `3dbfe7b9-db36-476e-b62b-2494f6b5be2d`。专项冻结项目为 `0f859538-68ca-43ef-be40-1344e5d990d3`，run 为 `49527609-e9f6-4292-a972-678af6552c48`。这些是测试定位信息，不是用户的正式数据。

## 3. 实际覆盖的操作

主流程的 12 组包括：注册入口及四视口、CSV 上传和字段确认、业务分类及月报、商品/异常来源/备注、预测和库存、真实 CPU AI 与导出、质量工作区、RF、RFM、商品共购、修改密码/退出/重新登录、第二账号不能读取第一账号数据。HTML、商品 CSV、JSON、原始行审计均真实下载；HTML 在 Chromium 中打开并生成 A4 PDF。AI 正常路径断言 `ai_used=true` 及 evidence_id 与本次报告/分类一致。

以下专项逐一验证本轮风险，数据仍由真实服务处理：

| 测试 ID | 验证内容 | 最终结果 |
|---|---|---|
| 01 | 已填编辑草稿后注入 `/auth/me` 500；不误退出，旧界面不可点击，Tab/Shift+Tab/Escape 不穿透，重新连接后草稿保留 | PASS |
| 02 | 历史月报经过销售、商品、数据、更多分析导航，刷新及前进后退仍保持 run | PASS |
| 03 | 真实 CPU AI 响应延迟交付后切换报告，不把旧答案显示到新报告 | PASS |
| 04 | 原始行响应延迟后切换商品，不显示另一商品记录 | PASS |
| 05 | 库存保存响应延迟后切换报告，不回写另一月份的参考值 | PASS |
| 06 | 点击字段标签聚焦正确输入；空格/Tab/Escape 操作帮助，输入保留并返回焦点 | PASS |
| 07 | 检查返回前修改月份，旧检查不能重新启用生成 | PASS |
| 08 | 1440/1280/768/390px 页面和表格；依据及帮助叠层不遮挡；200% 等效布局 | PASS |
| 09 | 全部操作后回读冻结报告，业务结果未修改；无未捕获脚本错误 | PASS |
| 10 | 同商品计算期间修改库存，旧响应失效；已保存结果与当前输入明确区分 | PASS |
| 11 | 月报提交返回前修改月份，旧响应不关闭或替换新设置 | PASS |
| 12 | 月报提交返回前关闭并重开设置，旧响应不抢走新草稿 | PASS |

500 是明确标记的隔离异常注入，不代表正常服务曾返回 500。慢请求测试先获得真实服务器响应，再延迟交付浏览器；没有使用假算法结果替代正常业务流程。200% 使用 720 CSS 像素、deviceScaleFactor=2 模拟等效布局，未宣称是浏览器菜单原生缩放操作。

### 候选中发现并修正的键盘缺陷

最初的重连遮罩能阻止鼠标操作，但页面原有编辑框通过 body portal 挂载，Tab 可绕到遮罩后的编辑界面，Escape 也可能影响下层弹窗。此问题在候选浏览器检查中发现，不能归为已通过。

现已在重连期间限制焦点和 Tab/Escape 事件，保留原编辑器挂载及草稿，重连结束移除限制并恢复原焦点。修复后重新构建，`after_focused4` 的第 01 组实际通过正向/反向 Tab、Escape、鼠标阻挡及重新连接回读；`auth_focus_trace.json` 和 `auth_reconnect_draft.png` 位于该专项证据目录。

## 4. 测试数据与数值核对

青禾便利店数据为**合成演示数据**，不代表真实商户或真实用户研究。原 CSV 为 `01_完整交易明细_2026-04至09.csv`，17,641 行、240 名模拟客户，SHA-256：

`e34d6cf870876e2baff8af00e45a74e70cea5a5a228f603fad21f30258425923`

| 案例 | 实际值/限制 | 证据 |
|---|---|---|
| 完整明细 2026-09 | 销售额 66,434.40 CNY；销量 10,640；12 商品；1,326 订单 | 主流程 `sales_run.json`、`report.json` |
| 完整明细 2026-08 | 销售额 70,402.60 CNY | 主流程历史比较及专项冻结结果 |
| 普通整数备货 | 预测177、库存10、确定到货7、备用3、每包6 → 168 | 主流程 `inventory.json`；后台边界测试 |
| 小数包装边界 | 预测177、库存175.6、每包1.4 → 1.4；修复前浮点计算为2.8 | `scripts/test_system_polish.py`、`before_boundary.txt` |
| XLSX 两工作表 | 从原 CSV 的9月前60行保留原列、分为两张销售工作表；销量275、金额1,722.8、12商品 | 补充 `data_manifest.json`、`xlsx_run.json` |
| 独立月汇总 | 原9月2,711行以 Decimal 按商品汇总为12行；销量10,640、金额66,434.4；无日趋势、不发布预测、无库存计算 | 补充 `monthly_run.json`、`monthly_limited_report.png` |
| 缺金额字段 | 使用行金额但未映射该列 → 422，数据版本数仍为0；补齐后正常创建 | 补充 results、页面文本和截图 |
| 空分类规则 | 显示需补全规则，检查与生成按钮禁用 | `empty_classification_blocked.png` |

补充 XLSX 项目/run：`61b30218-0870-4558-b596-a2cc8d510aa1` / `62804f95-357c-4625-96b4-816f080ef6cf`。月汇总项目/run：`de6e5037-707a-4e91-a73a-0f4f646a3140` / `7ec76fbf-a237-4bab-8756-87a6dd46e696`。输入文件各自哈希及派生规则保存在 `data_manifest.json`，不改原 CSV。

确定性比较严格核对 `month`、`summary`、`chart`、`previous_chart`、`products`、`attention_ids`、`highlights`、`actions`、`forecast`、`anomaly`、`quality`、`notices`，以及解析后的商品 CSV。字段内没有忽略、四舍五入或归一化业务数值；只通过明确字段清单排除这些字段以外的上下文 UUID、版本标识。CSV 列名、行顺序和实际值均比较。小数包装是明确修正的缺陷边界，不以错误旧值作为必须保持的基线。

## 5. 已执行命令与复跑条件

只对个人隔离副本执行。已有运行库环境包含 `PLAYWRIGHT_MODULE`、`PLAYWRIGHT_BROWSERS_PATH`、`LD_LIBRARY_PATH`、`FONTCONFIG_FILE` 和 `FONTCONFIG_PATH`；`HOME`、`TMPDIR`、`TEMP`、`TMP`、`XDG_CACHE_HOME` 等均指向任务目录，Python 禁写字节码。下列是本轮实际运行的程序入口及关键参数；复跑时另建输出目录，避免覆盖证据。没有授权将其指向共享在线业务库。

```sh
# 在相应隔离源码目录中
PYTHONPATH=backend:scripts .venv/bin/pytest scripts/test_*.py -q
.venv/bin/ruff check backend/app scripts/test_system_polish.py
node --test scripts/test_ux_guidance.mjs scripts/test_async_scope.mjs scripts/ui_redesign/test_report_guidance.cjs
cd frontend
npm run build -- --configLoader runner
```

本轮 Node 实际程序为 `/home/ubuntu/AIC_Shared/tools/node-v24.21.0-linux-x64/bin/node`。真实浏览器入口：

```sh
RETAIL_TEST_ROOT="$TASK/candidate/full_browser" \
RETAIL_BASE_URL=http://127.0.0.1:18110 \
node "$TASK/candidate/source/scripts/browser_auth_journey.cjs"

RETAIL_TEST_ROOT="$TASK/after_focused4" \
BASELINE_JOURNEY_ROOT="$TASK/baseline_browser3" \
RETAIL_BASE_URL=http://127.0.0.1:18109 MODE=after \
node "$TASK/source/scripts/browser_system_polish.cjs"

RETAIL_TEST_ROOT="$TASK/candidate/browser_import_modes_attempt4" \
RETAIL_BASE_URL=http://127.0.0.1:18110 \
RETAIL_PYTHON="$TASK/candidate/source/.venv/bin/python" \
RETAIL_SOURCE_CSV=/home/ubuntu/retailevidence_personal_20261009_01/demo_dataset_20261014_01/data/01_完整交易明细_2026-04至09.csv \
node "$TASK/candidate/source/scripts/browser_import_modes.cjs"
```

主流程根目录的 `data` 为既有演示数据的只读链接。专项只在主流程关闭浏览器后复用其测试 profile，禁止并行占用；账号随机生成且不记录密码。导入补充的四组通过后，为避免 resize 动画中间帧被误认成裁剪，增加了抽屉 transform 结束与视口边界断言；同一账号/报告的新增断言已独立实际复测，见 `resize_retest.json`。这不冒称最后修改后的脚本已经重新执行了全部四组。

以下可重复对账命令已对实际文件执行，产生13项 PASS：

```sh
"$TASK/candidate/source/.venv/bin/python" -B \
  "$TASK/candidate/source/scripts/compare_system_reports.py" \
  --baseline "$TASK/baseline_browser3/evidence/clean/sales_run.json" \
  --candidate "$TASK/candidate/full_browser/evidence/clean/sales_run.json" \
  --baseline-products "$TASK/baseline_browser3/evidence/clean/products.csv" \
  --candidate-products "$TASK/candidate/full_browser/evidence/clean/products.csv" \
  --output "$TASK/evidence/deterministic_comparison_replayed.json"
```

脚本缺字段、值不一致或读取失败会输出 FAIL 并以非零退出；CSV 参数必须成对提供。最终提交复验可复用该脚本，另存收据。

## 6. 失败历史、未覆盖及发布门槛

- 原代码新边界测试为 **8 FAIL / 3 PASS**，详见 `evidence/before_boundary.txt`；修复后纳入96项后台测试。不得删除前测记录或当作最终失败混算。
- 早期浏览器尝试有启动早于服务就绪、缺少数据只读链接、选择器/工作表 Escape 时序和超时；分别保留原日志。补充 attempt1/3 失败、attempt2/4 成功，最终四组依据 attempt4；原过渡帧截图保留，以 `monthly_mobile_stable.png` 核对稳定布局。
- 候选曾发现重连键盘穿透，已修复并通过专项复测；不以最初候选的正常主流程替代该项证明。
- NOT_APPLICABLE：历史纯UI任务“后端/路由源码相对旧基线完全不变”的断言不适用于本轮明确业务边界修复。原测试文件保留，其他业务/安全/帮助断言继续执行。
- NOT_RUN：最终 Git 提交干净检出后的完整/关键复验、GitHub origin/main SHA 再核对；由发布收据更新。
- NOT_RUN：真实商户试用、独立非开发者操作、长时间负载与压力测试、所有浏览器/读屏软件组合、原生浏览器菜单200%缩放。本轮属于开发阶段可用性自查。
- NOT_RUN：公网 HTTPS/鉴权部署、邮箱找回/验证、多角色团队协作、共享正式环境切换。现有账户隔离不等同已完成互联网生产部署审查。
- 本轮没有重跑全部公开数据大型算法实验，也没有穷举所有队列取消/重启/超时的浏览器组合；现有后台回归与已列出的真实UI路径通过，只代表其覆盖范围。

后续只有在最终提交、构建来源、远端 SHA 与新收据一致时，才能报告最终仓库交付通过。发布默认保持原18108及共享正式服务，提供独立预览；替换现有演示须单独授权。schema 6不变，回退继续使用原0.7.0源码/构建及服务，不需回滚业务数据库。
