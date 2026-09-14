import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { LicenseNotice } from './LicenseNotice'
import { OverviewLiveOverlay } from './OverviewLiveOverlay'
import { PlcSourceOverlay } from './PlcSourceOverlay'
import { SystemMapTelemetryOverlay } from './SystemMapTelemetryOverlay'
import './styles.css'
import './production-flow-tooltip-placement.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LicenseNotice>
      <App />
      <OverviewLiveOverlay />
      <PlcSourceOverlay />
      <SystemMapTelemetryOverlay />
    </LicenseNotice>
  </React.StrictMode>,
)
