import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Alert, App, Avatar, Button, Dropdown, Form, Input, Modal, Spin } from 'antd'
import { ArrowRightOutlined, LockOutlined, LogoutOutlined, UserOutlined } from '@ant-design/icons'
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { request } from './api'

type User = { id: string; username: string }
type AccountState = { user: User | null; loading: boolean; unavailable: boolean; reload: () => Promise<void>; accept: (user: User | null) => void }
const AccountContext = createContext<AccountState | null>(null)
export const useAccount = () => useContext(AccountContext)!
const broadcast = () => { const channel = new BroadcastChannel('retailevidence.account'); channel.postMessage('changed'); channel.close() }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [unavailable, setUnavailable] = useState(false)
  const generation = useRef(0)
  async function reload() {
    const attempt = ++generation.current
    try { const result = await request<{ user: User }>('/auth/me'); if (attempt !== generation.current) return; setUser(result.user); setUnavailable(false) }
    catch (e) { if (attempt !== generation.current) return; setUser(null); setUnavailable(e instanceof Error && 'code' in e && e.code === 'network_error') }
    finally { if (attempt === generation.current) setLoading(false) }
  }
  const accept = (next: User | null) => { generation.current++; setLoading(false); setUser(next); setUnavailable(false); broadcast() }
  useEffect(() => {
    void reload()
    const expired = () => { generation.current++; setLoading(false); setUser(null); broadcast() }
    const channel = new BroadcastChannel('retailevidence.account')
    channel.onmessage = () => { setLoading(true); void reload() }
    const focus = () => { void reload() }
    window.addEventListener('account-session-expired', expired)
    window.addEventListener('focus', focus)
    return () => { channel.close(); window.removeEventListener('account-session-expired', expired); window.removeEventListener('focus', focus) }
  }, [])
  return <AccountContext.Provider value={{ user, loading, unavailable, reload, accept }}>{children}</AccountContext.Provider>
}

export function RequireAccount() {
  const { user, loading, unavailable, reload } = useAccount()
  const location = useLocation()
  if (loading) return <div className="account-loading"><Spin /><p>正在进入工作台…</p></div>
  if (unavailable) return <div className="account-loading"><h1>暂时无法连接工作台</h1><p>请检查网络或服务连接，再重新尝试。</p><Button onClick={() => void reload()}>重新连接</Button></div>
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  return <Outlet key={user.id} />
}

function safeNext(search: string) {
  const value = new URLSearchParams(search).get('next') ?? '/projects'
  return /^\/projects(?:\/|\?|$)/.test(value) && !value.includes('\\') ? value : '/projects'
}

