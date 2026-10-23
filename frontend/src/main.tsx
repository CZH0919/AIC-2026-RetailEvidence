import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { Application } from './App'
import './styles.css'
import './help.css'
import './analysis.css'
import './retail.css'
import './commercial-ui.css'
import './auth.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode><ConfigProvider locale={zhCN} theme={{
    token: {
      colorPrimary: '#087f73', colorLink: '#087f73', colorLinkHover: '#06665d',
      colorText: '#1f2933', colorTextSecondary: '#53616f',
      colorBorder: '#dde2e5', colorBgLayout: '#f5f6f7', borderRadius: 6,
      fontFamily: '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
      fontSize: 14, controlHeight: 40, controlHeightLG: 46,
      boxShadow: '0 6px 20px rgba(31, 41, 51, 0.1)',
    },
    components: { Button: { primaryShadow: 'none' }, Modal: { borderRadiusLG: 12 } },
  }}><App><Application /></App></ConfigProvider></StrictMode>,
)
