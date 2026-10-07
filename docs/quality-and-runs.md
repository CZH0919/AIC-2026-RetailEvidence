# 质量、有效视图与任务合同

适用于应用 0.3.0、数据库 schema 3、质量策略 `quality-v1`。质量准备为确定性处理，不调用模型，不执行聚类或关联挖掘。

## 版本与范围

一次质量运行固定项目、数据版本、字段映射 revision、清洗策略 ID 和观察范围。相同映射下相同策略返回已有策略，变更产生新策略编号。重跑产生新运行，已有原始文件、映射和结果不覆盖。

策略：`trim_identifiers` 默认 true，仅修剪标识首尾空白，保留前导零；`duplicates` 默认 `keep`，用户明确选择 `drop_exact` 才移除原始全列完全相同的后续记录；`monetary_subset` 默认 `all_customers`，可明确改为 `complete_customers`；`accept_selected_amount_source` 默认 false，多金额来源冲突时须确认采用已选择的来源。

范围包含起止日期、国家/地区、商品 ID、单一币种。日期按已确认业务时区解释，起止日均包含；无映射字段不能使用对应筛选。时间先按确认格式解析，再保存 UTC ISO 时间；夏令时歧义/不存在的无偏移本地时间不猜测。带明确偏移的时间可正常转换。

每次运行的 `manifest.json` 记录上述上下文、参数、原始文件摘要、映射/策略/程序摘要、依赖版本、运行时间、采样峰值 RSS 和每个产物摘要。`quality_report.json` 保留范围、策略、映射与证据标识。内部子进程路径不进入发布的 manifest。

## 有效视图

结果目录由服务端以 `storage/runs/<project_id>/<run_id>` 生成；客户端不得提供目录或任意执行代码。

| 产物 | 粒度与用途 |
| --- | --- |
| `normalized.parquet` | 与原始展开行一一对应；规范化字段、`source_row_id`、问题标签和重复候选；仍包含不适用行，不能直接当算法输入 |
| `row_audit.parquet` | 与原始行一一对应；公共、RF、RFM、金额和关联分别给出唯一主原因，另保留多个问题标签 |
| `rf_orders.parquet` | 每个 RF 有效订单一行；用于客户最近时间和唯一订单频次 |
| `rfm_orders.parquet` | 每个金额完整客户的有效订单一行；必须同时通过 RFM 能力判断才可用于分群 |
| `amount_orders.parquet` | 每个金额可靠订单一行；可不含客户或时间，不能直接用于 RF/RFM |
| `basket_items.parquet` | 每个完整购物篮中的不同商品一行；`order_id,item_id` 唯一，单商品篮保留 |

订单视图字段：`order_id,customer_id,event_time,currency,amount,amount_source,source_rows,effective_source_rows,selected_rows,partial_order`。金额保存为精确十进制字符串，下游金额累加使用 Decimal；禁止先转 binary float 再汇总。`source_rows` 为原始订单行数，`effective_source_rows` 为确认去重后的行数，`selected_rows` 为通过公共质量和范围的行数。

`normalized.line_amount` 在“数量×单价”模式保存派生值，`source_line_amount` 留存原映射的行金额。`row_audit.source_row_id` 与 S02 `raw.parquet` / `canonical.parquet` 的同名字段关联，可回到原始行；订单/商品标识用于连接有效视图。

报告每个 `views.*` 均满足：`included_rows + excluded_rows = raw_rows`，`primary_reasons` 含 included 且总和为原始行数。问题标签允许重叠，不能相加当删除数。有效行、唯一订单、客户和购物篮属于不同粒度。

## 业务判断

