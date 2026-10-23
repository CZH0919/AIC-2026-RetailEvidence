import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { Application } from './App'
import './styles.css'
import './analysis.css'
import './retail.css'
import './auth.css'
import './help.css'
import './product-theme.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode><ConfigProvider locale={zhCN} theme={{
    token: {
      colorPrimary: '#087f73', colorText: '#24372f', colorTextSecondary: '#596b66',
      colorLink: '#087f73', colorLinkHover: '#075f51',
      colorBorder: '#dce5df', colorBgLayout: '#f6f8f5', borderRadius: 8,
      fontFamily: '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
      fontSize: 14, controlHeight: 40, controlHeightLG: 46,
      boxShadow: '0 10px 32px rgba(24, 43, 55, 0.08)',
    },
    components: { Button: { primaryShadow: 'none' }, Modal: { borderRadiusLG: 12 } },
  }}><App><Application /></App></ConfigProvider></StrictMode>,
)
