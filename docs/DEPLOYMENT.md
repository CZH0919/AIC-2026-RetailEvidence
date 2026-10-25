# 安装与部署

本指南面向首次部署和日常维护。示例使用 Linux 的 Bash；目录均属于部署者自己，已有业务实例应先完成备份和维护安排，不应重新初始化其数据。

## 1. 环境与资源

| 项目 | 要求或已验证配置 |
| --- | --- |
| 操作系统 | 已验证 Ubuntu 24.04；原生 Windows 后端运行未列为已验证方式 |
| Python | 3.12，具备 `venv` 和 pip；依赖固定在 `requirements.txt` 及其引用文件 |
| 前端构建 | Node.js 24、npm；使用锁文件执行 `npm ci` |
| Web | 单 Uvicorn worker，默认回环端口 8000 |
| AI（可选） | llama.cpp CPU server、Qwen2.5-1.5B-Instruct Q4_K_M GGUF；两线程、单推理槽、4096 上下文 |
| 磁盘 | 重任务执行检查至少 20 GiB 剩余空间；还需容纳依赖、模型、数据与备份 |
| 内存与并发 | 任务子进程有 8 GiB 地址空间硬限制及 RSS 监控；这不是物理内存最低要求或无限并发承诺，应按数据规模评估整机余量 |

基础 Web 不要求 GPU，也不要求先启动语言模型。停止模型不影响确定性的文件读取和销售统计。

**验证范围：** 既有依赖环境中的构建、日期逻辑和隔离账号接口已执行；下面的新机器联网安装、模型下载/编译及备份恢复示例尚未在全新机器整体复跑，部署后需按第 7 节验证。无需升级已能运行的团队环境来执行本指南。

## 2. 获取代码与准备独立目录

仓库访问取决于实际权限；需要访问授权时，先由仓库维护者授予权限，不在命令或文档中写入 Token。

```bash
git clone git@github.com:LSTongXXN/RetailEvidence-Studio.git
cd RetailEvidence-Studio
git switch main
git rev-parse HEAD

# 运行数据放在代码目录之外；以下变量只作用于当前 shell 及子进程
export RUN_ROOT="$PWD/../retailevidence-runtime"
mkdir -p "$RUN_ROOT"/{state,storage,public,tmp,cache,logs}
export TMPDIR="$RUN_ROOT/tmp"
export XDG_CACHE_HOME="$RUN_ROOT/cache"
export PIP_CACHE_DIR="$RUN_ROOT/cache/pip"
export UV_CACHE_DIR="$RUN_ROOT/cache/uv"
export npm_config_cache="$RUN_ROOT/cache/npm"
export PYTHONDONTWRITEBYTECODE=1
```

Windows 管理端可在非系统盘保存检出和资料，通过已安装 SSH 连接 Linux。上述 Bash 不是 PowerShell 命令；不要将 Linux 部署步骤直接粘贴到 Windows 终端。

## 3. 安装应用依赖与构建

Python、Node.js 和所需系统运行库应由部署者提前准备。本指南不自动修改系统软件、网络配置或全局包目录。

```bash
python3.12 --version
node --version
npm --version

python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
(cd frontend && npm ci && npm run build)
```

`requirements.txt` 已包含 `requirements-mining.txt` 的数值计算依赖。不要把项目依赖安装到系统 Python 或使用 `pip install --user` 替代虚拟环境。构建结果位于 `frontend/dist`，无需另外启动前端开发服务器。

## 4. 配置、启动与停止 Web

在项目根目录、保留 `RUN_ROOT` 的同一终端执行：

```bash
export AIC_PY="$PWD/.venv/bin/python"
export AIC_STATE_DIR="$RUN_ROOT/state"
export AIC_STORAGE_DIR="$RUN_ROOT/storage"
export AIC_PUBLIC_DATA_DIR="$RUN_ROOT/public"
export AIC_STATIC_DIR="$PWD/frontend/dist"
export AIC_PORT=8000
export AIC_AI_URL=http://127.0.0.1:8081/v1/chat/completions
export AIC_COOKIE_SECURE=0

bash scripts/run.sh
```

