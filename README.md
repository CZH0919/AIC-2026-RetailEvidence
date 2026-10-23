# RetailEvidence Studio

## 当前系统复查与界面细化（0.7.1）

注册登录后进入自己的项目空间。新版本修复搜索、历史报告导航、慢请求结果串入其他上下文、小数包装取整及临时断连丢草稿；统一导航、数字、表格和表单，详细帮助按需展开。没有改变销售算法、历史报告或数据库结构。

[复查与修复说明](docs/SYSTEM_REVIEW_20261023.md) · [实际验收](docs/SYSTEM_REVIEW_ACCEPTANCE.md) · [同数据前后截图](docs/SYSTEM_REVIEW_BEFORE_AFTER.md)。下面按日期列出的旧任务证据是历史记录，不能替代本轮结果。

小商户月度销售与备货助手，沿用团队 FastAPI、SQLite/SQLAlchemy、React/TypeScript 架构。当前版本 0.7.1，schema 6，销售算法 sales-v2.2.0；文案审计与本轮验收见 [文案验收](docs/USER_FACING_COPY_ACCEPTANCE.md)；此前操作提示验收见 [真实UX报告](docs/UX_GUIDANCE_ACCEPTANCE.md)；原系统验收见 [历史交付报告](docs/ACCEPTANCE_REPORT.md)。

上传收银明细、独立商品日汇总或月汇总 → 确认字段、月份、记录类型与金额口径 → 检查数据 → 生成月报 → 查看全部商品及异常原始记录 → 保存核对备注 → AI 辅助解释证据 → 导出 HTML/CSV/JSON、浏览器打印 PDF。RF/RFM 客户分群与 FP-growth 共购保留在“更多分析”。

分类支持实物、运费/服务、人工调整、其他、待确认。规则按数据版本与字段版本冻结，来源行规则优先，其次商品编号、已映射分类、默认口径；类型与金额是否计入分别确认。待确认项能核对明细，关键类型未知时暂停不可靠预测与建议。不会按名称包含 POST 等字符串全局删行。旧报告保留原口径，修改分类产生新运行。

预览阶段可请本地CPU AI解释字段，列名建议由程序提出；点击应用后仍需人工确认类型、金额等业务口径。字段解释不保存数据版本、不自动确认。

AI 只解释冻结证据，数字由程序填写。没有库存不能算进货量，没有成本不算利润；七天销量参考不等于整月采购量。公开批发数据验收不代表小店真实经营收益。

## 商业化 UI（2026-10-19）

用户已确认样板及说明收纳方向；现已统一项目库、导入/映射、月报、商品抽屉、质量与RF/RFM/共购。减少常驻小字，原帮助、风险与全部操作保留；计算、历史报告及导出内容不改，应用仍0.6.3。50组浏览器、17项展示合同、76pytest+6subtests及17项结果/请求对账通过，最终main干净检出收据独立保存。

[基线](docs/UI_REDESIGN_BASELINE.md) · [官方参考及方向](docs/UI_REDESIGN_DIRECTION.md) · [实际验收与未覆盖项](docs/UI_REDESIGN_ACCEPTANCE.md) · [真实前后截图及独立预览](docs/UI_REDESIGN_BEFORE_AFTER.md)。现有演示和共享正式服务未替换。

## 站内操作提示与使用说明

按上下文点击“怎么填写？”或“如何理解？”展开例子、未知数据处理和错误影响。42个统一主题覆盖上传、金额、记录分类、完整范围、月报、异常、预测、历史库存、AI、RF/RFM和共购。帮助支持点击、Enter/空格/Tab/Escape与焦点返回，不提交表单或调用模型。桌面、768px及390px真实浏览器复测。

- [网站使用说明](docs/WEBSITE_USER_GUIDE.md)
- [初次完整审查（独立提交）](docs/UX_GUIDANCE_AUDIT.md)
- [实现对应](docs/UX_GUIDANCE_IMPLEMENTATION.md)
- [真实复测与限制](docs/UX_GUIDANCE_ACCEPTANCE.md)
- [改造前后真实截图](docs/UX_GUIDANCE_BEFORE_AFTER.md)

2026-10-11操作提示任务37个主浏览器组PASS，帮助3条内容合同测试、pytest60执行案例加6subtests、Ruff与类型/构建PASS；完整长时任务超限和真人商户研究尚未执行。原有验收记录按原日期/版本保留，不能当本轮重跑。当前依赖复用已安装环境，下面依赖安装步骤属于既有启动说明，本轮没有重新网络安装。

## 运行（Ubuntu，Python 3.12、Node 24）

以下流程在独立环境实测；需要已安装 uv（不在本任务中全局安装）。先进入自己的源码目录，将所有状态、缓存与临时文件放在该目录或独立运行目录。

```bash
export TMPDIR="$PWD/.runtime/tmp"
export XDG_CACHE_HOME="$PWD/.runtime/cache"
export UV_CACHE_DIR="$PWD/.runtime/cache/uv"
export npm_config_cache="$PWD/.runtime/cache/npm"
export PYTHONDONTWRITEBYTECODE=1
export MPLCONFIGDIR="$PWD/.runtime/cache/matplotlib"
mkdir -p "$TMPDIR" "$UV_CACHE_DIR" "$npm_config_cache" "$MPLCONFIGDIR"
uv venv --python /usr/bin/python3 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
cd frontend
npm ci --no-audit --no-fund --ignore-scripts
npm run build -- --configLoader runner
cd ..
export AIC_STATE_DIR="$PWD/.runtime/state"
export AIC_STORAGE_DIR="$PWD/.runtime/storage"
export AIC_STATIC_DIR="$PWD/frontend/dist"
export AIC_PUBLIC_DATA_DIR="$PWD/.runtime/public"
export AIC_SOURCE_COMMIT="$(git rev-parse HEAD)"
export AIC_AI_URL=http://127.0.0.1:8081/v1/chat/completions
bash scripts/run.sh
```