export function AuthPage() {
  const { user, loading, accept } = useAccount()
  const location = useLocation()
  const navigate = useNavigate()
  const register = location.pathname === '/register'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [form] = Form.useForm()
  if (!loading && user) return <Navigate to={safeNext(location.search)} replace />
  const submit = async (values: { username: string; password: string }) => {
    setBusy(true); setError('')
    try {
      const result = await request<{ user: User }>(`/auth/${register ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify({ username: values.username, password: values.password }) })
      accept(result.user); form.resetFields(); navigate(safeNext(location.search), { replace: true })
    } catch (e) { setError(e instanceof Error ? e.message : '暂时无法登录，请稍后重试。') }
    finally { setBusy(false) }
  }
  return <main className="auth-page">
    <section className="auth-story" aria-label="数证智析介绍">
      <div className="auth-brand"><span className="brand-mark" aria-hidden="true"><i /><i /></span><span>数证智析<small>RetailEvidence Studio</small></span></div>
      <div className="auth-story-copy"><span className="auth-eyebrow">小店经营 · 心中有数</span><h1>看清每一笔销售，<br />从容做好下一步。</h1><p>把日常销售记录，整理成看得懂的月报。<br />发现值得关注的商品，让每一次判断都有依据。</p></div>
      <div className="auth-scene" aria-hidden="true">
        <div className="scene-orbit" /><div className="scene-window"><div className="scene-window-top"><i /><i /><i /></div><div className="scene-columns"><div /><div /><div /><div /><div /><div /></div><div className="scene-rule" /><div className="scene-rule short" /></div>
        <div className="scene-ledger"><span>每月回顾</span><div /><div /><div /><b>记录 → 发现 → 行动</b></div>
      </div>
      <div className="auth-story-footer"><span>销售月报</span><i /><span>商品洞察</span><i /><span>客户分析</span></div>
    </section>
    <section className="auth-entry" aria-labelledby="auth-title">
      <div className="auth-form-wrap"><div className="auth-mobile-brand">数证智析 <small>RetailEvidence Studio</small></div>
        <span className="auth-kicker">你的经营分析工作台</span>
        <h2 id="auth-title">{register ? '创建你的账号' : '欢迎回来'}</h2>
        <p className="auth-intro">{register ? '为自己的店铺，建立独立的数据空间。' : '登录后，继续查看你的店铺与销售月报。'}</p>
        {error && <Alert className="auth-error" type="error" showIcon title={error} role="alert" />}
        <Form form={form} layout="vertical" onFinish={submit} requiredMark={false} disabled={busy} className="auth-form">
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名。' }, { pattern: /^[a-zA-Z0-9][a-zA-Z0-9_-]{2,31}$/, message: '请输入3–32位字母、数字、下划线或短横线。' }]} extra={register ? '3–32位字母、数字、下划线或短横线，不区分大小写。' : undefined}>
            <Input size="large" prefix={<UserOutlined />} placeholder={register ? '例如 qinghe_shop' : '请输入用户名'} autoComplete="username" maxLength={32} autoCapitalize="none" spellCheck={false} />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码。' }, { min: 12, max: 128, message: '密码长度为12–128个字符。' }]} extra={register ? '至少12个字符，建议使用不在其他网站使用的长密码。' : undefined}>
            <Input.Password size="large" prefix={<LockOutlined />} placeholder={register ? '设置至少12个字符的密码' : '请输入密码'} autoComplete={register ? 'new-password' : 'current-password'} maxLength={128} />
          </Form.Item>
          {register && <Form.Item name="confirm" label="再次输入密码" dependencies={['password']} rules={[{ required: true, message: '请再次输入密码。' }, ({ getFieldValue }) => ({ validator(_, value) { return !value || value === getFieldValue('password') ? Promise.resolve() : Promise.reject(new Error('两次输入的密码不一致。')) } })]}>
            <Input.Password size="large" prefix={<LockOutlined />} placeholder="确认刚才设置的密码" autoComplete="new-password" maxLength={128} />
          </Form.Item>}
          <Button aria-label={register ? "注册并进入工作台" : "登录工作台"} type="primary" htmlType="submit" size="large" block loading={busy} icon={<ArrowRightOutlined />} iconPlacement="end">{register ? '注册并进入工作台' : '登录工作台'}</Button>
        </Form>
        <p className="auth-switch">{register ? '已经有账号？' : '第一次使用？'} <Link to={`${register ? '/login' : '/register'}${location.search}`}>{register ? '返回登录' : '创建账号'}</Link></p>
        <div className="auth-note"><LockOutlined /><span>每个账号独立管理自己的项目与数据。</span></div>
        <details className="auth-support"><summary>账号使用帮助</summary><p>使用用户名登录，无需填写邮箱。请妥善保存用户名和密码；目前不提供邮箱找回，忘记密码请联系网站维护者。旧演示项目需由维护者核对后迁入指定账号。</p></details>
      </div>
      <footer className="auth-entry-footer">数据有边界，结论有依据。</footer>
    </section>
  </main>
}

export function AccountMenu() {
  const { user, accept } = useAccount()
  const { message, modal } = App.useApp()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const logout = () => modal.confirm({ title: '退出当前账号？', content: '未保存的填写内容将不会保留，已保存的项目和报告不受影响。', okText: '退出登录', cancelText: '继续使用', onOk: async () => {
    try { await request('/auth/logout', { method: 'POST', body: '{}' }); accept(null); navigate('/login', { replace: true }) }
    catch (e) { void message.error(e instanceof Error ? e.message : '退出失败，请重试。'); throw e }
  } })
  const change = async (values: { current_password: string; new_password: string }) => {
    setBusy(true); setError('')
    try { const result = await request<{ user: User }>('/auth/password', { method: 'POST', body: JSON.stringify({ current_password: values.current_password, new_password: values.new_password }) }); accept(result.user); setOpen(false); form.resetFields(); void message.success('密码已更新，其他登录会话已退出。') }
    catch (e) { setError(e instanceof Error ? e.message : '修改失败，请重试。') }
    finally { setBusy(false) }
  }
  return <div className="account-menu">
    <Dropdown trigger={['click']} menu={{ items: [{ key: 'password', icon: <LockOutlined />, label: '修改密码' }, { type: 'divider' }, { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' }], onClick: ({ key }) => { if (key === 'logout') logout(); else { setError(''); setOpen(true) } } }}>
      <Button type="text" aria-label={`账号菜单：${user?.username}`}><Avatar size={26} className="account-avatar" icon={<UserOutlined />} /><span className="account-name">{user?.username}</span></Button>
    </Dropdown>
    <Modal title="修改密码" open={open} onCancel={() => { if (!busy) { setOpen(false); form.resetFields() } }} footer={null} maskClosable={!busy} closable={!busy} keyboard={!busy}>
      <p>保存后，其他浏览器中的登录会话将失效。</p>
      {error && <Alert type="error" title={error} role="alert" />}
      <Form form={form} layout="vertical" onFinish={change} requiredMark={false} disabled={busy}>
        <Form.Item name="current_password" label="当前密码" rules={[{ required: true, message: '请输入当前密码。' }]}><Input.Password autoComplete="current-password" /></Form.Item>
        <Form.Item name="new_password" label="新密码" rules={[{ required: true, min: 12, max: 128, message: '请设置12–128个字符的新密码。' }]}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
        <Form.Item name="confirm" label="确认新密码" dependencies={['new_password']} rules={[{ required: true, message: '请再次输入新密码。' }, ({ getFieldValue }) => ({ validator(_, v) { return v === getFieldValue('new_password') ? Promise.resolve() : Promise.reject(new Error('两次输入的密码不一致。')) } })]}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>保存新密码</Button>
      </Form>
    </Modal>
  </div>
}
