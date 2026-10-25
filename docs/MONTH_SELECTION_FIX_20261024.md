# 分析月份选择修复记录（2026-10-24）

## 交付范围与位置

本次按用户明确要求，直接修改团队正式目录 `/home/ubuntu/AIC_Project`，没有新建开发副本。备份、测试脚本和证据单独存放于 `/home/ubuntu/Project_Progress/10_24月份选择修复_20261024_01`，该目录不是另一份开发项目。

- 正式业务源文件：`frontend/src/components/SalesImportWizard.tsx`。
- 正式静态产物：`frontend/dist`，已发布；新资源先写入，最后原子替换 index.html，并保留原有20个静态资源以兼容尚未刷新的页面。
- 现有入口：http://127.0.0.1:18080/projects ，原SSH隧道继续使用。
- Web保持127.0.0.1:8000，AI保持127.0.0.1:8081；未重启两项服务。
- schema保持6；48个已有后端文件哈希均未改变。

## 问题、前测与实际处理

用户反馈：上传交易表时，点击九月显示八月，点击十月显示九月。用户提供的18080入口已确认指向正式站。

本次服务器Chromium的前测，在“已有表生成月报”和“新店铺上传交易表”两条路径中，实际点击09/10/01/12均得到同月。**原始偏移未稳定复现，不能宣称已证明是零基月份或时区错误。** 前测证据保留在 `evidence/probe.json`、`evidence/upload_baseline.json`。

本次作最小兼容性处理：将本处Ant Design DatePicker月份控件改为受控的month输入，直接使用输入控件给出的YYYY-MM字符串。移除该文件中不再使用的dayjs导入。没有对月份加一或减一，没有改动字段映射、来源月份校验、完整范围日期控件、后台请求结构、算法或历史报告。

原生月份控件的显示格式由浏览器语言决定，底层值与请求仍为YYYY-MM；本次服务器Chromium截图显示英文月份，不代表网站将日期或计算语言改为英文。Windows原生选择面板的同机人工复测尚未执行，不能把服务器Chromium检查冒充Windows同机复现。

## 备份与变更识别

- `backup/frontend_before.tgz`：正式前端源码、依赖清单和原静态产物。
- 前端归档SHA256：`1a16e538bd3c12f763d77c1b04d0815d031da5bb8049cf3713e4acc34687d0e5`。
- `backup/database_before.sqlite3`：SQLite在线备份API形成的一致性备份，quick_check=ok；不是热库单文件拷贝。备份包含账号数据，**不得上传仓库或下载传播**。
- `evidence/before.json`：时间、schema、源码/静态哈希和33条原运行摘要。
- 修改后源文件SHA256：`e7c1b42dc89e545794a7a070b7e9b8b1c6df51c273a4b076d4741869c6fbe234`。
- 正式index.html SHA256：`58c0f9b90a22e632e712b3e45561fbf699590d9f10688012c1109bbe8be7e14a`。
- 修改补丁：`evidence/month-picker.patch`。
- `evidence/publication.json`：发布策略与实际产物哈希。

## 本次真实验收

测试日期：2026-10-24。浏览器在服务器运行，桌面1440×1000及窄屏390×844；时区Asia/Shanghai。测试 profile、字体缓存、临时目录和日志均位于本次修复记录目录。使用现有浏览器和字体，没有安装依赖。

独立测试店铺：`c6cfb34e-3ec6-4d66-83a7-75b91e2cde2c`（月份选择回归_20261024_01）。测试文件 `evidence/month_boundary_fixture.csv` 为7行确定性模拟数据，覆盖2025-12、2026-01、08、09、10、12、2027-01；数量等于月份数、单价10、行金额为数量×10。它只用于本次边界测试，不是商户真实数据。

