# 分析历史展示：候选通过，发布复验待完成

基线47e6252；d4c7d3d产品仅QualityReport/新增AnalysisHistory/局部analysis.css。默认、参数、API/后端/数据/旧结果不变。8专项+9完整流程+18Node/构建+17对账PASS，首两次定位失败保留。新个人18106，旧18114不动。后续正常推main、实际SHA干净检出复验、本机18115；完整记录docs/ANALYSIS_HISTORY_DISPLAY.md，最终凭release2/evidence/release_receipt.json。未经批准不切换旧演示/共享正式，无C盘主动写入。

补充新任务在历史列表尚未刷新时的显示与2RAF首屏断言，全部17浏览器/18Node/构建/17对账重跑PASS。待该最终提交实际SHA的release2复验，旧release/ac751c2不能当最终版本。


# Current task: account login — 2026-10-23
Branch feature/account-login. Base cafe057 (0.6.3/schema5), candidate0.7.0/schema6.
Self-registration, account isolation, password changes, login UI and workspace refinements implemented.
Remote personal isolated directory updates/auth_ui_20261023_01; local D:/AIC_RetailEvidence_Work/delivery_20261009_01/auth_ui_20261023_01. Temporary authoring scripts in E:/小仙女专属/数据挖掘/数智证析/auth_ui_staging_20261023_01.
Verified: online backup and migration/restore copy; 85 pytest +6subtests; browser12groups including CPU model/exports/RF/RFM/association. Original/shared databases unchanged.
Preview18107 uses isolated state/storage; personal model18102 resumed with existing script. Old demo18106 remains stopped after reboot, not replaced.
Before delivery: push only after source review; fresh final-checkout build/browser proof; record SHA and final preview endpoint in external task evidence/release.json.
Historical presentation-only snapshot guard failures retained, not deleted; applicable help/report guards run separately. No C exception.
