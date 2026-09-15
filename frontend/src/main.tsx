import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { LicenseNotice } from './LicenseNotice'
import { MaterialsNavigationBridge } from './MaterialsNavigationBridge'
import { ReportsNavigationBridge } from './ReportsNavigationBridge'
import { AboutNavigationBridge } from './AboutNavigationBridge'
import './styles.css'
import './production-flow-tooltip-fix.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LicenseNotice>
      <MaterialsNavigationBridge />
      <ReportsNavigationBridge />
      <AboutNavigationBridge />
      <App />
    </LicenseNotice>
  </React.StrictMode>,
)
