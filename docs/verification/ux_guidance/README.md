# UX证据核验

EVIDENCE_SHA256.json计算Git索引中的规范文件字节SHA-256，不包含自身。Linux干净检出的文件可直接sha256sum；Windows若使用CRLF检出，应先读取Git规范blob再计算SHA（git show HEAD:docs/verification/ux_guidance/<路径>），不能把换行差异当证据修改。图片/PDF二进制不改变。

初次审查与后续修复、失败尝试和真实main复验分别存储，收据带实际运行SHA/命令/耗时。README不是通过凭证，应检查源码、results、日志与对应截图。公开数据测试说明与模拟库存不等于真实商户确认。完整原始浏览器产物和最终最新SHA复验收据保留在个人隔离工作区，不提交数据库、大数据或凭据。
