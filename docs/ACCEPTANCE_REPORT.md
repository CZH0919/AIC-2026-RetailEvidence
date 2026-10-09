# 实际验收报告（持续更新）

执行日期2026-10-09，主要环境Ubuntu24.04/CPU8/Python3.12.3/Node24.21.0；所有写入个人隔离目录。历史0.5记录单列，不计本轮PASS。最终远端main SHA与复验尚待写入release证据。

已执行：候选c8e7f9e3069cd8c943f591c7b6fe1db9d71bdd2d；干净依赖候选1b128111f6c5c62151942b9a9cc7758f2c64b9c3（业务源码相同）。原干净环境38唯一pytest PASS；后续扩展为40（分类销售26/真实子进程任务7/模拟AI契约7），新增2项已实际通过，最终干净环境总跑待执行；在线备份工具7项独立机制检查PASS，Ruff、tsc、Vite PASS。FastAPI TestClient有httpx弃用提示，Vite967KB chunk提示保留，不因此降低发布阈值。

真实原始XLSX541909行SHA43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d。独立原始计算：全类型628438/1154194.23GBP；声明特殊类型且费用不计销售额的验收假定下，实物626765/1105884.75GBP/2863商品。运费406/26681.09、人工1263/21548.67、其他4/79.72；分项可核对。差额307/785.07来自同单冲突过滤口径。不是商户确认或收益证明。

c8e7f9e检查run c3f6dd4d-b4af-4572-8d3c-12fccb7ea334（49.18秒），完整run e8ac1971-9e1f-45c3-bb2b-89f5e66ff984（61.47秒）。真实CPU AI_used=true、evidence/run/classification哈希绑定。机器运行与工件manifest可核对，不把AI回退记为推理成功。

时间切分验证9/20、9/27、10/4，独立测试10/11、10/18、10/25；复杂法MAE90.576004/WAPE93.096754%，四周平均MAE63.629083/WAPE65.399894%，采用四周平均。eligible1321/tested1000/published382，历史候选1061/resource excluded61。异常train270990/test93341/flags2106/simple10473，无标签准确率NOT_APPLICABLE。

HTTP首轮前13项实际PASS：项目/修改409、CSV真实日月派生金额一致、幂等参数冲突409、跨项目404、类型作用域422、重复上传生成不可变版本且重复合并拒绝、原始XLSX导入541909行。随后因错误挑选Groceries质量夹具失败，修正选择后旧RF/RFM/FP-growth、旧报告哈希不变、缺历史工件404、路径穿越404和旧AI分类保护共8项PASS。完整首轮并非整体PASS，不删除失败日志。9fe8c11完整重跑20项全部PASS（api-regression-candidate-three.log），不再以拆分首轮代替整轮回归。

新增真实质量检查run d12c82c0-195c-4637-87ac-85743a7f2dd1，October限定：RF1363客户/RFM1360客户、2128完整篮，completed_with_warnings，实际质量限制保留。旧算法结果未被分类功能重写。

候选3668063浏览器桌面/390px、2863全商品、5摘要/3行动、异常原始3行、备注409、真实AI、HTML和PDF实际PASS；PDF两页，首页摘要与中文截图视觉核对（Codex）PASS。这是标注SHA的本轮较早候选，不替代最终代码浏览器复验。9fe8c11严格AI浏览器上传全流程实际PASS，project 57c289b1-b9ec-4f34-912f-17aec2eef8b4，version 97b82239-e043-4649-8d2c-b6bad3bcc5fc，run da9873f6-c2ae-4270-90db-312e6c35fb02；AI真实推理且无不当承诺，三会话/导出/搜索返回通过。排序/分页2/滚动300/映射取消/新任务取消专项PASS，取消run 86d6e3cf-0136-422d-b42f-6ee6cf380f0e。最终main复验仍待执行，不提前宣称交付完成。

实际命令、数据SHA、runID、资源、结果与缺陷在docs/acceptance_matrix.csv及外部个人evidence/logs记录。主要日志：classified-public-candidate-two.log、clean-units-fresh-quality.log、task-ai-tests.log、legacy-regression-retry.log、browser-import-candidate-two-retry*.log、clean-install-candidate-two*.log。远端evidence/classified_public_candidate_02包含原始对账/模型回测/manifest/AI与全部CSV，browser_candidate_01含真实截图与PDF。

真实非开发者/商户试用BLOCKED（无参与人员）；录制视频、官方赛事核查与平台提交NOT_RUN；公网部署/鉴权BLOCKED（无批准）。这些不由模型冒充。GitHub尚未推送；必须最终候选复验后再推送main并fetch核对SHA。正式共享系统未部署，保持批准前不改动。

矩阵候选统计：{"PASS": 37, "FAIL": 0, "BLOCKED": 3, "NOT_RUN": 1, "NOT_APPLICABLE": 3}。剩余发布/最终复验任务明确待执行。