保持进程运行，访问 `http://127.0.0.1:8000`。前台启动的实例用 `Ctrl+C` 停止。退出终端后不会自动保证服务持续运行；如使用 tmux 或服务管理器，应由部署者保存同一组环境变量、日志位置和进程归属。不要终止其他实例或分析任务。

首次启动创建 SQLite 表；当前 schema 为 6。已有数据库使用增量初始化和兼容性检查，升级前必须备份，不通过删除数据库解决启动问题。

### 配置项

| 环境变量 | 未设置时的默认值 |
| --- | --- |
| `AIC_PY` | `.venv/bin/python` |
| `AIC_PORT` | `8000` |
| `AIC_STATE_DIR` | `storage/state` |
| `AIC_STORAGE_DIR` | `storage` |
| `AIC_PUBLIC_DATA_DIR` | `storage/datasets/public` |
| `AIC_STATIC_DIR` | `frontend/dist` |
| `AIC_AI_URL` | `http://127.0.0.1:8081/v1/chat/completions` |
| `AIC_COOKIE_SECURE` | `0`；HTTPS 访问时配置为 `1` |

启动脚本不自动读取 `.env`。业务相对路径从项目根目录解析。独立测试实例必须同时隔离状态、资产和端口；只改端口仍会共享数据。不要增加 Uvicorn workers 绕过单消费者和重任务锁。

前端开发可执行 `npm run dev`，默认 `127.0.0.1:5173`，API 代理到 `127.0.0.1:8000`。生产使用构建后的同源页面。

## 5. 远程访问

在自己的电脑建立已核验主机身份的 SSH 隧道。`SERVER_ALIAS` 需替换为自己的可信连接别名；显式密钥或主机信任路径按已有配置传入，不关闭主机校验。

```bash
ssh -N -o StrictHostKeyChecking=yes -L 18080:127.0.0.1:8000 SERVER_ALIAS
```

在同一台电脑打开 `http://127.0.0.1:18080`。隧道关闭或网络中断后需要重新连接；本机 18080 已占用时选择另一空闲端口。

这不是外部用户可直接访问的链接。公网访问需另行配置 HTTPS、反向代理、访问控制和维护策略。保持 Web 和模型服务的回环监听，不为演示直接暴露模型端口。

## 6. 启用 CPU AI（可选）

