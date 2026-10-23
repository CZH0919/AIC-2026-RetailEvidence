# 团队技术交接

2026-10-10 更新：0.6.1 F01/F02 反馈修复与本轮真实验证见 [FEEDBACK_20261010](FEEDBACK_20261010.md)。个人当前隔离库位于 updates/review_20261010_01/state，源码为该目录 source；下方 2026-10-09 路径/run 为历史。正式目录未部署。本轮 candidate SHA d8f19452b5c89989f306f239ea20bb4d08ad629c，实际发布/最终运行收据另存个人工作区 evidence/feedback_20261010/release.json。

先读TASK_PROGRESS.md（D盘工作区）和验收报告，再检查对应真实运行证据，不能仅凭进度文字判定PASS。本轮私人主开发目录 /home/ubuntu/retailevidence_personal_20261009_01；source源码、state数据库、storage资产、baseline备份、verification干净检出、evidence证据。正式 /home/ubuntu/AIC_Project 与 Project_Progress 是共享资产，不作为测试目录。

## 环境与服务

Python3.12.3、Node24.21.0、Ubuntu24.04、CPU8/RAM约30GB。干净安装见README；原共享依赖只读复用期间禁止向其symlink安装。全部新依赖、浏览器profile、下载、缓存与日志在个人目录。SQLite首次工厂启动初始化schema5，本轮分类沿用既有参数JSON，无schema升级。

个人Web tmux `re-personal-web`，127.0.0.1:18081；AI tmux `re-personal-ai`，127.0.0.1:18082。默认项目运行脚本仍为8000，个人进程设置AIC_PORT或使用显式uvicorn命令。不得停队友aic-app/aic-ai，不覆盖正式static/db。停止个人Web前查看队列，确认没有自己需要保留的计算；使用 `tmux send-keys -t re-personal-web C-c`（本轮已实际执行），停止只会中断自身任务，数据仍保留。

```bash
# 先在个人源码目录设置AIC_STATE_DIR、AIC_STORAGE_DIR、AIC_STATIC_DIR等
export AIC_PORT=18081
export AIC_SOURCE_COMMIT="$(git rev-parse HEAD)"
export AIC_AI_URL=http://127.0.0.1:18082/v1/chat/completions
bash scripts/run.sh
# 模型：使用已经获取并核验的二进制及模型路径，均须显式指定
llama-server -m "$MODEL_FILE" --host 127.0.0.1 --port 18082 -t 4 -c 2048 -np 1 -ngl 0
```

本轮实际二进制版本b11429/d81235049；模型文件SHA见THIRD_PARTY。通用命令中的MODEL_FILE和PATH须由接手者指定；机器实际命令与环境记录在个人evidence/service_commands_release.json（最终发布后实际记录）；较早候选服务见对应candidate文件。不需要远端Codex CLI或GitHub凭据。

Windows使用现有SSH私钥正常认证，不读取或复制其内容。显式 `UserKnownHostsFile` 指向D盘已有记录，`StrictHostKeyChecking=yes`、`UpdateHostKeys=no`；首次变化立即停止。C盘SSH/Git配置、认证、环境变量和日常浏览器均未修改。D盘Invoke-InWorkspace.ps1仅进程级重定向临时/cache/pycache/npm/Playwright/Git配置；禁止全局安装、系统清理和默认C盘浏览器profile。私有仓库Deploy Key只有D盘限制ACL；Git配置仅仓库级或GIT_SSH_COMMAND，GitHub官方指纹固定。

个人演示隧道为本机127.0.0.1:18080→远端127.0.0.1:18081（正式共享8000没有被本轮占用）。手动建立时使用同样的密钥、D盘信任和 `ssh -N -L 127.0.0.1:18080:127.0.0.1:18081 ...`；这些占位SSH参数须沿用已有配置，不自动创建新信任，不打开云端端口。它不是公网评委入口。

## 备份、恢复与协作

本轮当前源快照、在线SQLite备份和独立恢复验证详见BASELINE_AUDIT。备份恢复须保留对应datasets/projects及历史runs相对结构、schema和manifest哈希；真实数据访问遵守团队权限。

新备份使用显式路径，不再自动拷贝共享规划文件：`python3 -B scripts/backup_sales_release.py --database "$AIC_STATE_DIR/retailevidence.sqlite3" --destination "$BACKUP_PARENT/new_snapshot"`。目标父目录须存在，目标备份目录必须未存在；在线只读来源、完整性/FK校验、SHA和manifest；不能把外部资产省略。该命令须在指定隔离库复验，正式执行需先审查授权。

只在新的隔离目录恢复。停止该隔离实例，核对备份SHA，SQLite backup API恢复到新的DB（目标不得存在），检查integrity_check/FK/schema/关键行数，再用新的STATE/STORAGE路径启动。不要以cp热库.db替代一致性备份。正式恢复/迁移/覆盖部署需具体diff、备份、回退及用户批准；本轮没有批准或执行。

源码回退：新隔离目录检出基线a4dd458，不重写个人提交或强推，不自动降级正式数据库。0.6新参数对旧代码可能不可识别，回退须使用对应旧运行，不能拿旧算法读取新分类后声称同口径。

常见错误：
- ensurepip缺失：使用已有uv创建个人.venv，无须sudo安装系统包。
- npm配置double-loading：userconfig与globalconfig必须是不同个人空文件。
- AI不可用/超时：保持月报可查，问答明确回退，核对18082健康和单并发，不伪装模型成功。
- 数据未确认/混合币种/单位/重复版本/重叠日期：回到字段和分类确认，依业务口径生成新配置，不编辑旧报告。
- Chromium动态库缺失：本轮将Ubuntu依赖包解包到个人browser-runtime/sysroot并设置LD_LIBRARY_PATH，中文字体用个人FONTCONFIG_FILE；不sudo修改共享系统。该浏览器初始化不能默认为任意机器已具备。
- SQLite忙/备注409：保持expected_revision检查，刷新读取后再决定，不覆盖他人备注。

正式整合前重新检查队友文件哈希和修改时间；正式无.git，使用清单核对，不能只读取自己的Git状态。旧公开仓库只为历史来源，upstream保留。新origin必须LSTongXXN/RetailEvidence-Studio，初始Private；任何公开、强推、危险schema迁移或正式部署均需单独批准。

最终发布候选的源码/文档一致性以GitHub main为准；服务器个人发布检出计划位置 /home/ubuntu/retailevidence_personal_20261009_01/release/source，自己的state/storage继续沿用，不部署共享AIC_Project。最终实际启动命令/端口/环境见个人evidence/service_commands_release.json；若该文件尚未生成，发布运行尚未完成。字段助手只解释列名建议，原始样例不送模型，应用后confirmed仍false；保存版本必须现有确认流程，无schema迁移。
