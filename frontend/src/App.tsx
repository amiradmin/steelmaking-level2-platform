import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import { AuthenticationExpiredError, OperatorProfile, authorizedFetch, clearTokens, loadTokens, login } from './auth'
import { TelemetryConnectionStatus, subscribeRealtimeTelemetry } from './telemetry'

type Theme = 'dark' | 'light'
type View = 'login' | 'dashboard'

type Heat = {
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  started_at?: string | null
  updated_at?: string | null
}

type ApiMeta = {
  name: string
  api_version: string
  framework?: string
  process_flow?: string[]
}

type Alarm = {
  alarm_code: string
  severity: string
  state?: string
  message: string
  equipment_code?: string | null
  active_at?: string | null
}

type LiveValue = {
  tag_name: string
  equipment_code?: string | null
  area?: string | null
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
}

type HeatOverview = {
  active_alarms?: Alarm[]
  live_values?: LiveValue[]
}

type IconName =
  | 'dashboard' | 'heat' | 'bolt' | 'ladle' | 'cast' | 'inventory'
  | 'history' | 'chart' | 'alarm' | 'link' | 'settings' | 'search'
  | 'bell' | 'sun' | 'moon' | 'user' | 'clock' | 'temperature'
  | 'energy' | 'yield' | 'menu' | 'arrow' | 'check' | 'logout'

const iconPaths: Record<IconName, ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  heat: <path d="M12 22c4 0 7-2.7 7-6.6 0-3.1-1.7-5.5-4.7-8.5.1 2-1 3.1-2 3.8.1-3.6-2.1-6.3-4.3-8.7.2 3.4-3 6.1-3 9.8C5 17.6 8 22 12 22Z"/>,
  bolt: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z"/>,
  ladle: <><path d="M5 8h12l-1.5 10h-9L5 8Z"/><path d="M17 10h2.5a2.5 2.5 0 0 1 0 5H16M8 5h6"/></>,
  cast: <><path d="M4 5h16v5H4zM7 10v9M12 10v9M17 10v9"/><path d="M5 19h14"/></>,
  inventory: <><path d="m3 7 9 5 9-5-9-5-9 5Z"/><path d="m3 7 9 5v10M21 7l-9 5v10"/></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
  alarm: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
  link: <><path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>,
  moon: <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z"/>,
  user: <><circle cx="12" cy="8" r="4"/><path d="M4 22a8 8 0 0 1 16 0"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  temperature: <><path d="M10 14.8V5a2 2 0 1 1 4 0v9.8a4 4 0 1 1-4 0Z"/><path d="M12 9v8"/></>,
  energy: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z"/>,
  yield: <><path d="M3 20h18M5 17l4-5 4 3 6-9"/><path d="M15 6h4v4"/></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
  arrow: <path d="m9 18 6-6-6-6"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5"/></>,
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{iconPaths[name]}</svg>
}

const demoHeats: Heat[] = [
  { heat_no: 'H-4082', status: 'LF', grade_code: '3SP-Mod', planned_weight_t: 170, actual_weight_t: 168.5 },
  { heat_no: 'H-4081', status: 'CASTING', grade_code: '5SP-ISIRI', planned_weight_t: 170, actual_weight_t: 169.2 },
  { heat_no: 'H-4080', status: 'COMPLETED', grade_code: 'ST52-3 DIN', planned_weight_t: 170, actual_weight_t: 171.1 },
  { heat_no: 'H-4079', status: 'COMPLETED', grade_code: '1008-ASTM', planned_weight_t: 170, actual_weight_t: 168.8 },
]

const navItems: Array<{ icon: IconName; label: string; badge?: string }> = [
  { icon: 'dashboard', label: 'Overview' },
  { icon: 'heat', label: 'Heat Tracking', badge: 'H-4082' },
  { icon: 'bolt', label: 'Electric Arc Furnace (EAF)' },
  { icon: 'ladle', label: 'Ladle Furnace (LF)' },
  { icon: 'cast', label: 'Continuous Casting (CCM)' },
  { icon: 'inventory', label: 'Raw Materials & Charging' },
  { icon: 'history', label: 'Data Historian' },
  { icon: 'chart', label: 'Reports & Analytics' },
  { icon: 'alarm', label: 'Alarm Management', badge: '3' },
  { icon: 'link', label: 'L1 / L3 Communications' },
  { icon: 'settings', label: 'System Settings' },
]