- 同单客户、时间或币种冲突：整单隔离。客户或时间缺失使该订单不能进入 RF，但不单独破坏商品关联；没有可靠订单边界时不猜测订单。
- 取消/退货按已确认规则处理；只有用户选择 UCI 取消前缀规则，`C` 开头订单才作为取消。缺失/非法数量、未知状态与缺失商品会标记已知不完整购物篮，整篮排除；不把剩余好行当完整篮。完整性只针对提供的数据。
- 重复商品在篮中去重；同一订单与商品的不同数量/金额行不是“完全重复”，不得误删。
- 同单重复总额 100/100 只计 100；100/120 不取第一条、平均值或求和。行金额 40+60 计 100；行金额与订单总额不叠加。
- 订单被范围或质量过滤成部分明细时，只有可靠保留行金额才可按这些行重算，来源标为 `selected_lines`；不直接使用或比例分摊原总额。
- 默认有任一 RF 客户金额不完整时不启用全体 RFM；只有用户明确选择金额完整客户才可评估该子集。对应候选视图存在不表示能力已放行。缺金额可以使用 RF；多币种先明确筛选单币种，不自动换汇。
- RF/RFM 输入门槛为至少 50 个客户、至少 7 天有效跨度、至少两种不同特征组合。这里只是输入门槛，实际变换、候选 K 和有效聚类诊断由后续模块完成。
- 关联输入门槛为至少 200 个完整篮、至少两个商品。超过 10 万篮、5,000 商品或单篮 100 个不同商品时返回资源受限，不能静默截断后宣称通过。

能力 `allowed` 是后端准入依据；`state` 为 available/limited/unavailable/resource_limited；`reasons` 提供可操作解释。limited 可以准入但必须保留范围限制；unavailable/resource_limited 不得运行相应算法。

## HTTP 接口

以下路径前缀均为 `/api/projects/{project_id}`；所有版本、策略和运行校验所属项目。

| 方法与路径 | 行为 |
| --- | --- |
| POST `/versions/{version_id}/policies` | `mapping_revision,config`；创建或复用不可变策略，201 |
| GET `/versions/{version_id}/policies` | 策略历史 |
| POST `/runs` | 提交质量检查，202；必填 `dataset_version_id,policy_id,idempotency_key`；可选 scope、timeout_seconds、memory_mb |
| GET `/runs` | 可按 dataset_version_id、kind 过滤，默认 30，最多 100 条 |
| GET `/runs/{run_id}` | 运行状态、事件、已发布结果 |
| POST `/runs/{run_id}/cancel` | 取消指定运行；终态调用不会重启或删除结果 |
| POST `/runs/{run_id}/eligibility` | `AnalysisParameters` 校验；200 放行，409 不适用，422 参数错误；不执行算法 |
| GET `/runs/{run_id}/rows` | 已发布白名单视图预览；默认 20 行，最多 100，offset 最多 10,000 |

幂等键作用于项目：相同键与相同请求返回原运行；同键改变设置返回 409；用户主动重跑使用新键。字段/清洗/范围变化不得覆盖旧结果。列表需显式用 `kind=quality`，避免后续模块把算法运行当质量报告。

`AnalysisParameters` 固定 kind=rf/rfm/association；K 范围 2–8 且起点不大于终点，seed=42、n_init=10；关联 min_support∈(0,1]、min_count≥1、min_confidence∈(0,1]、max_length=2/3。后续算法仍须结合实际输入检查有效候选 K、项集规模与运行预算。

## 运行与恢复

`queued → running → succeeded / completed_with_warnings / not_applicable / failed / cancelled / resource_limited / interrupted`。前三个结束状态发布完整质量报告；not_applicable 是已完成判断但没有可用分析，不能视作计算失败。失败、取消、资源受限、中断无成功结果。

SQLite 持久队列；同一状态库只允许一个消费者，同一资产目录用文件锁串行化导入和计算。服务单 worker 启动；增加 Uvicorn worker 数不能提高重任务并发。任务子进程两核/两线程，Linux 8 GiB 地址空间上限，父进程另监控 RSS；默认 600 秒，可选 1,200 秒；磁盘剩余低于 20 GiB 拒绝执行。多套完全独立状态/资产目录之间没有全局集群调度，维护者需避免同时重计算。

运行先写本任务的隐藏临时目录；所有必要产物、上下文和摘要通过后才原子改名并提交数据库结果。取消只终止本消费者创建的当前子进程。服务重启把遗留 running 标记 interrupted，不暗中重跑；queued 保留并继续。Linux 父进程异常退出由 PDEATHSIG 终止其任务子进程。

突发断电可能保留未登记的隐藏目录；这些不会作为成功结果提供，也不会无条件删除。维护者先核对状态库、运行 ID 与进程归属，再归档自己的中断产物。不能靠扫描目录认定一次运行成功。
