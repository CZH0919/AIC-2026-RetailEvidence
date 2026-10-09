# 来源、许可与贡献

团队共同代码：原始Git历史及作者保留，服务器0.5.0以明确来源增量提交。LSTongXXN创建私有仓库与本轮修复整合，不代表独占原创；未添加未经团队确认的全项目LICENSE。团队已批准审查后私有托管，公开发布仍需另行许可确认。

AI辅助：Codex协助源码审查、分类实现、测试、文档和隔离执行；数据数字由确定性程序计算，真实测试日志保留，AI不替代真人验收或权利审核。

|依赖/数据/模型|本轮版本或指纹|许可/归属|取得方式|
|---|---|---|---|
|FastAPI / Uvicorn / SQLAlchemy / Pydantic|requirements.txt固定版本|上游MIT；保留安装包许可|各包官方发行|
|PyArrow|25.0.1|Apache-2.0，含其第三方NOTICE|Apache Arrow/PyPI|
|NumPy / pandas / scikit-learn / SciPy|2.5.3 /3.0.6 /1.9.1 /1.18.1|主体BSD，wheel附带多种第三方许可，不以主体许可覆盖所有捆绑库|安装包dist-info许可|
|mlxtend|0.25.0|BSD3，部分素材CC-BY；本系统使用算法|安装包LICENSE文件|
|React / Ant Design / TypeScript / Vite / React Router|frontend/package-lock.json|分别MIT/MIT/Apache-2.0/MIT/MIT，传递依赖以lock及包许可为准|官方npm固定完整性|
|Playwright / Chromium / Noto CJK|1.62.1 /151.0.7922.34 /Ubuntu24.04提供字体|Apache-2.0/BSD等第三方许可/OFL1.1；仅个人验收环境|工具与字体官方发行|
|Online Retail|541909行；XLSX SHA43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d|Daqing Chen，UCI CC BY4.0，DOI10.24432/C5BW33|[UCI官方](https://archive.ics.uci.edu/dataset/352/online+retail)|
|Groceries/arules|团队已固定的原包，具体版本见数据manifest|arules软件GPL；底层数据再分发许可尚待专门确认，不随Git上传|原项目公开数据manifest|
|Qwen2.5-1.5B-Instruct-GGUF Q4_K_M|1117320736字节，SHA6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e|官方模型Apache-2.0；本轮实文件与官方公布SHA一致|[官方模型文件](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/qwen2.5-1.5b-instruct-q4_k_m.gguf)|
|llama.cpp|b11429，d81235049|MIT|[上游许可](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE)|

不上传模型权重、原始大数据、数据库、私钥、Token、个人真实商户信息或共享运行产物。examples中若有UCI派生小样例，其出处与变化在独立README声明；样例仅演示，不替换评测样本或降低门槛。模型/依赖/系统包原许可随获取资产保留，不能因本仓库忽略大型资产而忽略使用许可。

公开模型下载可使用官方文件页，保存到自己的模型目录，执行sha256sum与上述实测值比较。新平台安装、下载和启动步骤尚未在所有操作系统验证；本轮只确认既有Ubuntu CPU服务及当前干净Python/Node环境。
