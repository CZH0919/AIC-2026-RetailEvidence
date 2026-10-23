# 可公开的小演示样例

public_monthly_small.csv 为 UCI Online Retail（Daqing Chen，CC BY 4.0，DOI10.24432/C5BW33）2011-10 正向有效记录的可追溯月汇总子集，18行。原始源SHA和本样例SHA见sample_origin.json。选择前10个实物分组、非实物分组及存在时一个名称含POST的正常商品；原全数据541909行评测集没有因此删减。

本文件仅演示，不是冻结预测/异常评测集，也不代表小商户账目。字段record_type是明示验收分类假定，使用者需确认；费用不计销售额是可选择口径，不是强制会计结论。

界面映射 item_id/名称name/数量quantity/行金额amount/分类record_type，选择月汇总、2011-10、GBP、原始商品单位、全部正向；分类规则精确匹配record_type：physical_product计入，shipping_service/manual_adjustment/other排除，确认后检查再生成。此小文件没有日历史，预测/异常应不可用。

来源：[UCI官方](https://archive.ics.uci.edu/dataset/352/online+retail)。变化：过滤质量规则、同单冲突排除、按商品及名称汇总、添加需确认分类列、取明示小子集，无客户标识/订单号。
