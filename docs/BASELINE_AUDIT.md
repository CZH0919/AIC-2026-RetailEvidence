# 基线审计

日期 2026-10-09；现场源码 /home/ubuntu/AIC_Project，正式目录无 .git。应用0.5.0/schema5/sales-v2.1.1，89个源码文件；以当前源文件哈希清单锁定，不用旧GitHub覆盖。原仓库HEAD dc9943573fa4e03ff805a35240940f1fe2be9661（0.3.0/S03），基线导入提交 a4dd458c2467dce1ff6a4ebdf9dfaa1153236fae。

当前源码快照 SHA-256 `c46d6a9498e210ce53a247e5ecd0dc87297cd076d74c932279066c2de259ce08`。SQLite在线备份 SHA-256 `e67deee042429012f05a617b1e89c88e2956ab396f2e339d219705207c7332a2`，使用mode=ro来源与backup API，独立恢复 integrity_check=ok、foreign_key_check=0、user_version=5；20analysis_runs/6dataset_versions/6mappings/4projects。不是热库单文件拷贝。

个人主要工作区 /home/ubuntu/retailevidence_personal_20261009_01，source/state/storage/cache/tmp/logs/evidence互相明确。46,761,610字节项目数据复制到个人资产目录；公开原始数据和旧运行以只读引用用于验证；新任务写个人UUID目录。原模型、共享虚拟环境和原 node_modules 只读复用，后续干净验证拥有独立依赖。复制共享虚拟环境没有作为干净安装通过的证据。

CPU8、RAM约30GB、初始磁盘约82GB可用。恢复初始正式8000/8081无监听、无运行服务。个人候选18081/18082监听127.0.0.1，单Worker；未修改共享SSH、代理、网络、正式数据或共享服务。

既有 source_handoff_20261009.tgz、manifest及handoff备份存在，参考使用，不强制恢复。原始UCI文件SHA `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`。历史月汇总比明细多307数量/785.07 GBP：本轮原始XLSX独立计算证明为同单冲突的过滤口径差异，已按相同过滤条件重新派生，并非凭历史截图推断。

原备份脚本硬编码项目父目录及正式storage路径，会自动复制规划文件，本轮基线未直接执行该脚本。正式部署前必须再核对队友新增文件差异、做新的在线备份和源码哈希快照，并取得批准。

本地可信SSH记录固定在D盘；用户明确豁免管理员独立核验，无同IP:22历史可信冲突。GitHub目标LSTongXXN/RetailEvidence-Studio，团队已授权审查后私有托管；专用Deploy Key仅D盘，固定官方GitHub主机公钥。源码、数据库快照与完整安全日志不随Git公开。

可核验外部证据：D盘TASK_PROGRESS.md、evidence/remote-baseline-manifest.json、source-import-verification.json、server-trust-conflict-check.json、logs/isolation-setup.log；远端个人baseline/baseline_manifest.json、source_current_20261009.tgz、database_backup/database.sqlite3、restore_verification.sqlite3。备份恢复需连同对应不可变数据版本资产及旧运行目录，相对引用保持一致；仅有SQLite不足以完整恢复附件。
