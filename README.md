# 数证智析 · RetailEvidence Studio

将交易数据组织成独立项目，让每一次分析都有清晰的依据。

当前提供项目创建、搜索、查看、切换与编辑，项目资料保存在 SQLite 中。页面包含项目库、项目概览、数据准备入口和使用指南。文件要求页用于准备交易数据；文件上传、数据版本、挖掘与 AI 能力按后续功能计划接入。

## 运行

需要 Python 3.12、Node.js 24，以及项目依赖。已有环境可以直接复用。

```bash
# 项目根目录，首次准备 Python 依赖时执行
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-s01.txt

# 构建前端
cd frontend
npm ci
npm run build
cd ..

# 启动同源页面与 API
bash scripts/run.sh
```

默认访问 `http://127.0.0.1:8000`。该入口用于可信环境，当前没有账号认证，不直接作为公共互联网服务。应用仅绑定回环地址；模型服务不参与项目管理功能。

`scripts/run.sh` 优先使用 `AIC_PY`，未设置时使用项目 `.venv/bin/python`。`AIC_STATE_DIR` 可指定独立状态目录，默认 `storage/state`；`AIC_PORT` 可指定端口，默认 8000。不同实例须使用明确的数据目录和端口。

开发时可单独运行 `frontend` 的 `npm run dev`，通过同源 `/api` 代理连接后端。正式访问使用前端构建产物，不需要保持 Vite 运行。

## 验证与文档

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check backend tests
cd frontend
npm run build
```

- [API 与模块边界](docs/api-contract.md)
- [界面设计规范](docs/design-system.md)

项目数据、模型、环境、构建产物和依赖目录不进入源码备份。测试使用独立临时数据库，不污染用户项目。后续修改数据库结构时需提供显式迁移；当前启动只建立缺少的表，不清空现有记录。
