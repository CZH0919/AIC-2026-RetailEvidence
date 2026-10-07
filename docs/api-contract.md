# 项目工作区 API 与模块边界

## 项目对象

`Project` 包含 `id`（UUID）、`name`（去除首尾空白后 1–64 字符）、`description`（最多 500 字符）、`color`（teal/blue/amber/plum）、UTC `created_at/updated_at` 和整数 `revision`。

同一工作区内名称经 NFKC + casefold 后唯一；仅用于重复判断，显示保留原名。文本始终当作数据，React 自动转义，不渲染用户 HTML。当前没有删除接口。

| 接口 | 行为 |
| --- | --- |
| `GET /api/health` | 轻量进程健康状态 |
| `GET /api/projects?q=&limit=30&offset=0` | 名称/说明搜索，按更新时间降序和 ID 排序；返回 items、total、limit、offset；limit 最大 100 |
| `POST /api/projects` | 接受 name、description、color，成功返回 201 和项目对象 |
| `GET /api/projects/{id}` | 返回指定项目，不存在返回 404 |
| `PATCH /api/projects/{id}` | 接受完整可编辑字段及读取时的 revision；原子校验后更新，revision 加 1；旧 revision 返回 409 |

例如创建：`{"name":"门店季度复盘","description":"观察客户购买行为","color":"teal"}`。更新同一对象时额外携带 `"revision":1`。

错误结构统一为 `{"error":{"code":"...","message":"面向用户的提示","fields":{}}}`。422 表示字段验证失败，409 的 `name_exists` 表示同名，`revision_conflict` 表示有较新编辑，503 的 `storage_unavailable` 表示存储操作失败。内部异常写日志，不回传给页面。跨来源浏览器写入被拒绝；请求不启用宽泛 CORS。

## 持久化

SQLite 存储项目对象，启用 WAL、外键约束及 5 秒 busy timeout，使用短事务。名称唯一性由数据库约束保证；并发更新通过 `WHERE id AND revision` 原子保护。`PRAGMA user_version=1` 标记初始结构，遇到未知版本拒绝启动，不尝试覆盖数据库。

生产默认状态目录为项目内 `storage/state`。测试把数据库放在独立临时目录，验证跨应用重启读取和并发写入；不依赖浏览器缓存保存项目内容。

## 页面与项目上下文

- `/projects`：项目库、搜索、分页、新建。
- `/projects/:projectId`：项目概览、资料编辑。
- `/projects/:projectId/data`：数据准备入口与文件要求；当前不接收文件。
- URL 中的项目 UUID 决定内容。切换时取消旧读取并重新挂载项目视图，避免迟到响应串入其他项目。
- localStorage 仅缓存最多四个最近访问入口；禁用缓存时项目功能仍可用。刷新及直接打开详情链接从 API 恢复真实数据。

## 后续模块接口边界

以下是后续模块的合同，不是已实现的 API：

| 对象 | 必须携带的上下文 | 接入原则 |
| --- | --- | --- |
| DatasetVersion | project_id、data_version_id | 新上传产生独立版本，保留原文件摘要；通过项目内版本接口接入数据页 |
| AnalysisRun | project_id、data_version_id、run_id | 固定映射、清洗及参数版本；状态与产物属于同一运行 |
| Evidence | project_id、data_version_id、run_id、evidence_id | 引用必须属于同一项目及运行，不跨版本拼接 |

建议后续路由归属为 `/api/projects/{id}/datasets`、`/api/projects/{id}/runs` 及运行下的 evidence。服务端必须逐层校验资源归属，不能仅依靠前端传入 ID。当前未实现的 API 返回 404，不伪造空分析结果或成功状态。

组件接入点：`ProjectSpace` 的数据页区域、`ProjectEditor` 的公共表单模式、`States` 的加载/错误/空状态，以及 `api.ts` 的同源客户端。文件预检、解析、版本创建属于数据模块；本阶段不创建空文件版本冒充导入成功。