function getInitialTheme(): Theme {
  const stored = localStorage.getItem('level2-theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function formatMetric(value: number | null | undefined, fractionDigits = 1): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

function formatClock(value: string | null): string {
  if (!value) return 'waiting for telemetry'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'just now'
  return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function alarmTone(severity: string): 'critical' | 'warning' | 'info' {
  const normalized = severity.toUpperCase()
  if (normalized === 'CRITICAL' || normalized === 'HIGH') return 'critical'
  if (normalized === 'WARNING' || normalized === 'MEDIUM') return 'warning'
  return 'info'
}

function ThemeToggle({ theme, onChange }: { theme: Theme; onChange: () => void }) {
  return (
    <button className="icon-button theme-toggle" type="button" onClick={onChange} aria-label="Change color theme" title="Toggle light and dark mode">
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  )
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? 'brand-compact' : ''}`}>
      <span className="logo-frame"><img src="/mianeh-steel-logo.png" alt="Mianeh Steel Complex logo" /></span>
      <span className="brand-copy"><strong>Mianeh Steel Complex</strong><small>Level 2 Steelmaking System</small></span>
    </div>
  )
}

function LoginPage({ theme, onThemeChange, onLogin }: { theme: Theme; onThemeChange: () => void; onLogin: (username: string, password: string, remember: boolean) => Promise<void> }) {
  const [employeeId, setEmployeeId] = useState('OP-4109')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [formError, setFormError] = useState('')
  const [remember, setRemember] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!employeeId.trim() || !password.trim()) {
      setFormError('Enter your employee ID and password.')
      return
    }
    setFormError('')
    setSubmitting(true)
    try {
      await onLogin(employeeId.trim(), password, remember)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Unable to sign in to the system.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <header className="login-header">
        <Brand compact />
        <div className="login-header-actions">
          <span className="shift-chip"><Icon name="clock" size={16} /> Shift B · Morning</span>
          <span className="date-chip">Sep 7, 2026 · 11:40</span>
          <ThemeToggle theme={theme} onChange={onThemeChange} />
        </div>
      </header>

      <section className="login-stage">
        <div className="metallurgy-visual" aria-hidden="true">
          <div className="visual-kicker">METALLURGICAL STATUS FEED</div>
          <h1>Monitor, Track, and Optimize<br />the Production Process</h1>
          <div className="ladle-illustration">
            <span className="temperature-readout">1,628.4 <small>°C</small></span>
            <div className="ladle-glow" />
            <div className="ladle-vessel"><span /></div>
          </div>
          <div className="visual-stats">
            <div><span>Argon Flow</span><strong>240.8 <small>Nm³/h</small></strong><em>STABLE PURGE</em></div>
            <div><span>Transformer Power</span><strong>84.2 <small>MW</small></strong><em>ARC ON</em></div>
            <div><span>Current Heat</span><strong>H-4082</strong><em>3SP-MOD</em></div>
          </div>
        </div>

        <div className="login-panel">
          <div className="panel-brand"><Brand /></div>
          <div className="login-title-row">
            <div><span className="section-kicker">METALLURGY CONSOLE AUTHENTICATION</span><h2>Sign in to Operations</h2></div>
            <span className="terminal-id">WS-CR-04</span>
          </div>
          <form onSubmit={submit} noValidate>
            <label className="form-label" htmlFor="workstation">Workstation / Metallurgy Zone</label>
            <select id="workstation" defaultValue="CCR-1">
              <option value="CCR-1">Steelmaking Shop 1 Central Control Room (CCR-1)</option>
              <option value="EAF-01">Electric Arc Furnace No. 1 (EAF-01)</option>
              <option value="LF-01">Ladle Furnace & Secondary Metallurgy (LF-01)</option>
              <option value="CCM-02">Continuous Casting Machine (CCM-02)</option>
            </select>

            <label className="form-label" htmlFor="employee-id">Employee ID / Personnel Number</label>
            <div className="input-with-icon"><Icon name="user" /><input id="employee-id" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} autoComplete="username" /></div>

            <div className="label-row"><label className="form-label" htmlFor="password">Password</label><button type="button" className="text-button">Recover Password</button></div>
            <div className="input-with-icon"><Icon name="settings" /><input id="password" type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" placeholder="Password" /><button type="button" className="show-password" onClick={() => setShowPassword((value) => !value)}>{showPassword ? 'Hide' : 'Show'}</button></div>

            <label className="remember-row"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /><span>Remember this workstation</span><small>TLS 1.3 / JWT</small></label>
            {formError && <p className="form-error" role="alert">{formError}</p>}
            <button className="login-button" type="submit" disabled={submitting}><Icon name="logout" /> {submitting ? 'Authenticating…' : 'Sign in to Operations'}</button>
          </form>
          <div className="support-row"><span>Shift technical support: Ext. 4218</span><span>Version 2.8.4</span></div>
        </div>
      </section>

      <section className="diagnostics" aria-label="Automation infrastructure status">
        <div className="diagnostics-heading"><div><span className="status-dot online" /><strong>Automation Infrastructure Online</strong></div><span>HEARTBEAT: ALL ACTIVE</span></div>
        <div className="diagnostic-grid">
          <article><span className="diag-icon"><Icon name="link" /></span><div><small>Level 1 Connection (PLC / SCADA)</small><strong>L1 BUS · 4 ms</strong><em>PROFINET STABLE</em></div></article>
          <article><span className="diag-icon"><Icon name="history" /></span><div><small>Event Database</small><strong>Historian L2</strong><em>12.4k tags/sec</em></div></article>
          <article><span className="diag-icon"><Icon name="chart" /></span><div><small>Level 3 Integration</small><strong>MES / ERP · Active</strong><em>PRODUCTION ORDER SYNCED</em></div></article>
        </div>
      </section>
    </main>
  )
}

function MiniTrend() {
  return (
    <svg className="trend-chart" viewBox="0 0 760 230" preserveAspectRatio="none" role="img" aria-label="Live process parameter trend chart">
      <g className="chart-grid"><path d="M0 30H760M0 80H760M0 130H760M0 180H760"/><path d="M120 0V210M280 0V210M440 0V210M600 0V210"/></g>
      <path className="trend-line temperature" d="M0 176 C70 168 95 122 160 130 S260 155 320 104 S430 78 480 96 S575 42 650 68 S720 40 760 36" />
      <path className="trend-line power" d="M0 192 C75 178 110 184 170 158 S280 120 335 142 S435 160 505 122 S620 108 680 126 S730 112 760 116" />
      <path className="trend-line argon" d="M0 160 C90 154 120 170 205 164 S310 138 380 150 S490 146 555 132 S665 150 760 128" />
      <circle className="chart-now" cx="760" cy="36" r="5" />
    </svg>
  )
}

function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = { LF: 'Final Refining', CASTING: 'Casting', COMPLETED: 'Completed', EAF: 'Melting', TAPPING: 'Tapping', CHARGING: 'Charging' }
  return <span className={`status-badge status-${status.toLowerCase()}`}>{labels[status] ?? status}</span>
}

function Dashboard({ theme, onThemeChange, onLogout, initialOperator }: { theme: Theme; onThemeChange: () => void; onLogout: () => void; initialOperator: OperatorProfile | null }) {
  const [heats, setHeats] = useState<Heat[]>([])
  const [overview, setOverview] = useState<HeatOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [operator, setOperator] = useState<OperatorProfile | null>(initialOperator)
  const [telemetryStatus, setTelemetryStatus] = useState<TelemetryConnectionStatus>('connecting')
  const [l1LinkOnline, setL1LinkOnline] = useState(false)
  const [l1AgeSeconds, setL1AgeSeconds] = useState<number | null>(null)
  const [lastTelemetryAt, setLastTelemetryAt] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      authorizedFetch('/api/v1/meta').then((response) => {
        if (!response.ok) throw new Error('Metadata API unavailable')
        return response.json() as Promise<ApiMeta>
      }),
      authorizedFetch('/api/v1/heats?limit=12').then((response) => {
        if (!response.ok) throw new Error('Heat API unavailable')
        return response.json() as Promise<Heat[]>
      }),
      authorizedFetch('/api/v1/auth/me').then((response) => {
        if (!response.ok) throw new Error('Operator profile unavailable')
        return response.json() as Promise<OperatorProfile>
      }),
    ])
      .then(([, heatResponse, operatorResponse]) => {
        if (cancelled) return
        setHeats(heatResponse)
        setOperator(operatorResponse)
        const active = heatResponse.find((heat) => !['COMPLETED', 'ABORTED', 'CANCELLED'].includes(heat.status))
        if (active) {
          authorizedFetch(`/api/v1/heats/${encodeURIComponent(active.heat_no)}/overview`)
            .then((response) => response.ok ? response.json() : null)
            .then((value: HeatOverview | null) => { if (!cancelled) setOverview(value) })
            .catch(() => undefined)
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          if (requestError instanceof AuthenticationExpiredError) {
            onLogout()
            return
          }
          setError('The API is unavailable. Showing demo data from the latest synchronization.')
          setHeats(demoHeats)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [onLogout])

  useEffect(() => subscribeRealtimeTelemetry({
    onSnapshot: (snapshot) => {
      setLastTelemetryAt(snapshot.server_time)
      setL1LinkOnline(snapshot.l1_link.online)
      setL1AgeSeconds(snapshot.l1_link.age_seconds)
      setOverview({
        active_alarms: snapshot.active_alarms,
        live_values: snapshot.live_values,
      })
      if (snapshot.active_heat) {
        setHeats((current) => [
          snapshot.active_heat as Heat,
          ...current.filter((heat) => heat.heat_no !== snapshot.active_heat?.heat_no),
        ])
      }
      setError(null)
      setLoading(false)
    },
    onStatus: setTelemetryStatus,
    onAuthenticationExpired: onLogout,
  }), [onLogout])

  const activeHeat = useMemo(() => heats.find((heat) => !['COMPLETED', 'ABORTED', 'CANCELLED'].includes(heat.status)) ?? heats[0], [heats])
  const alarms = overview?.active_alarms ?? []
  const liveValues = overview?.live_values ?? []

  const valueFor = (...tagNames: string[]): number | null => {
    for (const tagName of tagNames) {
      const value = liveValues.find((item) => item.tag_name === tagName)?.value_double
      if (typeof value === 'number' && Number.isFinite(value)) return value
    }
    return null
  }

  const moltenTemperature = activeHeat?.status === 'LF'
    ? valueFor('LF.SteelTemperature', 'EAF.SteelTemperature')
    : activeHeat?.status === 'CASTING'
      ? valueFor('CCM.TundishTemperature', 'LF.SteelTemperature')
      : valueFor('EAF.SteelTemperature', 'LF.SteelTemperature', 'CCM.TundishTemperature')
  const eafPower = valueFor('EAF.PowerMW')
  const argonFlow = valueFor('LF.ArgonFlow')
  const castingSpeed = valueFor('CCM.CastingSpeed')
  const criticalAlarmCount = alarms.filter((alarm) => ['CRITICAL', 'HIGH'].includes(alarm.severity.toUpperCase())).length
  const realtimeHealthy = telemetryStatus === 'live' && l1LinkOnline

  return (
    <div className="dashboard-shell">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand"><Brand /></div>
        <div className="link-health"><span className={`status-dot ${realtimeHealthy ? 'online' : 'warning'}`} /><span><strong>{realtimeHealthy ? 'L1 / L2 LINK: ACTIVE' : 'L1 / L2 LINK: DEGRADED'}</strong><small>{l1AgeSeconds === null ? 'NO RECENT SAMPLE' : `${formatMetric(l1AgeSeconds, 1)} s · REALTIME`}</small></span></div>
        <nav className="side-nav" aria-label="System navigation">
          {navItems.map((item, index) => <button className={index === 0 ? 'active' : ''} type="button" key={item.label}><Icon name={item.icon} /><span>{item.label}</span>{item.badge && <em>{item.badge}</em>}</button>)}
        </nav>
        <div className="sidebar-footer"><button type="button"><Icon name="settings" /> Shift Technical Support</button><button type="button" onClick={onLogout}><Icon name="logout" /> Sign Out</button></div>
      </aside>
      {sidebarOpen && <button className="sidebar-scrim" type="button" onClick={() => setSidebarOpen(false)} aria-label="Close menu" />}

      <main className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="dashboard-context">
            <button className="mobile-menu icon-button" type="button" onClick={() => setSidebarOpen((value) => !value)} aria-label="Open menu"><Icon name="menu" /></button>
            <span className="plant-mark">M</span>
            <span><strong>Steelmaking Shop No. 1</strong><small>Shift B · Morning</small></span>
          </div>
          <div className="topbar-actions">
            <span className="live-chip"><span className={`status-dot ${telemetryStatus === 'live' ? 'online' : 'warning'}`} /> Live Telemetry <b>{telemetryStatus === 'live' ? 'LIVE' : 'RETRY'}</b></span>
            <label className="search-box"><Icon name="search" /><input placeholder="Search heat, grade, or ladle..." /></label>
            <ThemeToggle theme={theme} onChange={onThemeChange} />
            <button className="icon-button notification-button" type="button" aria-label="Notifications"><Icon name="bell" /><i>{alarms.length}</i></button>
            <div className="operator"><span><strong>{operator?.username ?? operator?.display_name ?? 'Level 2 Operator'}</strong><small>Authenticated User</small></span><span className="operator-avatar"><Icon name="user" /></span></div>
          </div>
        </header>

        <div className="dashboard-content">
          <div className="page-heading">
            <div><span className="section-kicker">LEVEL 2 OPERATIONS</span><h1>Steelmaking Operations Overview</h1><p>Integrated production monitoring from the electric arc furnace to continuous casting</p></div>
            <div className="update-state"><span className={`status-dot ${error || !realtimeHealthy ? 'warning' : 'online'}`} /><span><strong>{error ? 'Demo Data Mode' : realtimeHealthy ? 'Synced with Level 1' : 'Realtime Link Degraded'}</strong><small>Last updated: {formatClock(lastTelemetryAt)}</small></span></div>
          </div>

          {error && <div className="api-notice"><Icon name="alarm" /><span>{error}</span></div>}

          <section className="kpi-grid" aria-label="Key process indicators">
            <article className="kpi-card accent-orange"><div className="kpi-icon"><Icon name="heat" /></div><span>Current Active Heat</span><strong>{loading ? '…' : `#${activeHeat?.heat_no ?? '—'}`}</strong><small>Grade: {activeHeat?.grade_code ?? '—'} <b>{activeHeat?.status ?? 'WAITING'}</b></small></article>
            <article className="kpi-card accent-cyan"><div className="kpi-icon"><Icon name="ladle" /></div><span>Active Metallurgy Station</span><strong>{activeHeat?.status ?? '—'}</strong><small>Realtime process state <b>{realtimeHealthy ? 'RUNNING' : 'STALE'}</b></small></article>
            <article className="kpi-card accent-amber"><div className="kpi-icon"><Icon name="clock" /></div><span>Tap-to-Tap Cycle Time</span><strong>54 <i>min</i></strong><small>Target: 52 min <b>+2 min</b></small></article>
            <article className="kpi-card accent-cyan"><div className="kpi-icon"><Icon name="temperature" /></div><span>Molten Bath Temperature</span><strong>{formatMetric(moltenTemperature, 1)} <i>°C</i></strong><small>Historian quality: {liveValues.length ? 'GOOD' : 'NO DATA'} <b>{realtimeHealthy ? 'LIVE' : 'STALE'}</b></small></article>
            <article className="kpi-card accent-blue"><div className="kpi-icon"><Icon name="energy" /></div><span>Specific Energy Consumption</span><strong>398 <i>kWh/t</i></strong><small>Shift average <b>−3.4%</b></small></article>
            <article className="kpi-card accent-red"><div className="kpi-icon"><Icon name="yield" /></div><span>Yield & Alarms</span><strong>96.8 <i>%</i></strong><small>{alarms.length} active alarms <b>{criticalAlarmCount} CRITICAL</b></small></article>
          </section>

          <section className="panel process-panel">
            <div className="panel-heading"><div><span className="section-kicker">HEAT TRACKING TIMELINE</span><h2>Continuous Melting and Billet Production Flow</h2></div><span className="sync-badge"><Icon name="check" /> Historian Stream · {telemetryStatus === 'live' ? 'Connected' : 'Reconnecting'}</span></div>
            <div className="process-flow">
              <article className={`process-card ${activeHeat?.status === 'EAF' ? 'current' : ''}`}><div className="process-card-top"><span className="stage-number">01</span><span className="equipment-icon"><Icon name="bolt" /></span><StatusBadge status="EAF" /></div><h3>Electric Arc Furnace</h3><code>EAF-01 · {activeHeat?.status === 'EAF' ? `HEAT #${activeHeat.heat_no}` : 'STANDBY'}</code><dl><div><dt>Current Stage</dt><dd>{activeHeat?.status === 'EAF' ? 'Melting' : 'Waiting / Previous Stage'}</dd></div><div><dt>Active Power</dt><dd>{formatMetric(eafPower, 1)} MW</dd></div></dl><div className="progress"><span style={{ width: activeHeat?.status === 'EAF' ? '65%' : '20%' }} /></div><small>Value source: EAF.PowerMW historian tag</small></article>
              <span className="flow-arrow"><Icon name="arrow" /></span>
              <article className={`process-card ${activeHeat?.status === 'LF' ? 'current' : ''}`}><div className="process-card-top"><span className="stage-number">02</span><span className="equipment-icon"><Icon name="ladle" /></span><StatusBadge status="LF" /></div><h3>Ladle Furnace</h3><code>LF-01 · {activeHeat?.status === 'LF' ? `HEAT #${activeHeat.heat_no}` : 'STANDBY'}</code><dl><div><dt>Steel Temperature</dt><dd>{formatMetric(valueFor('LF.SteelTemperature'), 1)} °C</dd></div><div><dt>Argon Flow</dt><dd>{formatMetric(argonFlow, 1)} Nm³/h</dd></div></dl><div className="progress"><span style={{ width: activeHeat?.status === 'LF' ? '85%' : '20%' }} /></div><small>Realtime values from LF historian tags</small></article>
              <span className="flow-arrow"><Icon name="arrow" /></span>
              <article className={`process-card ${activeHeat?.status === 'CASTING' ? 'current' : ''}`}><div className="process-card-top"><span className="stage-number">03</span><span className="equipment-icon"><Icon name="cast" /></span><StatusBadge status="CASTING" /></div><h3>Continuous Casting</h3><code>CCM-01 · {activeHeat?.status === 'CASTING' ? `HEAT #${activeHeat.heat_no}` : 'STANDBY'}</code><dl><div><dt>Casting Speed</dt><dd>{formatMetric(castingSpeed, 2)} m/min</dd></div><div><dt>Tundish Temperature</dt><dd>{formatMetric(valueFor('CCM.TundishTemperature'), 1)} °C</dd></div></dl><div className="progress"><span style={{ width: activeHeat?.status === 'CASTING' ? '52%' : '20%' }} /></div><small>Realtime values from CCM historian tags</small></article>
            </div>
          </section>

          <div className="dashboard-grid">
            <section className="panel trend-panel">
              <div className="panel-heading"><div><span className="section-kicker">REALTIME TREND · 60 MIN</span><h2>Live Parameters for Heat {activeHeat?.heat_no ?? '—'}</h2></div><button className="outline-button" type="button">1 Hour Zoom</button></div>
              <div className="chart-legend"><span className="temperature">Steel Temperature (°C)</span><span className="power">Electrical Power (MW)</span><span className="argon">Argon Flow (Nm³/h)</span></div>
              <MiniTrend />
              <div className="chart-axis"><span>−60 min</span><span>−45 min</span><span>−30 min</span><span>−15 min</span><span>NOW</span></div>
              <div className="live-metrics"><div><small>Molten Bath Temperature</small><strong>{formatMetric(moltenTemperature, 1)} °C</strong><em>{realtimeHealthy ? 'LIVE HISTORIAN' : 'STALE'}</em></div><div><small>Argon Gas Flow</small><strong>{formatMetric(argonFlow, 1)} Nm³/h</strong><em>LF.ArgonFlow</em></div><div><small>EAF Electrical Power</small><strong>{formatMetric(eafPower, 1)} MW</strong><em>EAF.PowerMW</em></div><div><small>CCM Casting Speed</small><strong>{formatMetric(castingSpeed, 2)} m/min</strong><em>CCM.CastingSpeed</em></div></div>
            </section>

            <section className="panel alarm-panel">
              <div className="panel-heading"><div><span className="section-kicker">ACTIVE ALARMS</span><h2>Process Alarms</h2></div><span className="alarm-count">{alarms.length} ACTIVE</span></div>
              <div className="alarm-list">
                {alarms.length > 0 ? alarms.slice(0, 4).map((alarm) => (
                  <article className={`alarm-item ${alarmTone(alarm.severity)}`} key={`${alarm.alarm_code}-${alarm.active_at ?? ''}`}>
                    <div className="alarm-title"><span><Icon name="alarm" /> {alarm.severity.toUpperCase()} · {alarm.equipment_code ?? 'L1'}</span><time>{formatClock(alarm.active_at ?? null)}</time></div>
                    <strong>{alarm.message}</strong>
                    <p>{alarm.state ?? 'ACTIVE'} · Source synchronized from the Level 2 alarm table.</p>
                  </article>
                )) : (
                  <article className="alarm-item info"><div className="alarm-title"><span><Icon name="check" /> SYSTEM · LEVEL 2</span><time>{formatClock(lastTelemetryAt)}</time></div><strong>No active process alarms</strong><p>The current heat has no active unacknowledged or acknowledged alarms.</p></article>
                )}
              </div>
            </section>
          </div>

          <section className="panel heats-panel">
            <div className="panel-heading"><div><span className="section-kicker">PRODUCTION RECORD</span><h2>Recent Heat Metallurgical Record</h2></div><button className="outline-button" type="button">View Archive</button></div>
            <div className="table-wrap"><table><thead><tr><th>Heat Number</th><th>Steel Grade</th><th>Production Route</th><th>Actual Weight</th><th>Tap Temperature</th><th>Quality Status</th></tr></thead><tbody>{heats.slice(0, 6).map((heat) => <tr key={heat.heat_no}><td className="heat-no">#{heat.heat_no}</td><td>{heat.grade_code ?? '—'}</td><td><code>EAF1 › LF1 › CCM1</code></td><td>{heat.actual_weight_t ?? heat.planned_weight_t ?? '—'} t</td><td>{heat.heat_no === activeHeat?.heat_no ? formatMetric(moltenTemperature, 1) : heat.status === 'COMPLETED' ? '1632.0' : '—'} °C</td><td><StatusBadge status={heat.status} /></td></tr>)}</tbody></table></div>
            <div className="table-summary"><span>Realtime source: <strong>Timescale Historian</strong></span><span>L1 sample age: <strong>{l1AgeSeconds === null ? '—' : `${formatMetric(l1AgeSeconds, 1)} s`}</strong></span><span>WebSocket: <strong>{telemetryStatus.toUpperCase()}</strong></span></div>
          </section>
        </div>
      </main>
    </div>
  )
}

function App() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  const [view, setView] = useState<View>(() => loadTokens() ? 'dashboard' : 'login')
  const [operator, setOperator] = useState<OperatorProfile | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('level2-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((value) => value === 'dark' ? 'light' : 'dark')

  async function handleLogin(username: string, password: string, remember: boolean) {
    const profile = await login(username, password, remember)
    setOperator(profile)
    setView('dashboard')
  }

  const handleLogout = useCallback(() => {
    clearTokens()
    setOperator(null)
    setView('login')
  }, [])

  return view === 'login'
    ? <LoginPage theme={theme} onThemeChange={toggleTheme} onLogin={handleLogin} />
    : <Dashboard theme={theme} onThemeChange={toggleTheme} onLogout={handleLogout} initialOperator={operator} />
}

export default App