1. 从 [llama.cpp 官方发布](https://github.com/ggml-org/llama.cpp/releases) 获取适用于主机的 CPU `llama-server`，或按 [官方构建说明](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md) 编译。现有启动脚本引用 `b11429`；部署时记录实际二进制版本，不因文档示例自动升级既有环境。
2. 从 [Qwen 官方 GGUF 模型库](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) 选择 Q4_K_M 权重，保存到自己的模型目录。记录下载版本、来源、文件名和 SHA-256，并核对模型页的使用条款。
3. 仓库不包含模型权重。不要用不同模型的文件名冒充相同版本；若没有可核对的历史哈希，新的下载需要重新做模型问答验证。

模型路径示例均需替换为实际值：

```bash
LLAMA_BIN=/absolute/path/to/llama-server
MODEL_GGUF=/absolute/path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf
"$LLAMA_BIN" --version
sha256sum "$MODEL_GGUF"
"$LLAMA_BIN" -m "$MODEL_GGUF" \
  -ngl 0 -t 2 -tb 2 -np 1 -c 4096 \
  --host 127.0.0.1 --port 8081 --alias aic-assistant
```

`scripts/run_ai.sh` 依赖既有共享环境文件和机器路径，新部署请使用上面的显式方式。模型与 Web 端口不同，启动前检查占用情况。模型前台进程用 `Ctrl+C` 停止。

服务正常启动后，在已生成的月报中提问，并确认页面报告为真实模型解释；HTTP 服务可连接不等于业务问答已经验证。模型不可用、超时或结果校验失败时，系统保留确定性事实回退，不能将回退记作模型成功。

## 7. 首次部署检查

Web 运行后，在另一个终端执行只读健康检查：

```bash
curl --fail --max-time 5 http://127.0.0.1:8000/api/health
# 仅在启动模型后检查
curl --fail --max-time 5 http://127.0.0.1:8081/health
```

随后在浏览器验证：注册/登录 → 新建测试店铺 → 上传无敏感信息的测试表 → 预览和确认字段 → 检查月份与范围 → 生成月报 → 回读商品和原始记录 → 保存备注 → 导出并打开文件。另用一个账号确认不能查看前一账号的店铺。

新环境的浏览器流程、PDF 分页与真实 AI 问答需分别记录，不由构建成功或健康检查代替。更多验证说明见 [VALIDATION.md](VALIDATION.md)。

## 8. 可选公开数据

先确认下载目录有足够空间和所需访问权限。脚本只准备数据，不会代替网页中的字段与业务确认。

```bash
.venv/bin/python -m pip install -r requirements-data.txt
.venv/bin/python -B scripts/prepare_public_data.py --output "$AIC_PUBLIC_DATA_DIR"
.venv/bin/python -B scripts/profile_public_data.py --root "$AIC_PUBLIC_DATA_DIR"
```

来源、数据限制与许可记录见 [public-data.md](public-data.md)。Groceries 没有真实时间、客户或金额，适用于共购，不应伪造字段生成经营月报。

## 9. 账号与数据维护

用户名为 3–32 位字母、数字、下划线或短横线，首位为字母或数字；密码为 12–128 位。账号由使用者自行注册，不提供共享默认密码。网页支持修改密码，未提供邮件找回流程。

历史未归属项目不会自动分配给首个注册用户。维护者确认接收账号和项目后，可用以下只检查命令；将占位符替换为实际账号与项目 UUID：

```bash
PYTHONPATH=backend "$AIC_PY" -B -m app.account_admin \
  --database "$AIC_STATE_DIR/retailevidence.sqlite3" \
  --username ACCOUNT_NAME --assign-project PROJECT_UUID
```

检查正确且获所有者确认后，才在同一命令末尾添加 `--apply`。工具写入前建立在线数据库备份；不支持通过此方式转移已有归属的项目。密码恢复使用同一工具的 `--reset-password --apply`，新密码通过终端隐藏输入，不写入命令行。

## 10. 备份、升级与恢复

1. 记录代码 SHA、依赖、模型版本和实际配置路径；检查正在执行的任务及备份空间。
2. 采用维护窗口暂停写入，在业务空闲时停止自己管理的 Web 实例。不要在文件仍变化时声称数据库和资产已形成一致快照。
3. 使用 SQLite backup API 生成数据库快照并执行 `PRAGMA quick_check`；同时保存对应 `AIC_STORAGE_DIR` 的上传、映射和运行资产，以及使用的公开数据来源清单。数据库备份不能代替资产备份。
4. 在新的独立状态/资产目录恢复，核对表版本、关键项目和运行文件引用，再启动相容代码验证。不要覆盖原环境来试验恢复。
5. 验证完成后再安排正式切换，保留原代码和完整数据备份。schema 6 数据库不能直接交给不相容的旧程序。

仓库中的 `backup_sales_release.py` 带有既有部署假设，使用前须审查源路径与副作用；不要直接复制活动数据库主文件代替在线备份。以上是维护流程，未声明在每个新环境完成了恢复演练。

## 11. 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| 浏览器拒绝连接 | 分别检查服务器、Web 进程、端口和本机 SSH 隧道；不要通过开放公网端口排错 |
| 登录后没有旧店铺 | 确认账号与项目归属；历史未归属项目由维护者明确分配，不复制数据库绕过权限 |
| 有页面但 API 失败 | 使用同源正式入口；核对代理目标、Cookie 与 HTTPS 配置，保留具体错误码 |
| 导入失败或长时间排队 | 查看格式提示、任务状态与磁盘余量；重任务串行，不要反复上传制造重复任务 |
| 月份不在范围内 | 检查实际日期解析、已选数据版本、月汇总所属月份及完整范围，不随意扩大范围 |
| 无预测或备货入口 | 查看数据粒度、覆盖完整性、历史长度和误差原因；不能通过填写虚假库存绕过门槛 |
| 助手返回核实事实 | 检查模型进程与地址、响应时间和校验状态；回退不影响原月报 |
| 测试出现 `KeyError: 'id'` | 当前部分旧 API 测试缺少合法登录准备；不要关闭鉴权，参见验证文档 |

维护日志不应记录密码、会话或商户敏感明细。公网入口、监控与自动启动属于部署者的运行配置，不由仓库同步自动完成。
