# 正式站日期与表格上传修复记录 — 2026-10-24

完成时间（UTC）：2026-10-24T15:10:57.255195+00:00。用户明确授权直接修复团队正式目录 `/home/ubuntu/AIC_Project`；本轮没有建立开发副本。测试使用独立店铺，备份及测试证据位于 `/home/ubuntu/Project_Progress/10_24日期与上传流程复核_20261024_02`。

## 结论与适用范围

日期、月份和上传流程的本轮已覆盖检查通过：浏览器 121 项、日期边界单元检查 26 项。类型检查和生产构建通过；构建仍有既有大 chunk 提示，没有增加依赖。
这不是对系统未来绝无缺陷的保证，也不是完整重跑所有 AI、RF/RFM 或库存业务算法。用户 Windows Chrome 100% 点击原 DatePicker 后偏移未在服务器 Chromium 前测复现，不把推测写成已证实根因。

当前正式静态文件已更新，无 Web/AI 进程重启、无数据库迁移、无后端算法修改。旧静态资产全部保留。
本机现有 `http://127.0.0.1:18080` 隧道已实际返回 HTTP 200 与新 index 资产；无需更换浏览器或改变缩放来规避缺陷。

## 发现与处理

| 编号 | 依据 / 问题 | 正式修复 |
|---|---|---|
| DATE-01 | 用户报告点击4月1日变成3月；前测三时区30次原日期面板点击未复现 | 两个完整记录日期使用浏览器原生日历输入，直接保留 YYYY-MM-DD；不经 dayjs、UTC 或月份下标转换。分析月份继续使用直接 YYYY-MM |
| UP-01 | `state_before.json` 实际复现清空所有销售表后仍能开始分析、仍显示旧月份 | 清空来源立即清空元信息、月份及完整范围，按钮和提交均检查当前所选来源 |
| UP-02 | 源码确认换文件/重新读取未清除旧完整范围 | 重置范围、停业日、缺失日和确认状态；新上传失败不继续使用上一文件 |
| DATE-02 | 月汇总高级所属月份与分析月份是两个未同步状态 | 双向同步，保存、识别月份与运行月份一致 |
| DATE-03 | 后端建议上一个月可能没有实际记录（例如只有一月与三月） | 保留已有建议规则，但仅采用实际可选月份；缺口示例实际生成三月报告后验证默认不选二月 |
| DATE-04 | 日期错误原来在保存版本之后才被拦截，错误范围可能得到空结果 | 保存前校验真实日历日、起止顺序、1095天限制、月份与范围是否有交集、缺失/停业冲突；支持中英文逗号、分号与换行，去重后提交 |
| UP-03 | Excel 清空工作表可能按默认首表读取 | 新旧两条导入入口均显式要求至少一张表；不同表头仍保留原校验 |
| UP-04 | 日期列切换后可能缺少格式/时区，重复快速点击可能重复提交 | 提前要求确认日期格式/时区；异步工作使用即时互斥保护 |
| QUALITY-01 | 质量范围反向时可能先产生清洗策略再报错 | 日期范围先校验，错误时不创建策略/任务 |
| MSG-01 | “月份不在表里”不足以帮助定位原因 | 展示当前字段/时区识别的实际月份，明确下一步检查日期列、格式、时区或月汇总所属月份 |

完整范围与分析月份有不同含义：范围声明可用历史，分析月份选择要看的月报。部分月份覆盖仍允许，但保留受限说明；不把缺失日期补成零、不降低预测门槛。没有对应记录的月份仍会拒绝创建报告。

## 真实操作及对账

1. 空测试店铺上传 CSV，经字段、日期、范围到报告；反向日期、不可能日期、缺失与停业重叠、月份无交集均在创建版本/运行前拦截。
2. XLSX：说明页、正确工作表、清空选择、不同表头报错与恢复；GBK 分号 CSV 从错误读取恢复；日汇总/月汇总生成报告。
3. 三时区（上海、UTC、洛杉矶）输入两种起止日、闰日、跨年和12个月；日期/月份值不偏移。前测原 DatePicker 点击证据与后测输入行为分开保存，未冒充 Windows 原生日历点击重演。
4. 普通跨月原始行：3月31日、4月1日、4月30日、5月1日；四月报告为15件、200元。CSV、XLSX、GBK、日/月汇总均独立核对。
5. 带 UTC 偏移原始行：3月31日16:30Z 按中国标准时间属于4月1日；4月30日16:30Z属于5月1日。四月结果2件、20元。
6. 换文件、返回上一步再继续、无数据月份报错后修正、清空已有来源；错误不生成误导报告。
7. 旧“数据记录”导入：保存字段草稿、关闭、刷新、继续、人工确认并创建3行不可变版本。
8. 质量检查反向范围不产生策略/任务；实际下载HTML、全部商品CSV；四月报告刷新后run与数字不变。390px与1440px日期区域截图已逐张检查。
9. 你的青禾主 CSV（完全模拟，17,641行）实际从浏览器上传，完整范围2026-04-01～2026-09-30，分析2026-09。独立Decimal对账与系统结果：**销量10,640件，销售额66,434.40元**。

