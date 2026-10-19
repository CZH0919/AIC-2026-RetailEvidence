# 2026-10-19 商业化 UI 改版恢复点

## 当前状态

- 分支：feature/commercial-ui-refresh；源代码基线 origin/main `160a90c47b6f2a675386355cc283fb869e85334a`（应用0.6.3），已实际fetch和ls-remote核对。
- 当前仅保存准备材料。第一阶段实际页面基线 **BLOCKED，未完成**；没有修改UI、后端、算法、数据库或旧演示，没有开始三页样板。
- 两次严格SSH连接超时；补充TCP检查同样超时。本机18092/18095均无监听。仅能认定当前不可达，不能断言实例关机。
- 主要开发仍应在服务器个人隔离目录进行；不以本地静态页面、Mock或历史截图替代当前运行验收。

## 位置

- 本机工作区：D:/AIC_RetailEvidence_Work/delivery_20261009_01/ui_refresh_20261019_01；源码在source，工具tools，日志logs，收据evidence。
- 缓存/临时：沿用上层 Invoke-InWorkspace.ps1 的 D 盘进程重定向；无C盘主动写入或获批例外。
- 远端计划：/home/ubuntu/retailevidence_personal_20261009_01/updates/ui_refresh_20261019_01，尚未连接验证或创建。
- 现有个人演示及共享 AIC_Project 均未变更；没有备份活动库、迁移、重启或部署。

## 已执行

1. 安全读取进度与原交接，确认D/E空间及工具；读取已有D盘脚本/主机信任配置，保持严格校验，不输出私钥。
2. 从原本地完整历史复制独立Git，使用原专用Deploy Key fetch正确仓库；保留upstream和历史作者。
3. 清点真实React/AntD依赖、路由、API/状态/帮助/弹层与样式，形成15类保护矩阵。没有声称页面都已验证。
4. 查阅Shopify、Linear、Atlassian、AntD官方公开资料，形成11条推荐规则和基础规范；官方截图像素未获得，访问边界如实记录。
5. 原帮助合同 `node --test scripts/test_ux_guidance.mjs`：3PASS；冻结模拟CSV以Decimal独立对账全量与6个月：7PASS。合计10个已执行用例PASS、0FAIL；运行环境BLOCKED、实际浏览器与改后检查未执行。

## 文件与证据

- docs/UI_REDESIGN_BASELINE.md：当前源代码和输入基线、运行阻塞、请求/状态保护、源码风险与恢复顺序。
- docs/UI_REDESIGN_DIRECTION.md：真实官方来源、访问边界、推荐方向、11条应用规则、视觉规范、拒绝采用内容及审美确认检查点。
- docs/UI_REDESIGN_PROTECTION_MATRIX.csv：15类入口/字段/动作/合同/源文件/用例，基线BLOCKED、改后NOT_RUN。
- docs/verification/ui_redesign/：原帮助日志、代码合同哈希、冻结输入独立核算、GitHub检查及连接收据。
- 完整任务历史继续保留在上层D盘 TASK_PROGRESS.md；本文件仅是本分支恢复点。不能凭进度文字判验收成功。

## 必须继续的下一步

1. 服务器恢复可达后先重读本文件和上述原始证据，读取远端HEAD/status/进程cwd/健康/UI收据，确认当前实际部署与main差异，不覆盖队友修改。
2. 检查新目录/端口；SQLite在线一致性备份、验证与必要storage清单，在个人目录建立独立基线和候选环境。
3. 在未改UI的当前main实际浏览全流程、运行适当旧测试，记录所有未通过项、真实请求/回读/导出、冻结结果、桌面/窄屏截图及构建体积。补齐基线并独立提交后才修改业务页面。
4. 仅三类真实数据样板：月报；商品列表及详情；复杂字段映射/分类表单。保持后端、算法、输入和状态合同；分批提交并回归。
5. 提供同数据/报告/视口前后截图、受限或错误状态及独立预览；**停止全站扩展等待用户确认视觉方向**。确认前不合并main、不替换旧演示。
6. 确认后才继续全站实施、各视口/200%缩放/键盘/弹层/端到端/CPU AI/导出及最终SHA验收。尚无UI_REDESIGN_ACCEPTANCE/BEFORE_AFTER完成证据，不得宣称交付。

回滚：目前无产品改动，无需恢复任何数据库或服务；仅独立本地准备分支。