| 验收项 | 状态 | 实际证据 |
|---|---|---|
| 12个月逐一输入、失焦保持 | PASS | acceptance.json前12项 |
| 四个跨年边界操作 | PASS | acceptance.json第13—16项 |
| 清空月份后阻止分析并显示必填提示 | PASS | EMPTY_MONTH_VALIDATION |
| 390px月份控件完整可见、不横向裁剪 | PASS | NARROW_390_MONTH；x=38、宽314 |
| 更改月份保留已填销量单位 | PASS | 每次输入后回读“件” |
| 新上传CSV→九月分析请求→报告回读 | PASS | request/result=2026-09；9件、90 CNY |
| 同一冻结版本生成十月报告 | PASS | request/result=2026-10；10件、100 CNY |
| 页面未捕获脚本错误 | PASS | page_errors=[] |
| TypeScript检查、Vite构建 | PASS | typecheck.log、build.log |
| 正式HTTP实际返回新index构建 | PASS | integrity.json；本机18080/projects HTTP200 |
| 33条旧运行、11版本、11映射、9清洗策略、6条旧销售记录逐字段一致 | PASS | integrity.json |
| SQLite完整性和schema | PASS | quick_check=ok，schema6 |
| 原构建与源码可从归档独立读出并验证哈希 | PASS | integrity.json；tmp/rollback_*_check.* |
| 临时18474预览登录 | BLOCKED | 既有来源校验拒绝，未降低安全校验；随后在正式8000实际完成验证 |
| Windows同机原生月份面板人工复验 | NOT_RUN | 需用户刷新页面后使用自己的浏览器确认 |
| 全站算法/AI/导出完整回归 | NOT_RUN | 单一月份控件修复，不声称重跑全站 |

正式前端浏览器脚本最终20项检查PASS（包含12个月和4个边界操作），没有未解决的本轮功能FAIL。

九月run：`f74d7d88-526f-4f8b-a96c-e6adae6ab93e`。
十月run：`c9ad41be-88e7-4a35-816f-218cf5e501d2`。
共同冻结数据版本：`6f2874d8-9d56-476e-ba3e-4f8d40833e2e`。

测试自动登录、虚拟列表定位、弹层动画同步和测试表初始日期映射的失败尝试均保留为harness-*.json等文件；这些尝试不计入成功验收。窄屏初次测量在抽屉尺寸动画完成前失败，增加等待后实际几何和截图一致，无需修改CSS。已有大chunk构建提示仍存在，不计为构建失败，也不在本次扩展重构。

## 实际执行方式

正式前端使用现有Node与node_modules，无npm install：

```bash
source /home/ubuntu/AIC_Shared/aic-env.sh
export TMPDIR=/home/ubuntu/Project_Progress/10_24月份选择修复_20261024_01/tmp
export XDG_CACHE_HOME=/home/ubuntu/Project_Progress/10_24月份选择修复_20261024_01/cache
export npm_config_cache=$XDG_CACHE_HOME/npm
cd /home/ubuntu/AIC_Project/frontend
npm run typecheck
npm run build -- --outDir /home/ubuntu/Project_Progress/10_24月份选择修复_20261024_01/candidate_dist
```

上述构建命令已实际执行；**再次构建不会自动发布**，不能据此冒充正式产物已更新。

浏览器脚本位于记录目录 `acceptance.cjs`。本次执行环境还设置现有浏览器sysroot的LD_LIBRARY_PATH、修复目录fonts.conf、TEST_BASE_URL=http://127.0.0.1:8000，再用现有Node执行该脚本。它会在专用测试店铺新建测试版本和报告，**不是只读脚本**，再次执行前应先确认只操作该测试店铺。密码由已有共享账号文件内部读取，未输出或复制其内容。

## 团队Git与回退

正式目录目前没有.git元数据。团队交接记录标注的基线为ab0c647，不能把它当成本次新提交。**本次没有Git commit或push，不声称GitHub已更新。** 已留下单文件补丁和运行记录，由团队在当前已合并分支应用或提交；不要拿旧main覆盖正式目录。

回退预案（未执行正式回退）：先核对本次源文件、index哈希和队友后续改动；从备份恢复该源文件，并将备份中的旧index原子替换回正式index。原静态哈希资源均保留且已校验，可恢复原前端而不恢复数据库。归档中这两个文件已经在tmp独立读出并核对哈希。若队友已修改同一文件，先比较差异，不能盲目覆盖。

## 安全与后续

本次主动本地文件写入仅D/E盘；SSH保持D盘known_hosts及StrictHostKeyChecking=yes，未改C盘认证或配置。不能保证Windows/Codex自身后台绝对零写入。没有schema升级、服务重启、端口开放或真实商户数据改写。专用测试店铺及其草稿/报告保留供团队复核，未自动删除任何共享数据。

用户下一步：在原页面按Ctrl+F5刷新，重新打开上传窗口，核对九月、十月选择。若同机仍有偏移，请保存实际月份面板截图与浏览器版本，不能仅凭本次远端测试声称所有浏览器均不可能出现问题。
