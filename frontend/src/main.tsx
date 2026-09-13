import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { LicenseNotice } from './LicenseNotice'
import { PlcSourceOverlay } from './PlcSourceOverlay'
import { SystemMapTelemetryOverlay } from './SystemMapTelemetryOverlay'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LicenseNotice>
      <App />
      <PlcSourceOverlay />
      <SystemMapTelemetryOverlay />
    </LicenseNotice>
  </React.StrictMode>,
)
