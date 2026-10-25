# 正式代码同步到个人仓库 main（2026-10-25）

本次仅整理和发布 Git 版本，未修改正式服务器源码、数据库、运行服务或算法。

## 哪一版是当前代码

- 目标仓库：`LSTongXXN/RetailEvidence-Studio`；目标分支：`main`。
- 内容依据：正式目录 `/home/ubuntu/AIC_Project` 的 164 个源码、配置、脚本和说明文件。
- 原个人 main：`0abb46edf134e8ad51c08fc2cda6aef60a74d412`。
- 团队整合基线：`CZH0919/AIC-2026-RetailEvidence` 的 `fix/20261023-product-integration`，提交 `ab0c6479ec9f81ecd2a8d7c9039efa0582e6c0be`。
- 正式目录后续修复归档提交：`e2c54a3fe72a9f14151ea2ca65deeebed245b44f`。
- 运行算法：`sales-v3.1.1`、`association-v2`，数据库代码 schema 6。包文件仍写 0.5.0；本次保留正式文件原文，不以包版本数字判断新旧。

团队基线已经通过合并提交 `2caaa49` 保留双方开发历史，原个人 main 是团队整合提交的祖先。本次直接继承这条提交链，再保存正式目录后续修复；无需重写历史或强推。

## 本次同步内容

完整同步正式目录的 backend、frontend 源码、依赖锁文件、scripts、docs 与根配置；不只同步日期补丁。相对团队提交的实际逻辑变化集中在日期解析、完整记录范围、月份选择、上传切换及草稿校验，详见同目录 `DATE_UPLOAD_FIX_20261024.md` 和 `MONTH_SELECTION_FIX_20261024.md`。其他部分文件带有正式目录既存 CRLF 行尾，按原字节保存。

排除运行数据库、商户数据、上传文件、历史报告产物、备份、模型、虚拟环境、node_modules、构建 dist、缓存、日志、凭据和主机信任文件。它们保留在原环境，不是源码仓库的一部分。

`FORMAL_SOURCE_MANIFEST_20261025.json` 登记上述 164 个文件的 SHA-256，可核对源码一致性。额外增加的本记录、清单和任务进度是仓库交付记录，不冒充正式目录原有文件。

## 历史与贡献在哪里

- 原 main 全部提交、作者信息、原有远端分支和 `v0.6.0`、`v0.6.1` 标签保留。
- 旧个人文档、图片、测试脚本有一部分已在队友整合过程中从当前文件树移除，但仍存在于旧提交和旧分支中。本次不把旧运行模块重新混回正式代码。
- 旧个人完整工作记录：[0abb46e 文件树](https://github.com/LSTongXXN/RetailEvidence-Studio/tree/0abb46edf134e8ad51c08fc2cda6aef60a74d412)，其中的 `docs`、`TASK_PROGRESS.md`、`CHANGELOG.md` 可追溯此前工作。
- 服务器团队合并记录：`/home/ubuntu/Project_Progress/10_23合并工作/Fix_work_record.md`。
- 本轮本机材料：`D:\AIC_RetailEvidence_Work\delivery_20261009_01\formal_main_sync_20261025_01`。
- 正式源码快照 SHA-256：`c8ff86ec36970e87b73eec4cb1ae61ededbe2da98caf56ef17bc049119242167`。
- 发布前 Git 全引用备份：本轮目录 `evidence/history-before.bundle`；原引用清单 `evidence/refs-before.txt`。

保留团队作者和原有来源说明；此次发布不代表个人独立原创，也不新增或替团队决定开源许可证。仓库继续私有。

## 本轮验证的真实结果

验证源码从正式快照提取到个人 runtime 目录，所有数据库、缓存和临时文件隔离。正式依赖只读复用，未安装或升级系统软件。

| 项目 | 状态 | 实际结果 |
| --- | --- | --- |
| 正式文件逐项 SHA-256 对照 | PASS | 164/164 一致，复查未发现正式源码在快照后变化 |
| 前端类型检查和 Vite 构建 | PASS | `npm run build`（包含 `tsc --noEmit`）通过 |
| 与正式静态资源对照 | PASS | 新构建 12 个文件全部与正式同名文件哈希一致；正式 dist 额外保留 22 个旧资源，不在本轮删除 |
| 日期边界验证 | PASS | `node scripts/test_calendar_dates.mjs`，26 项 |
| 历史报告选择 | PASS | `node scripts/test_report_selection.cjs "$PWD/frontend/src/reportSelection.ts"` |
| 销售信号展示 | PASS | `node scripts/test_sales_signals.cjs "$PWD/frontend/src/salesSignals.ts"`，6 个场景 |
| 原样后端 unittest 全量发现 | FAIL | 134 次测试执行：84 通过、50 ERROR；50 项均在旧测试准备阶段访问项目返回体时发生 `KeyError: 'id'` |
| 独立账号接口冒烟 | PASS | 13 项：注册、登录、项目创建回读、未登录限制、请求头检查、跨账号隔离、退出和会话失效 |
| 新增历史和候选源码高置信秘密模式扫描 | PASS（有限扫描） | 8 个新增历史提交、186 个新增历史 blob 及候选源码，未发现所扫描私钥/Token 模式或超 2MB 新增资产；不表示能证明不存在任何秘密 |
| 本轮完整浏览器业务重跑、真实 CPU AI 问答 | NOT_RUN | 本次是正式源码同步，未把历史验收当成本次通过 |

旧后端测试没有先注册/登录，也没有按现有认证约定准备修改请求头，因此不能直接用于宣称当前系统全量回归通过。独立账号冒烟采用真实接口和临时账号，未关闭鉴权、未修改生产逻辑。保留原失败日志，不删除或跳过原测试。本次将正式现状同步归档，不以此宣布一个全测试通过的新稳定版本。

原始日志在本轮 `evidence/`：`unittest.log`、`frontend-build.log`、`build-parity.json`、`calendar-tests.json`、`report-selection.log`、`sales-signals.log`、`auth-smoke.py`、`auth-smoke.json`、`secret-scan.json`。测试依赖已有服务器环境；单独克隆后需按依赖文件准备环境。

## 尚需维护的既有事项

1. 正式 README 前半部分仍有“没有账号认证”、schema 5、旧算法等历史描述，与后半部分账号章节及当前源码不一致。本次为保持正式原文未改写；当前能力以上述实际源码及团队交接记录为准。
2. 旧 API 测试需要更新合法登录准备步骤，再重跑完整回归；本次未扩大为产品修复。
3. `npm run build` 提示已有大分块警告；没有构建失败，未为发布修改依赖或分包逻辑。

## 安全与回退

正式代码、正式数据库和既有服务保持原状。本次没有部署动作，不需要恢复业务数据库。Windows 主动写入仅在 D 盘发布目录和 E 盘工作目录，SSH/Git 配置仅本次进程及本地仓库；不修改 C 盘配置。操作系统和 Codex 自身后台写入无法由此记录保证完全不存在。

需要查旧版时按提交检出或查看原分支，不要用旧 main 覆盖正式服务器。仓库需要回退内容时通过新的 revert/恢复提交，不强推，不删分支或标签。

推送成功与最终远端 SHA 以本轮目录 `evidence/final-publication.json` 为准；发布前的候选提交或本记录本身不能代替远端验证。