测试店铺：`e177a1e4-8082-48fb-a2ee-324c2435c83f`；青禾运行：`73742e05-bb4b-47b1-abe5-8dfc32970a6a`。原用户项目没有被修改。共享验收账号访问用户提供的项目版本接口返回404，未绕过账号隔离；无法据此断言用户原项目的具体映射设置正确。

## 可复核命令与证据

实际执行：

```sh
cd /home/ubuntu/AIC_Project/frontend
npm run typecheck
npm run build -- --outDir /home/ubuntu/Project_Progress/10_24日期与上传流程复核_20261024_02/build
cd /home/ubuntu/AIC_Project
node --experimental-strip-types scripts/test_calendar_dates.mjs
# 浏览器运行前 source /home/ubuntu/AIC_Shared/aic-env.sh，环境指向本轮tmp/cache/fonts.conf和现有浏览器依赖
CASE=transactions node /home/ubuntu/Project_Progress/10_24日期与上传流程复核_20261024_02/flow_after.cjs
# 同一脚本分别执行 xlsx encoding monthly daily timezone replace unavailable gap sources qinghe
node /home/ubuntu/Project_Progress/10_24日期与上传流程复核_20261024_02/extra_after.cjs
node /home/ubuntu/Project_Progress/10_24日期与上传流程复核_20261024_02/legacy_after.cjs
```

机器报告：`evidence/FINAL_ACCEPTANCE.json`、`evidence/acceptance.csv`。
每个上传场景保存 `after-场景.json`（真实请求、断言、run/version）和 `result-场景.json`（结果及参数）。
数据来源及哈希：`fixtures/manifest.json`、`evidence/qinghe_independent_reconciliation.json`。
截图：`before-april-calendar.png`、`before-empty-sources.png`、`after-date-390.png`、`after-date-desktop.png`、`report-*.png`。
导出：`report.html`、`products.csv`。日志：`build.log`。源码发布收据：`deployed.json`。

测试脚本调试期间出现过按钮包含图标/双字空格导致定位失败、多选读取时弹层没有关闭、缺口测试误重新打开默认四月来源等失败；这些是测试脚本问题，已修正定位/保持当前报告并重跑，没有删除业务断言。保留 `failure-*.txt/png`、`legacy-failure.txt/png`，不得把这些旧失败截图当最终PASS证据。

## 修改文件与版本

- `frontend/src/calendarDate.ts`
- `frontend/src/coverageReadiness.ts`
- `frontend/src/components/CoverageConfirmation.tsx`
- `frontend/src/components/SalesImportWizard.tsx`
- `frontend/src/components/ImportEditor.tsx`
- `frontend/src/components/QualityWorkspace.tsx`
- `scripts/test_calendar_dates.mjs`

正式目录无`.git`，因此本轮没有伪造 Git commit，也没有将旧 main 覆盖正式代码或声称已推送 GitHub。团队合并基线 ab0c647 来自既有交接信息；本轮实际可核实的是文件哈希与补丁。

当前 index SHA-256：`67b633cf938af65644c923ae2d04b5f6466926513b83c1463f61f7fa0b3c639a`。
全部修改文件哈希见 `FINAL_ACCEPTANCE.json`；用于团队版本管理的统一补丁：`/home/ubuntu/Project_Progress/10_24日期与上传流程复核_20261024_02/formal_date_upload_fix.patch`。合并补丁前须先核对团队分支当前差异。

## 数据保护、备份和回滚

修改前源码归档：`backup/source_before.tgz`，SHA-256 `be8feb2c21da1885b6555fe9ad062a5f7f676d7ec3d845143ae832532edae998`。
活动数据库通过SQLite在线backup API保存为`backup/database_before.sqlite3`，前测quick_check=ok；不是热库文件直接复制。
最终逐行对比：原39条运行、12个版本、12个映射、10条清洗策略、6条业务备注均未改动；后端文件未改（`history_integrity.json`）。测试新增数据仅在独立测试店铺。
回滚仅需先检查后续队友改动，再从归档恢复本轮修改的前端文件及旧index；新旧资产均在dist中，不需要恢复业务数据库。此为待需要时执行的回滚说明，本轮未进行回滚。
本地主动写入仅D/E，浏览器、缓存及临时文件均在服务器本轮记录目录；未更改C盘配置、凭据、全局环境。无法对操作系统/Codex自身后台写入作绝对零写入保证。

## 给使用者的当前填写方式

Chrome 100%即可。刷新正式网页（Ctrl+F5），重新打开上传窗口；CSV与XLSX同名主文件二选一，不要重复追加。
对于青禾四月至九月主文件，选择销售日期“交易时间”、分析月份2026-09、中国标准时间、正常销售记录；确认完整范围2026-04-01至2026-09-30，缺失与停业日期留空（主文件无这两类声明）。
十月不在这份主文件中；必须另行导入十月文件后才能分析十月。新规则不会修改历史报告，旧错误月份/范围报告应以正确设置重新生成，原报告继续保留。
