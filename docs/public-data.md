# 公开数据来源与复现

核查日期：2026-10-07。以下为真实文件流式读取结果，不将页面介绍等同于文件质量。

| 数据集 | 读取结果 | 时间 / 结构 | 来源与许可记录 |
| --- | --- | --- | --- |
| Online Retail | 541,909 行、8 列 | 单表；2010-12-01 08:26 至 2011-12-09 12:50 | [UCI 352](https://archive.ics.uci.edu/dataset/352/online+retail)，Daqing Chen (2015)，DOI 10.24432/C5BW33，CC BY 4.0 |
| Online Retail II | 1,067,371 行、8 列 | 两表分别 525,461 / 541,910 行；2009-12-01 07:45 至 2011-12-09 12:50 | [UCI 502](https://archive.ics.uci.edu/dataset/502/online+retail+ii)，Daqing Chen (2012)，DOI 10.24432/C5CG6D，CC BY 4.0 |
| Groceries | 9,835 篮、169 类商品、43,367 条篮子—商品记录 | 原对象无客户、金额或逐篮时间；没有空篮或同篮重复商品 | [固定来源说明](https://raw.githubusercontent.com/mhahsler/arules/1eccd3800209b4ec62c7f41abd2ff5f584a20ec7/man/Groceries.Rd) |

Online Retail 的 Description 缺失 1,454 行、CustomerID 缺失 135,080 行；C 前缀取消 9,288 行，非正数量 10,624 行，非正单价 2,517 行。UCI 页面“No missing values”与客户和描述列实际缺失不一致，以原始文件统计为准。

Retail II 的 Description 缺失 4,382 行、Customer ID 缺失 243,007 行；C 前缀取消 19,494 行，非正数量 22,950 行，非正单价 6,207 行。上述计数允许交叉，不能相加冒充唯一排除行数。两套 Retail 的时间范围重叠，Retail II 第二表比独立 Retail 多一行；分别保存，不能混合作为独立样本。金额单位按官方说明为 GBP，取消 C 前缀仅在确认该来源规则时启用。

## Groceries 来源与转换

固定 arules commit：`1eccd3800209b4ec62c7f41abd2ff5f584a20ec7`。下载 `data/Groceries.rda`、`DESCRIPTION` 与 `man/Groceries.Rd`。该 DESCRIPTION 记录包许可 **GPL-3**；Groceries 说明要求引用 Hahsler、Hornik、Reutterer (2006)，没有另列数据专属许可。包许可与数据说明分别记录，不自行标注为 CC0 或 UCI 的 CC BY。源码仓库不包含原始数据与完整转换数据；正式再分发前按实际使用方式核对数据条款。

参考文献：Michael Hahsler, Kurt Hornik, Thomas Reutterer (2006), *Implications of probabilistic data modeling for mining association rules*, pp. 598–605, Springer-Verlag。

使用 `rdata==1.1.0` 读取原始 transactions 对象的 ngCMatrix 稀疏矩阵。矩阵维度为 169×9,835，`p` 定位每个原篮的区间，`i` 指向 `itemInfo.labels`；按原列序号 +1 保存 basket_id，以原类别标签作为 item_id。转换前验证维度、指针与标签唯一性，转换后核对数量与摘要。保留 RDA 和来源通知，不生成时间、客户或金额。

## 运行方式与清单

从项目任意工作目录执行下载与统计脚本，默认输出在项目的 `storage/datasets/public`。`--output` / `--root` 的相对路径也从项目根解析。依赖安装和入口见 [README](../README.md)。运行设置限制两核，模型与大数据不自动下载到开发电脑。

每个数据目录的 `dataset_manifest.json` 保存下载 URL、固定版本、取得时间、文件字节数与 SHA-256、实际统计和生成脚本摘要。公开数据导入再次核对实际源文件与 manifest 摘要，并将来源快照随数据版本保存；校验失败不会继续创建版本。

可审阅的清单副本见 [public-data-manifests.json](public-data-manifests.json)，其中不包含明细。生成脚本摘要记录实际执行时内容；后续仅格式化源码不会改写历史来源记录。CSV 与 Parquet 均为派生产物，不能冒充源文件。
