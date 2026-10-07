# 数证智析 · RetailEvidence Studio

将交易数据组织成独立项目，让每一次分析都有清晰的依据。

提供项目管理、CSV / XLSX 导入、公开数据选择、数据预览、字段草稿、业务口径确认，以及独立数据版本和映射历史。原始文件与每次确认的设置都可追溯。导入与映射不依赖 AI。

## 运行

需要 Python 3.12、Node.js 24，以及项目依赖。已有环境可以直接复用。

前端锁文件使用通用 npm 官方下载地址，并保留固定版本与完整性摘要，不依赖某个云平台的内部镜像。

```bash
# 项目根目录，首次准备 Python 依赖时执行
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# 构建前端
cd frontend
npm ci
npm run build
cd ..

# 启动同源页面与 API
bash scripts/run.sh
```

默认访问 `http://127.0.0.1:8000`。该入口用于可信环境，当前没有账号认证，不直接作为公共互联网服务。应用仅绑定回环地址；模型服务不参与项目管理功能。

`scripts/run.sh` 优先使用 `AIC_PY`，未设置时使用项目 `.venv/bin/python`。`AIC_STATE_DIR` 指定 SQLite 状态目录，默认 `storage/state`；`AIC_STORAGE_DIR` 指定上传和版本资产根目录，默认 `storage`；`AIC_PUBLIC_DATA_DIR` 指定公开数据目录，默认 `storage/datasets/public`；`AIC_PORT` 默认 8000。相对路径均以项目根目录解析。不同实例应同时隔离状态、资产目录及端口。脚本读取进程环境，不自动加载 `.env` 文件。

开发时可单独运行 `frontend` 的 `npm run dev`，通过同源 `/api` 代理连接后端。正式访问使用前端构建产物，不需要保持 Vite 运行。

## 准备公开数据

```bash
# 在计划保存公开数据的部署机器上执行；安装仅影响项目虚拟环境
uv pip install --python .venv/bin/python -r requirements-data.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/prepare_public_data.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/profile_public_data.py
```

数据来自 UCI 与固定版本的 arules。脚本保留来源文件、摘要、许可记录和真实统计；Groceries 从原始稀疏购物篮对象转换，不补造业务字段。详细信息见 [数据来源与复现](docs/public-data.md)。原始数据和转换文件不随源码发布。

## 使用

1. 创建项目，进入“数据与版本”。选择本地文件或已准备的公开数据。
2. CSV 选择编码和分隔符；XLSX 明确选择工作表，只有相同表头才能合并。每行购物篮列表需明确列表列和商品分隔符。
3. 检查预览与缺失计数，调整字段，确认订单边界、金额口径、币种、单位、时间及退货含义。可以保存草稿稍后继续。
4. 确认后创建数据版本。再次上传生成新版本；调整已有字段产生新映射，旧记录保持完整。

单文件最多 100 MiB、150 万展开行、200 列，XLSX 解压上限 1 GiB。解析子进程限两核、两线程、10 分钟，Linux 使用 8 GiB 虚拟地址空间硬上限；同一资产目录的重任务互斥。剩余磁盘低于 20 GiB 时拒绝新增处理。未知或有问题的数据保留原值，数据质量判断与分析能力另行处理；金额候选不等于可直接发布的分析结果。

## 验证与文档

```bash
.venv/bin/python -B -m ruff check --no-cache backend scripts
cd frontend
npm run build
```

- [API 与模块边界](docs/api-contract.md)
- [界面设计规范](docs/design-system.md)
- [统一输入、金额与版本合同](docs/data-contract.md)
- [数据来源与复现](docs/public-data.md)

项目数据、模型、环境、构建产物和依赖目录不进入源码备份。开发测试脚本、测试数据库、缓存与中间产物放在正式项目之外的独立开发目录，不污染运行目录。测试时将项目的 `backend` 加入 `PYTHONPATH`，并通过应用工厂参数把状态与资产配置到外部目录；使用 `PYTHONDONTWRITEBYTECODE=1` 和 pytest 的 `-p no:cacheprovider`。具体验收资料独立维护。

文件路径从源码所在的项目根目录推导，部署差异使用环境变量，不写入某台服务器的绝对路径。数据库 v1 → v2 为新增表迁移，不清空项目。升级前用 SQLite backup API 建立一致性快照；备份与恢复需要同时保留版本资产及其相对结构，不能仅复制正在运行的 SQLite 主文件。
