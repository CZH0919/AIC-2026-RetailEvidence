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

SQLite 存储项目、导入草稿、数据版本、映射版本、清洗策略、运行及状态事件，启用 WAL、外键约束及 5 秒 busy timeout。v1 是项目初始结构，v2 增加数据/映射，v3 增加策略/运行；均以新增表方式迁移，不删除项目。未知 schema 版本拒绝启动，不尝试覆盖数据库。项目名称与各级版本号有唯一约束。

生产默认状态目录为项目内 `storage/state`。测试把数据库放在独立临时目录，验证跨应用重启读取和并发写入；不依赖浏览器缓存保存项目内容。

## 页面与项目上下文

- `/projects`：项目库、搜索、分页、新建。
- `/projects/:projectId`：项目概览、资料编辑。
- `/projects/:projectId/data`：文件上传、公开数据选择、预览、字段草稿、确认、版本切换和映射历史。
- `/projects/:projectId/quality`：清洗策略、业务范围、质量与能力、有效视图预览、任务取消及历史。
- URL 中的项目 UUID 决定内容。切换时取消旧读取并重新挂载项目视图，避免迟到响应串入其他项目。
- localStorage 仅缓存最多四个最近访问入口；禁用缓存时项目功能仍可用。刷新及直接打开详情链接从 API 恢复真实数据。

## 数据接口

所有资源按 URL 中的项目 UUID 校验归属，跨项目访问返回 404。上传文件名只用于展示，资产路径由服务端 UUID 生成。

| 接口 | 行为 |
| --- | --- |
| `GET /api/public-datasets` | 已准备且具有来源记录的公开数据 |
| `POST /api/projects/{id}/imports?filename=...` | `application/octet-stream` 原始文件体，最大 100 MiB，返回草稿 |
| `POST /api/projects/{id}/imports/public/{source_id}` | 只接受目录中已有的白名单来源；校验源摘要，无任意路径 / URL 下载入口 |
| `GET /api/projects/{id}/imports` | 最近 10 个尚未确认草稿 |
| `POST /api/projects/{id}/imports/{draft}/preview` | ParseOptions：编码、分隔符、工作表、交易 / 购物篮格式；流式解析并生成新的 preview_token |
| `PUT /api/projects/{id}/imports/{draft}/mapping-draft` | preview_token + mapping；保存未完成对应关系，不创建版本 |
| `DELETE /api/projects/{id}/imports/{draft}` | 放弃未确认上传；不能删除已创建的版本 |
| `POST /api/projects/{id}/imports/{draft}/confirm` | preview_token + mapping（confirmed=true）；原子登记独立数据版本与 M1 |
| `GET /api/projects/{id}/versions` | 数据版本列表，按新到旧排列 |
| `GET /api/projects/{id}/versions/{version}` | 原始预览、读取配置、当前映射及语义警告 |
| `GET /api/projects/{id}/versions/{version}/mappings` | 全部映射历史与业务口径 |
| `POST /api/projects/{id}/versions/{version}/mappings` | expected_revision + mapping，新增映射版本，冲突返回 409 |

解析和确认使用最多 600 秒的隔离子进程。相同资产根的并发重处理返回 `409 import_busy`，普通项目读取可继续。`413` 表示文件 / 行列 / 工作簿资源上限，`422` 表示格式或语义错误，`409 preview_conflict` 表示预览被更新，`507 disk_limit` 表示可用磁盘不足。页面保留输入，并给出可重试提示。

相同 preview_token 与相同映射的确认是幂等的；已保存文件带不同映射重试会返回冲突，需通过映射修订接口追加。故障清理只针对本次新建产物，不覆盖既有数据版本。完整结构见 [输入与版本合同](data-contract.md)。

## 质量与运行

`/api/projects/{id}/runs` 已实现质量任务的提交、历史、详情、取消、分析准入校验和有效视图预览。清洗策略挂在数据版本下。完整路径、schema、状态与不可变资产见 [质量与任务合同](quality-and-runs.md)。分析入口校验不执行算法；聚类、关联和报告接口尚未实现。

`AnalysisRun` 固定 project_id、dataset_version_id、mapping_version_id、policy_id、kind、parameters、idempotency_key；结果引用同一个 run_id 和输入上下文。质量证据 ID 与指标已随报告保存，单独 evidence 路由暂未实现。

## 后续模块接口边界

算法与独立证据接口接入时继续遵循：

| 对象 | 必须携带的上下文 | 接入原则 |
| --- | --- | --- |
| AnalysisRun | project_id、data_version_id、run_id | 固定映射、清洗及参数版本；状态与产物属于同一运行 |
| Evidence | project_id、data_version_id、run_id、evidence_id | 引用必须属于同一项目及运行，不跨版本拼接 |

后续算法任务可扩展运行机制，证据归属运行下的 evidence。服务端必须逐层校验资源归属，不能仅依靠前端传入 ID。当前未实现的 API 返回 404，不伪造空分析结果或成功状态。见 [分析模块接入](analysis-extension.md)。

组件接入点：`DataWorkspace` 的版本视图、`ImportEditor` 的导入流程、`MappingEditor` 的字段与业务口径、`DataPreview` 原始预览、`QualityWorkspace` 的策略/任务、`QualityReport` 的能力/有效视图，以及 `States` 的加载/错误/空状态。AI 网关、挖掘和报告应有独立模块，不由导入或质量接口代替。
