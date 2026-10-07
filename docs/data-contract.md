# 输入、映射与版本合同

## 三层数据

1. 原文件 `source.csv` / `source.xlsx` 按上传字节原样保存，以 SHA-256 标识。上传展示名称不作为磁盘路径；目录使用服务端 UUID。
2. `raw.parquet` 保存流式解析的原值，列为 `c0…cN` 与 `source_row_id`。所有值为可空 UTF-8 字符串；空白字段为 null，完整原字节仍在原文件。CSV 的来源编号按逻辑记录编号，XLSX 按工作表与行号。日期型 Excel 值转换为 ISO 表示，数字型 ID 不声称恢复已丢失的前导零。
3. 每个映射版本有 `canonical.parquet`、`mapping.json` 和 `order_amounts.parquet`。canonical 是已对应语义名称的原值层，并非质量合格表；金额、时间和状态仍需按确认设置做完整质量检查。订单金额表单独按订单存储候选金额，不能把明细中的重复 `order_amount` 再求和。

## 字段与配置

标准列为 `source_row_id, order_id, item_id, item_name, customer_id, event_time, quantity, unit_price, line_amount, order_amount, currency, record_status, country, category`。缺失字段为 null，不由模型、姓名、相邻行或默认零值补齐。

映射使用内部列键而不是直接拼接用户表头。一个原列只能对应一个语义。精确别名可提出建议；`Total/Amount/Price/金额` 等含义不明的列不自动归为行金额或订单总额。公开 Retail II 的 Price 含义只通过该源的说明提出建议，也要人工确认。

每次确认固定：列映射、订单边界、金额来源、固定币种或币种列、数量单位、时间格式与 IANA 时区、取消/退货解释、原始状态对照。确认开关不可省略；改动任一设置后页面要求重新确认。不明确的含义可以显式选未知并保留警告，不因此宣称具备分析能力。

只有显式选择 `basket_list` 时，才允许以原始行生成篮子标识并拆分商品列表；只生成篮子和商品两列，原文件保留。`basket_long` 与交易明细不会自动猜测订单边界。Groceries 的篮子编号来自原对象列序号，不是对商品行逐行造订单。

## 金额

金额来源只选一种：不使用、行金额、数量 × 单价、订单总额。行金额与订单总额分开保留，不能混加。金额用 Decimal，输入超过 28 位有效数字或绝对十进制数量级超过 28 时视为待核验原值；计算采用 100 位上下文，无默认四舍五入或汇率换算。

`order_amounts.parquet` 每个订单只有一条记录，包含原始行数、金额候选、币种、冲突原因及 `quality_gate=pending`。同单总额 100、100 只产生 100；100、120 或 100、非法非空金额不产生可用候选。行金额 40、60 得到 100，不再加订单总额。币种、客户或原始时间冲突也记录原因。取消/退货、负数、完整性、时间解析、有效范围及所有质量门控仍必须在质量模块完成，不能直接把候选用于 RFM。

部分订单筛选合同：保留全部明细时可使用核验过的订单总额；只留部分明细时，必须有对应的可靠行金额，否则返回金额不可用，不能分摊整单总额。`scoped_amount` 只表达该金额边界，调用者必须先核验来源行集合与订单完整性。

## 不可变资产

```text
storage/
  state/retailevidence.sqlite3
  imports/<draft-id>/                  # 应用自己的待确认上传
  datasets/public/<source-id>/         # 正式公开原始 / 转换数据
  datasets/projects/<project-id>/<version-id>/
    source.csv | source.xlsx
    raw.parquet
    version.json
    mappings/1/{mapping.json,canonical.parquet,order_amounts.parquet}
    mappings/2/{mapping.json,canonical.parquet,order_amounts.parquet}
```

以上均为运行所需资产。开发测试脚本、测试数据库、测试缓存和实验中间产物在工程外保存。

数据版本以项目内递增编号和 UUID 定位。相同文件再次上传仍是新版本。映射通过 `expected_revision` 追加；旧配置和产物保持原样。新解析生成新的 preview token；旧 token 不得确认。相同 token 与相同配置的重复确认返回原版本；不同配置返回冲突。新版本先生成完整目录再登记数据库，正常异常回滚本次新目录。进程被强制杀死时可能留下 `.building-*` 或未登记映射目录，自动重试不会覆盖它们，应核验后处理。

后续运行和报告必须同时固定 `project_id + dataset_version_id + mapping_revision`，不得在读取历史结果时隐式套用最新映射。

质量检查现在由独立运行生成规范化行、互斥排除明细、RF/RFM 唯一订单、金额订单及完整购物篮视图。每次固定清洗策略与筛选范围，原有三层输入仍保持不变。具体粒度、准入条件及源行关联见 [质量与任务合同](quality-and-runs.md)；下游通过 [分析输入解析器](analysis-extension.md) 检查能力与产物完整性。
