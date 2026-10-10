# 数证智析 · RetailEvidence Studio

当前主线：小商户上传营业表，查看本月销售、需要留意的商品和下次进货前要做的事。数据缺失时明确降级，不补造库存或经营原因。

提供项目管理、CSV / XLSX 导入、公开数据选择、数据预览、字段草稿、业务口径确认、独立数据版本、清洗策略和质量检查。系统分别判断客户 RF/RFM 与商品关联分析的输入是否适用，保留逐行排除依据、有效视图与处理历史。导入、映射与质量检查不依赖 AI。

当前版本 0.5.0 在 S01-S03 基础上增加销售月报、完整商品表、七天销量参考、异常核对、本地 CPU AI 和报告导出。原有客户分群和商品共购保留在“更多分析”。AI 不计算销售数值，也不代表已验证经营收益。

接手先读 [代码结构与接手说明](docs/代码结构与接手说明.md)、[当前网页方案](docs/网页最终方案_v2.1.md) 和 [本轮开发规划](docs/开发执行规划_v2.1.md)。本轮 R0-R3 与旧 S01-S09 分开记录，不表示旧 S07-S09 的全部目标已完成。

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

`scripts/run.sh` 优先使用 `AIC_PY`，未设置时使用项目 `.venv/bin/python`。`AIC_STATE_DIR` 指定 SQLite 状态目录，默认 `storage/state`；`AIC_STORAGE_DIR` 指定上传和版本资产根目录，默认 `storage`；`AIC_PUBLIC_DATA_DIR` 指定公开数据目录，默认 `storage/datasets/public`；`AIC_STATIC_DIR` 指定已构建的前端，默认 `frontend/dist`；`AIC_PORT` 默认 8000。相对路径均以项目根目录解析。不同实例应同时隔离状态、资产目录及端口。脚本读取进程环境，不自动加载 `.env` 文件。

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

1. 创建店铺工作区，在月报页上传营业表，或进入“数据记录”选择已准备的公开数据。
2. CSV 选择编码和分隔符；XLSX 明确选择工作表，只有相同表头才能合并。每行购物篮列表需明确列表列和商品分隔符。
3. 检查预览与缺失计数，调整字段，确认订单边界、金额口径、币种、单位、时间及退货含义。可以保存草稿稍后继续。
4. 确认后创建数据版本。再次上传生成新版本；调整已有字段产生新映射，旧记录保持完整。
5. 在月报页选择“生成月报”，确认月份、使用的数据、完整记录范围、重复候选和重叠处理；先检查，再确认生成。未确认完整记录时，空缺日期不按零销量计算。
6. 看本月概况、默认五件重点商品和最多三项行动；商品明细能查看全部结果。详情可核对异常日期原始行及可用的七天销量参考。没有库存不计算进货数量。通过“导出月报”下载 HTML 并打印为 PDF，或下载全部商品表。
7. 旧 RF/RFM、共购和独立质量检查在“更多分析”。这些功能仍按原有数据条件判断，不强迫店主提供客户编号。已有结果保留，取消只作用于所选任务。

单文件最多 100 MiB、150 万展开行、200 列，XLSX 解压上限 1 GiB。重任务单进程串行，子进程限两核、两线程，Linux 使用 8 GiB 虚拟地址空间硬上限。质量任务默认 10 分钟，可显式选择 20 分钟容量预算；另有 RSS 内存监控。剩余磁盘低于 20 GiB 时拒绝新增处理。导入与质量任务共用重任务互斥锁；浏览已有项目与结果不需等待计算完成。

质量检查不覆盖原始数据、不补造客户/金额/日期。行金额与订单总额分开计算，重复总额只按唯一订单计一次；缺损购物篮整篮排除。客户分群和商品共购均从已发布的有效视图读取输入，结果保留参数、分母、候选诊断与运行上下文。各有效视图及限制见 [质量与任务合同](docs/quality-and-runs.md)。

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
- [质量、有效视图与任务合同](docs/quality-and-runs.md)
- [后续分析模块接入](docs/analysis-extension.md)

项目数据、模型、环境、构建产物和依赖目录不进入源码备份。开发测试脚本、测试数据库、缓存与中间产物放在正式项目之外的独立开发目录，不污染运行目录。测试时将项目的 `backend` 加入 `PYTHONPATH`，并通过应用工厂参数把状态与资产配置到外部目录；使用 `PYTHONDONTWRITEBYTECODE=1` 和 pytest 的 `-p no:cacheprovider`。具体验收资料独立维护。

文件路径从源码所在的项目根目录推导，部署差异使用环境变量，不写入某台服务器的绝对路径。数据库 v1/v2 → v3 为新增表迁移，不清空项目。升级前用 SQLite backup API 建立一致性快照；备份与恢复需要同时保留版本资产及其相对结构，不能仅复制正在运行的 SQLite 主文件。
