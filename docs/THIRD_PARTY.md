# 来源、贡献与许可说明

## 团队自研内容

团队共同完成业务流程、数据合同、质量与任务机制、分析集成、证据解释、网页交互、测试和文档。提交历史保存作者及贡献来源；个人账号托管不代表所有内容由该账号持有人独立原创。

开发过程中使用了 AI 辅助工具进行部分实现、检查和文档整理，团队负责需求决策、代码审核、测试与结果确认。辅助生成内容不构成独立测试证据，也不代替对第三方资源权利的核查。

**当前仓库未附团队自研代码的独立 `LICENSE`，尚未选择开源许可证。** 代码可查看与获得使用、修改、分发授权不是同一件事。若需正式开源，应由共同权利人确认许可范围后添加准确的许可证及署名；本文不替代该授权。

## 软件与模型

| 资源 | 用途 | 来源与核对位置 |
| --- | --- | --- |
| FastAPI、Uvicorn、Pydantic、SQLAlchemy | 服务、请求校验与持久化 | `requirements.txt`；各项目发行包中的许可文件 |
| NumPy、pandas、SciPy、scikit-learn、mlxtend | 数据处理、预测、聚类与关联 | `requirements-mining.txt`；对应锁定版本发行包 |
| PyArrow、openpyxl、defusedxml、psutil | 表格读取、资产与资源控制 | `requirements.txt` |
| React、TypeScript、Ant Design、Vite 及前端依赖 | 界面与构建 | `frontend/package.json`、`package-lock.json`；发行包许可 |
| llama.cpp | 本机 CPU 模型推理 | [官方项目](https://github.com/ggml-org/llama.cpp)，以实际部署版本许可为准 |
| Qwen2.5-1.5B-Instruct GGUF | 证据解释模型 | [官方模型](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF)，模型页列示 Apache-2.0；下载时记录版本与条款 |

依赖的许可证不自动覆盖团队自研代码。模型权重、二进制和依赖目录未纳入源码仓库。发行或再分发前应核对锁定版本的许可证、NOTICE 和必要署名；此表不是完整软件物料清单或法律审查结论。

## 数据与素材

公开数据的来源、下载记录及限制见 [public-data.md](public-data.md) 和 [public-data-manifests.json](public-data-manifests.json)。公开可下载不等于可以省略来源或任意再分发。

青禾便利店数据用于模拟演示，不代表真实经营、客户或收益。真实商户明细、数据库、账号密码、会话、模型文件和敏感截图不作为项目源码提交。演示素材应避免包含无权公开的个人信息。

产品界面参考通用业务后台的布局原则，不以第三方品牌、字体或资产许可代替自身素材授权。新增外部图片、字体或数据时，应补充准确来源和使用条款。
