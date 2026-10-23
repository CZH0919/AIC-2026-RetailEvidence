# 账号、登录与数据归属（0.7.0）

## 用户操作

1. 打开网站，未登录时进入登录页；首次使用点击“创建账号”。
2. 用户名为 3–32 位字母、数字、下划线或短横线，首位为字母或数字，不区分大小写。密码为 12–128 个字符，注册时再次确认。
3. 注册成功自动进入自己的项目库。新账号没有默认店铺、数据或他人的历史演示报告。
4. 新建项目并上传自己的数据，后续导入、人工确认、销售月报、商品核查、库存参考、AI、客户分群、共购和导出流程沿用现有规则。
5. 右上角账号菜单提供“修改密码”和“退出登录”。修改密码使其他登录会话失效；退出前会提醒尚未保存的填写内容。
6. 登录有效期为 12 小时，到期需要重新登录。已保存的报告保留。浏览器保存会话，前端不把密码或会话令牌存入 localStorage。

目前使用用户名登录，没有邮箱验证、短信或邮箱自助找回。忘记密码由维护者核对身份后使用服务器工具重置；请不要在聊天、日志或命令参数中发送密码。

## 服务端保护

- 全部 `/api/` 业务接口默认要求有效会话，仅健康检查、注册、登录公开。项目级路径统一核对 `project_id` 的账号归属，再由现有子资源检查核对版本、任务与文件归属。
- 项目列表、数量、搜索、同名校验均按账号限定。直接访问他人的项目、来源数据、AI、任务、备注、HTML 或 CSV/JSON 下载返回 404；未登录返回 401。
- 密码采用随机盐 scrypt（N=32768、r=8、p=3），同时最多执行两次密码派生。数据库只存密码摘要与会话令牌的 SHA-256 摘要。
- Cookie 为 HttpOnly、SameSite=Strict、host-only、Path=/。所有修改请求要求本站的 `X-Requested-With: RetailEvidence` 头，并保留来源检查，不启用跨域凭据访问。
- 登录按来源地址每 15 分钟 60 次、按用户名每 15 分钟 15 次限制；注册按来源每小时 10 次。限流计数持久化，不信任转发地址头。SSH 隧道下各用户可能共享来源限额。
- 登录替换本浏览器旧会话；退出立即撤销当前令牌；修改密码撤销该账号其他会话。多标签页通知只发送“账号变化”，不发送令牌或密码。
- 最近访问历史使用账号独立的浏览器存储键。旧版无账号的历史键不再展示。共享电脑上退出仍需关闭已下载的文件；退出无法收回用户已经保存的导出文件。

## 数据库与已有项目

Schema 5 → 6 是增量迁移，新增 `accounts`、`account_sessions`、`project_owners`、`auth_throttle` 四张表，不重建销售表，不重算历史报告。原项目、数据版本、来源文件、运行及备注保持原样。

历史项目默认没有账号归属，因此任何自行注册的用户都不能自动取得它们。管理员必须核实目标账号与具体项目后明确分配。不要把“第一个注册的账号”当成管理员。

为了保留旧库的全局唯一索引，新建或明确分配的项目内部 `name_key` 使用“账号 UUID:标准化名称”。显示名称和历史报告内容不变；同一账号不能重复命名，不同账号可以使用相同名称。内部键不是授权依据，授权始终检查 `project_owners`。

## 安全启用与恢复

仅在独立环境验证通过并批准部署后，才可升级已有运行库。部署前检查队友改动、使用 SQLite 在线备份、保存源码和构建。不要单独复制活动数据库主文件。

本轮预览使用独立空数据库、独立存储与回环端口，没有升级共享正式库或原个人演示库。Schema 5 备份已在独立副本验证升级和恢复。旧代码不支持 schema 6；回滚应切回保留的旧服务/旧数据库或经审核的完整备份，不能把新库直接交给旧代码。升级后新增的账号与数据需要另行保留，不能盲目恢复旧备份覆盖。

本地 SSH 隧道 HTTP 预览使用 `AIC_COOKIE_SECURE=0`。经批准的公网部署必须配置 HTTPS、`AIC_COOKIE_SECURE=1`、正确的受信主机及反向代理；本轮没有开放公网或完成公网部署。生产还需独立审核注册滥用、配额、备份和密码恢复人员流程。

## 维护者工具

在源码目录、已有虚拟环境和经批准的 schema-6 数据库上执行。下面路径是占位示例，正式部署命令待审批。

```bash
# 仅校验，不分配；必须指定实际数据库、已注册用户名和具体未分配项目。
PYTHONPATH=backend .venv/bin/python scripts/account_admin.py \
  --database /approved/state/retailevidence.sqlite3 \
  --username shop_owner --assign-project PROJECT_UUID
# 取得归属批准后追加 --apply 才会操作；会先生成在线备份与收据。

# 维护者核实身份后恢复账号，密码通过终端隐藏输入，不放命令参数。
PYTHONPATH=backend .venv/bin/python scripts/account_admin.py \
  --database /approved/state/retailevidence.sqlite3 \
  --username shop_owner --reset-password --apply
```

工具不能转移已有归属项目，不会创建账号，不会自动迁移数据库。操作备份位于数据库旁 `account-backups/<时间>/`，包含私有数据，不进入 Git。重置密码会撤销该账号所有旧会话。

## 实现与参考

`backend/app/auth.py` 为统一认证边界；`models.py`/`database.py` 为增量持久化；`main.py` 为路由依赖与账号限定项目查询；`frontend/src/Auth.tsx`、`auth.css` 为登录、注册、账号操作和视觉样式；`api.ts` 统一携带同源请求头；`Shell.tsx` 隔离最近访问记录。

实现依据包括 [OWASP 会话管理](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)、[CSRF 防护](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) 和 [认证建议](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)。使用现有 FastAPI、SQLAlchemy、React、Ant Design 与 Python 标准库，未添加认证云服务、外部字体或图片依赖。

登录背景是本项目 CSS 绘制的装饰，不是真实经营图表；对辅助技术隐藏。首页只调整表面、边框和对齐，现有业务字段、算法与报告规则保持不变。
