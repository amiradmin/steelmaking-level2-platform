import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { LicenseNotice } from './LicenseNotice'
import { MaterialsNavigationBridge } from './MaterialsNavigationBridge'
import './styles.css'
import './production-flow-tooltip-fix.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LicenseNotice>
      <MaterialsNavigationBridge />
      <App />
    </LicenseNotice>
  </React.StrictMode>,
)
