# 商品详情与计算依据抽屉修复（2026-10-14）

本轮修复“下个月先做这些 → 查看商品和依据 → 查看计算依据”被原商品面板遮挡的问题。测试使用青禾便利店完全模拟数据，不代表真实商户研究。

## 基线与复现

- GitHub main 与正在使用的个人后端源码均核对为 `3c0cdff6d18324b41a0bc1af80788b4a329b3258`；应用 0.6.3、schema 5、sales-v2.2.0。
- 项目 `8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a`，数据版本 `079c4221-28b1-460c-9df2-be174312d824`，运行 `35cf3631-064c-4a90-a845-b06485eb9a3e`。
- 本轮真实浏览器：先在月报打开“查看依据”，关闭，再打开“查看商品和依据”，点击商品底部“查看计算依据”。
- 复现时两层 `z-index` 均为 1000。依据已经打开，但命中检测 `elementFromPoint` 落在商品标题上，依据位于商品后面。新页面直接第一次打开商品、再打开依据时不会复现；因此必须测试此前打开过的顺序。
- 原因是同层级的独立 portal 按首次挂载顺序排列，关闭抽屉并不删除其 portal。

## 修复内容

- `frontend/src/overlayLayers.ts` 集中定义商品 1000、助手 1100、依据 1200、帮助 1300。
- `SalesWorkspace.tsx` 给相关抽屉明确层级；在子面板打开期间禁用底层 Esc 关闭，保持逐层返回。
- `HelpHint.tsx` 的 Drawer / Popover 高于依据，避免修复后帮助反而被遮挡。
- 商品详情始终保留，关闭依据不会重建库存表单或清空未保存的核对备注。
- 不变更销售计算、模型、分类、人工确认门槛、数据库 schema 或冻结报告；此次沿用 0.6.3 应用版本，前端补丁由 Git 提交区别，无新 tag。

## 本轮实际验收

| 项目 | 状态 | 实际检查 |
|---|---|---|
| 前端类型检查与构建 | PASS | `cd frontend && npm run build`，包含 `tsc --noEmit` |
| 原帮助内容合同 | PASS | `node --test scripts/test_ux_guidance.mjs`，3 项通过 |
| 隔离候选站浏览器 | PASS | 1440px / 390px × 首次 / 预先打开过依据和助手，4 组 |
| 已发布个人演示站浏览器 | PASS | 同样 4 组重新实际执行，非沿用候选结果 |
| 每组计算依据可见性 | PASS | 实际点击、标题命中检测、焦点在上层、无页面横向溢出 |
| 子层帮助、关闭和返回 | PASS | 帮助可见；Esc 只关闭帮助，再只关闭依据；关闭按钮也可用 |
| 库存和备注草稿 | PASS | 库存输入 11、未保存的备注经过打开/关闭仍一致 |
| 助手及助手内核对依据 | PASS | 实际提问、获得回复，依据高于助手；关闭后问题文字保留 |
| 月报导出 | PASS | 两个环境均实际下载 HTML，包含 66,434.4 销售额 |
| 冻结计算结果 | PASS | 发布前后完整 result 的规范 JSON SHA-256 相同 |
| 全量算法与全站导入回归 | NOT_RUN | 本轮仅前端层级补丁，未把此前数据包验收算作本轮重跑 |
| 真人商户可用性研究 | NOT_RUN | 本轮属于开发者真实浏览器自查 |

候选浏览器首次启动遇到服务尚未监听的启动时序错误，健康检查成功后从头重跑。原始失败日志保留在独立任务证据，不将失败当作通过。候选服务没有改动原站点；最终发布站另外重跑。

## 证据

原始及改后证据位于 `docs/verification/drawer_fix/`：

- `before.json` / `before_ordered.png`：遮挡命中结果和实际截图。
- `after_18096.json`：隔离环境 4 组实际记录。
- `after_18094.json`：已发布演示站 4 组实际记录。
- `after_1440_warm.png`、`after_390_warm.png`：实际改后界面，已做视觉复核。
- `build.txt`、`help_contract.txt`：构建及 3 项内容合同结果。
- `static_deploy.json`：旧资源哈希、备份哈希、发布前后 result 哈希相同、两个个人端口 HTTP 200。

## 重跑

安装项目既有依赖及 Playwright 浏览器后，在独立测试环境设置：

```bash
export PLAYWRIGHT_MODULE=/path/to/node_modules/playwright
export PLAYWRIGHT_BROWSERS_PATH=/path/to/isolated/browser-cache
export RETAIL_TEST_ROOT=/path/to/isolated/test-root
export RETAIL_BASE_URL=http://127.0.0.1:TEST_PORT
export RETAIL_PROJECT_ID=你的模拟项目ID
export RETAIL_RUN_ID=你的9月模拟月报ID
mkdir -p "$RETAIL_TEST_ROOT/evidence"
node scripts/browser_sales_drawers.cjs
```

本脚本对应本仓库青禾模拟数据包：9 月销售额 66,434.4，第一条行动对应可预测商品。其他数据应使用适合该数据的金额断言，不得改动算法门槛以通过。脚本输入库存和备注草稿但不保存，不重新生成月报；助手确实发送问答请求，HTML 保存到独立测试目录。

## 发布、备份与回退

已更新个人网站及青禾演示站使用的同一份前端静态资源。先备份旧 dist，再复制新哈希资源，最后原子替换 `index.html`；保留全部旧哈希资源，已打开旧页面的资源仍可取回。刷新页面加载新入口即可。

没有重启 Web 或 AI，没有迁移或替换运行数据库，没有修改共享正式项目。后台仍运行原 3c0cdff 后端，报告中的算法来源标识保留真实后端来源；新前端代码由本次修复 Git 提交标识。

内部备份在本次个人隔离任务的 `evidence/frontend_before.tgz`，SHA-256 见发布收据。回退只需从该归档取出旧 `dist/index.html`，在个人前端目录原子恢复；旧哈希资源仍保留，无须恢复数据库。禁止将本步骤用于覆盖共享正式目录。

本机代码、Git、缓存、临时文件及证据均位于 D/E 盘；浏览器 profile 位于远端个人隔离目录。未主动写入 C 盘或复制个人凭据。无法保证操作系统/Codex 自身后台绝对零写入。