默认 Web `http://127.0.0.1:8000`，单 Worker；首次在自己的状态目录初始化 schema 6。环境通过进程变量提供，脚本不会自动加载 `.env`；安全样例见 [.env.example](.env.example)。`.runtime/` 不提交 Git。Ubuntu 未安装 ensurepip 时可使用已有 uv，无须 sudo。Windows 操作需遵守 [C 盘保护与交接](docs/HANDOFF.md)，本任务主要测试在远端完成。

模型使用 [官方 Qwen2.5-1.5B GGUF](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) 和 llama.cpp CPU 服务，详细配置、SHA-256、线程与端口见 [技术交接](docs/HANDOFF.md)。模型不可用仍可使用确定性报告，界面明确标记预设说明。没有模型权重、原始大数据、个人凭据或数据库随 Git 发布。

## 测试与证据

2026-10-10 反馈补丁已完成费用/旧未分类报告备货保护及历史 run 地址同步。49 唯一单测、20 HTTP 和 4 套真实浏览器专项已重跑通过，来源与实际 SHA 见 [本轮反馈验收](docs/FEEDBACK_20261010.md)。刷新、复制链接和浏览器返回保持所选报告；旧报告统计不重写。下文 2026-10-09 证据保留为历史。

```bash
export PYTHONPATH="$PWD/backend"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
.venv/bin/python -B -m pytest -p no:cacheprovider scripts/test_record_classification.py scripts/test_task_safety.py scripts/test_ai_contract.py scripts/test_field_assistant.py -q
.venv/bin/ruff check --no-cache backend scripts/test_record_classification.py scripts/test_task_safety.py scripts/test_ai_contract.py scripts/test_field_assistant.py scripts/accept_classified_public.py
```

47 个唯一测试在隔离Git检出通过（另6个子测试不重复计数），7项在线备份机制、20项HTTP回归也有独立执行记录。最新候选bb8b645d19abd6422f47f6682a21a9f55b3124a6已通过真实字段CPU AI、完整上传/类型确认/月报/备注/AI/全部导出/中文PDF、桌面390px和取消状态验收。最终远端main的fetch/SHA与复验收据记录在个人工作区evidence/release_verification.json；Git中的候选证据不冒充最终远端复验。详见 [报告](docs/ACCEPTANCE_REPORT.md)、[矩阵](docs/FEATURE_ACCEPTANCE_MATRIX.md) 和 [机器矩阵](docs/acceptance_matrix.csv)。

预测实测选择四周平均：独立测试 MAE 63.6291、WAPE 65.3999%；复杂模型未超过简单基线。测试商品 1000/eligible 1321，发布382；异常2106/93341，只是无标签报警，没有检测准确率。

## 目录与贡献

`backend/app/`：输入、质量、持久任务、销售与旧算法；`frontend/src/`：现有页面及业务分类确认；`scripts/`：启动、测试、独立验收；`docs/`：需求追踪、证据、演示和交接；`examples/`：可公开小样例（不是冻结真实评测集）。

原团队仓库历史及 chang-zihe 的作者署名完整保留；原服务器 0.5.0 增量导入有专门基线提交。LSTongXXN 创建个人私有仓库并承担本轮分类修复与交付整合，不声称团队全部代码个人原创。许可和依赖见 [THIRD_PARTY](docs/THIRD_PARTY.md)；团队自研代码未擅自改为开源许可，公开发布需另行确认。

[演示指南](docs/DEMO_GUIDE.md) · [变更](CHANGELOG.md) · [基线](docs/BASELINE_AUDIT.md) · [限制](docs/KNOWN_LIMITATIONS.md)

![真实公开数据月报](docs/verification/monthly_desktop.png)

截图来自bb8b645的真实浏览器月汇总上传流程，待确认/费用展示对应docs/verification/final_candidate/browser_import.json中的run，不是设计Mock。

## 0.6.3 全站文案核查

本轮16区域、35主操作组、42帮助、12固定AI问题和6受控模型故障实际重跑。32项（5P0/19P1/8P2）完成处理，保留业务限制和全部质量详情；76 Python执行案例+6subtests、帮助3内容测试、受影响范围Ruff与构建PASS。全scripts132条继承格式问题单列FAIL，真人与长时预算未验证。见[原始审计](docs/USER_FACING_COPY_AUDIT.md)、[改造及前后对比](docs/USER_FACING_COPY_CHANGES.md)、[本轮验收](docs/USER_FACING_COPY_ACCEPTANCE.md)、[后续规范](docs/USER_FACING_COPY_STYLE_GUIDE.md)。


### 说明按需展开

月报通用说明收进现有帮助，分类金额、关注原因与行动依据按需展开；动态风险、人工确认与原始证据保留。用户已批准并推广全站，应用版本0.6.3不变。详见[本轮修订及验收](docs/UI_REDESIGN_COPY_REFINEMENT.md)。

## 账号与独立数据空间（0.7.0）

打开网站先登录，首次使用可自行注册。各账号只访问自己的项目、任务和导出文件，支持修改密码与退出。用户名3–32位、密码12–128位；目前没有邮箱找回。旧项目不会自动交给新注册用户。

详见 [账号与迁移说明](docs/AUTHENTICATION.md) 和 [本轮验收](docs/AUTH_ACCEPTANCE.md)。原有演示库不得未经批准直接升级。首次启动空库会创建schema 6。
