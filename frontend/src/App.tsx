import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react'

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
  message: string
  active_at?: string | null
}

type HeatOverview = {
  active_alarms?: Alarm[]
  live_values?: Array<{
    tag_name: string
    engineering_unit?: string | null
    value_double?: number | null
  }>
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
  { icon: 'dashboard', label: 'نمای کلی' },
  { icon: 'heat', label: 'ردیابی ذوب', badge: 'H-4082' },
  { icon: 'bolt', label: 'کوره قوس الکتریکی (EAF)' },
  { icon: 'ladle', label: 'کوره پاتیلی (LF)' },
  { icon: 'cast', label: 'ریخته‌گری مداوم (CCM)' },
  { icon: 'inventory', label: 'مواد اولیه و شارژ' },
  { icon: 'history', label: 'بایگانی داده (Historian)' },
  { icon: 'chart', label: 'گزارش‌ها و تحلیل' },
  { icon: 'alarm', label: 'مدیریت هشدارها', badge: '۳' },
  { icon: 'link', label: 'ارتباطات L1 / L3' },
  { icon: 'settings', label: 'تنظیمات سیستم' },
]

function getInitialTheme(): Theme {
  const stored = localStorage.getItem('level2-theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function ThemeToggle({ theme, onChange }: { theme: Theme; onChange: () => void }) {
  return (
    <button className="icon-button theme-toggle" type="button" onClick={onChange} aria-label="تغییر حالت نمایش" title="تغییر حالت روشن و تاریک">
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  )
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? 'brand-compact' : ''}`}>
      <span className="logo-frame"><img src="/mianeh-steel-logo.png" alt="لوگوی مجتمع فولاد میانه" /></span>
      <span className="brand-copy"><strong>مجتمع فولاد میانه</strong><small>سامانه سطح ۲ فولادسازی</small></span>
    </div>
  )
}

function LoginPage({ theme, onThemeChange, onLogin }: { theme: Theme; onThemeChange: () => void; onLogin: () => void }) {
  const [employeeId, setEmployeeId] = useState('OP-4109')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [formError, setFormError] = useState('')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!employeeId.trim() || !password.trim()) {
      setFormError('کد کاربری و رمز عبور را وارد کنید.')
      return
    }
    setFormError('')
    onLogin()
  }

  return (
    <main className="login-page">
      <header className="login-header">
        <Brand compact />
        <div className="login-header-actions">
          <span className="shift-chip"><Icon name="clock" size={16} /> شیفت ب · صبح‌کار</span>
          <span className="date-chip">۱۴۰۵/۰۶/۱۶ · ۱۱:۴۰</span>
          <button className="language-button active" type="button">FA</button>
          <button className="language-button" type="button">EN</button>
          <ThemeToggle theme={theme} onChange={onThemeChange} />
        </div>
      </header>

      <section className="login-stage">
        <div className="metallurgy-visual" aria-hidden="true">
          <div className="visual-kicker">METALLURGICAL STATUS FEED</div>
          <h1>پایش، ردیابی و بهینه‌سازی<br />فرایند تولید</h1>
          <div className="ladle-illustration">
            <span className="temperature-readout">۱۶۲۸٫۴ <small>°C</small></span>
            <div className="ladle-glow" />
            <div className="ladle-vessel"><span /></div>
          </div>
          <div className="visual-stats">
            <div><span>فشار آرگون</span><strong>240.8 <small>Nm³/h</small></strong><em>STABLE PURGE</em></div>
            <div><span>توان ترانسفورماتور</span><strong>84.2 <small>MW</small></strong><em>ARC ON</em></div>
            <div><span>شماره ذوب جاری</span><strong>H-4082</strong><em>3SP-MOD</em></div>
          </div>
        </div>

        <div className="login-panel">
          <div className="panel-brand"><Brand /></div>
          <div className="login-title-row">
            <div><span className="section-kicker">احراز هویت کنسول متالورژی</span><h2>ورود به کنسول عملیات</h2></div>
            <span className="terminal-id">WS-CR-04</span>
          </div>
          <form onSubmit={submit} noValidate>
            <label className="form-label" htmlFor="workstation">ایستگاه کاری / زون متالورژی</label>
            <select id="workstation" defaultValue="CCR-1">
              <option value="CCR-1">کنترل روم مرکزی کارگاه ذوب ۱ (CCR-1)</option>
              <option value="EAF-01">کوره قوس الکتریکی شماره ۱ (EAF-01)</option>
              <option value="LF-01">کوره پاتیلی و تصفیه ثانویه (LF-01)</option>
              <option value="CCM-02">ماشین ریخته‌گری پیوسته (CCM-02)</option>
            </select>

            <label className="form-label" htmlFor="employee-id">کد کاربری / شماره پرسنلی</label>
            <div className="input-with-icon"><Icon name="user" /><input id="employee-id" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} autoComplete="username" /></div>

            <div className="label-row"><label className="form-label" htmlFor="password">رمز عبور امنیتی</label><button type="button" className="text-button">بازیابی گذرواژه</button></div>
            <div className="input-with-icon"><Icon name="settings" /><input id="password" type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" placeholder="رمز عبور" /><button type="button" className="show-password" onClick={() => setShowPassword((value) => !value)}>{showPassword ? 'پنهان' : 'نمایش'}</button></div>

            <label className="remember-row"><input type="checkbox" defaultChecked /><span>به‌خاطرسپاری این ایستگاه کاری</span><small>TLS 1.3 / L2 ENCRYPT</small></label>
            {formError && <p className="form-error" role="alert">{formError}</p>}
            <button className="login-button" type="submit"><Icon name="logout" /> ورود به کنسول عملیات</button>
          </form>
          <div className="support-row"><span>پشتیبانی فنی شیفت: داخلی ۴۲۱۸</span><span>نسخه ۲.۸.۴</span></div>
        </div>
      </section>

      <section className="diagnostics" aria-label="وضعیت زیرساخت اتوماسیون">
        <div className="diagnostics-heading"><div><span className="status-dot online" /><strong>وضعیت برخط زیرساخت اتوماسیون</strong></div><span>HEARTBEAT: ALL ACTIVE</span></div>
        <div className="diagnostic-grid">
          <article><span className="diag-icon"><Icon name="link" /></span><div><small>اتصال سطح ۱ (PLC / SCADA)</small><strong>L1 BUS · 4 ms</strong><em>Profinet پایدار</em></div></article>
          <article><span className="diag-icon"><Icon name="history" /></span><div><small>پایگاه داده وقایع</small><strong>Historian L2</strong><em>12.4k tags/sec</em></div></article>
          <article><span className="diag-icon"><Icon name="chart" /></span><div><small>یکپارچه‌سازی سطح ۳</small><strong>MES / ERP · Active</strong><em>دستور تولید همگام</em></div></article>
        </div>
      </section>
    </main>
  )
}

function MiniTrend() {
  return (
    <svg className="trend-chart" viewBox="0 0 760 230" preserveAspectRatio="none" role="img" aria-label="نمودار روند زنده پارامترهای فرایند">
      <g className="chart-grid"><path d="M0 30H760M0 80H760M0 130H760M0 180H760"/><path d="M120 0V210M280 0V210M440 0V210M600 0V210"/></g>
      <path className="trend-line temperature" d="M0 176 C70 168 95 122 160 130 S260 155 320 104 S430 78 480 96 S575 42 650 68 S720 40 760 36" />
      <path className="trend-line power" d="M0 192 C75 178 110 184 170 158 S280 120 335 142 S435 160 505 122 S620 108 680 126 S730 112 760 116" />
      <path className="trend-line argon" d="M0 160 C90 154 120 170 205 164 S310 138 380 150 S490 146 555 132 S665 150 760 128" />
      <circle className="chart-now" cx="760" cy="36" r="5" />
    </svg>
  )
}

function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = { LF: 'تصفیه نهایی', CASTING: 'در حال ریخته‌گری', COMPLETED: 'تکمیل شده', EAF: 'در حال ذوب', TAPPING: 'تخلیه', CHARGING: 'شارژ' }
  return <span className={`status-badge status-${status.toLowerCase()}`}>{labels[status] ?? status}</span>
}

function Dashboard({ theme, onThemeChange, onLogout }: { theme: Theme; onThemeChange: () => void; onLogout: () => void }) {
  const [heats, setHeats] = useState<Heat[]>([])
  const [overview, setOverview] = useState<HeatOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetch('/api/v1/meta').then((response) => {
        if (!response.ok) throw new Error('Metadata API unavailable')
        return response.json() as Promise<ApiMeta>
      }),
      fetch('/api/v1/heats?limit=12').then((response) => {
        if (!response.ok) throw new Error('Heat API unavailable')
        return response.json() as Promise<Heat[]>
      }),
    ])
      .then(([, heatResponse]) => {
        if (cancelled) return
        setHeats(heatResponse)
        const active = heatResponse.find((heat) => !['COMPLETED', 'ABORTED', 'CANCELLED'].includes(heat.status))
        if (active) {
          fetch(`/api/v1/heats/${encodeURIComponent(active.heat_no)}/overview`)
            .then((response) => response.ok ? response.json() : null)
            .then((value: HeatOverview | null) => { if (!cancelled) setOverview(value) })
            .catch(() => undefined)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('ارتباط با API برقرار نیست؛ داده‌های نمایشی آخرین همگام‌سازی نمایش داده می‌شود.')
          setHeats(demoHeats)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const activeHeat = useMemo(() => heats.find((heat) => !['COMPLETED', 'ABORTED', 'CANCELLED'].includes(heat.status)) ?? heats[0], [heats])
  const alarms = overview?.active_alarms ?? []

  return (
    <div className="dashboard-shell">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand"><Brand /></div>
        <div className="link-health"><span className="status-dot online" /><span><strong>L1 / L2 LINK: ACTIVE</strong><small>2.1 ms · REALTIME</small></span></div>
        <nav className="side-nav" aria-label="ناوبری سامانه">
          {navItems.map((item, index) => <button className={index === 0 ? 'active' : ''} type="button" key={item.label}><Icon name={item.icon} /><span>{item.label}</span>{item.badge && <em>{item.badge}</em>}</button>)}
        </nav>
        <div className="sidebar-footer"><button type="button"><Icon name="settings" /> پشتیبانی فنی شیفت</button><button type="button" onClick={onLogout}><Icon name="logout" /> خروج از سامانه</button></div>
      </aside>
      {sidebarOpen && <button className="sidebar-scrim" type="button" onClick={() => setSidebarOpen(false)} aria-label="بستن منو" />}

      <main className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="dashboard-context">
            <button className="mobile-menu icon-button" type="button" onClick={() => setSidebarOpen((value) => !value)} aria-label="نمایش منو"><Icon name="menu" /></button>
            <span className="plant-mark">M</span>
            <span><strong>کارگاه ذوب شماره ۱</strong><small>شیفت ب · صبح‌کار</small></span>
          </div>
          <div className="topbar-actions">
            <span className="live-chip"><span className="status-dot online" /> پخش زنده تله‌متری <b>LIVE</b></span>
            <label className="search-box"><Icon name="search" /><input placeholder="جستجوی ذوب، گرید یا پاتیل..." /></label>
            <ThemeToggle theme={theme} onChange={onThemeChange} />
            <button className="icon-button notification-button" type="button" aria-label="هشدارها"><Icon name="bell" /><i>3</i></button>
            <button className="language-button active" type="button">FA</button>
            <div className="operator"><span><strong>مهندس احمدی</strong><small>سرپرست متالورژی L2</small></span><span className="operator-avatar"><Icon name="user" /></span></div>
          </div>
        </header>

        <div className="dashboard-content">
          <div className="page-heading">
            <div><span className="section-kicker">LEVEL 2 OPERATIONS</span><h1>نمای کلی عملیات فولادسازی</h1><p>پایش یکپارچه مسیر تولید از کوره قوس تا ریخته‌گری مداوم</p></div>
            <div className="update-state"><span className={`status-dot ${error ? 'warning' : 'online'}`} /><span><strong>{error ? 'حالت داده نمایشی' : 'همگام با Level 1'}</strong><small>آخرین بروزرسانی: همین حالا</small></span></div>
          </div>

          {error && <div className="api-notice"><Icon name="alarm" /><span>{error}</span></div>}

          <section className="kpi-grid" aria-label="شاخص‌های کلیدی فرایند">
            <article className="kpi-card accent-orange"><div className="kpi-icon"><Icon name="heat" /></div><span>ذوب فعال جاری</span><strong>{loading ? '…' : `#${activeHeat?.heat_no ?? '—'}`}</strong><small>گرید: {activeHeat?.grade_code ?? '—'} <b>T+42 min</b></small></article>
            <article className="kpi-card accent-cyan"><div className="kpi-icon"><Icon name="ladle" /></div><span>ایستگاه متالورژی فعال</span><strong>{activeHeat?.status ?? 'LF-1'}</strong><small>آلیاژسازی دقیق <b>RUNNING</b></small></article>
            <article className="kpi-card accent-amber"><div className="kpi-icon"><Icon name="clock" /></div><span>زمان چرخه Tap-to-Tap</span><strong>۵۴ <i>دقیقه</i></strong><small>هدف: ۵۲ min <b>+2 min</b></small></article>
            <article className="kpi-card accent-cyan"><div className="kpi-icon"><Icon name="temperature" /></div><span>دمای حمام مذاب</span><strong>۱٬۶۲۴ <i>°C</i></strong><small>بازه مطلوب ۱۶۱۵–۱۶۳۰ <b>مطلوب</b></small></article>
            <article className="kpi-card accent-blue"><div className="kpi-icon"><Icon name="energy" /></div><span>مصرف ویژه انرژی</span><strong>۳۹۸ <i>kWh/t</i></strong><small>میانگین شیفت <b>−3.4%</b></small></article>
            <article className="kpi-card accent-red"><div className="kpi-icon"><Icon name="yield" /></div><span>راندمان و هشدارها</span><strong>۹۶٫۸ <i>%</i></strong><small>{Math.max(alarms.length, 3)} هشدار فعال <b>۱ بحرانی</b></small></article>
          </section>

          <section className="panel process-panel">
            <div className="panel-heading"><div><span className="section-kicker">HEAT TRACKING TIMELINE</span><h2>خط پیوسته فرایند ذوب و تولید شمش</h2></div><span className="sync-badge"><Icon name="check" /> توالی همگام · +۴ دقیقه</span></div>
            <div className="process-flow">
              <article className="process-card"><div className="process-card-top"><span className="stage-number">۰۱</span><span className="equipment-icon"><Icon name="bolt" /></span><StatusBadge status="EAF" /></div><h3>کوره قوس الکتریکی</h3><code>EAF-1 · NEXT #H-4083</code><dl><div><dt>مرحله جاری</dt><dd>شارژ سبد دوم قراضه</dd></div><div><dt>توان اکتیو</dt><dd>82.4 MW</dd></div></dl><div className="progress"><span style={{ width: '65%' }} /></div><small>پیشرفت ذوب ۶۵٪ · تخلیه ۱۴:۴۸</small></article>
              <span className="flow-arrow"><Icon name="arrow" /></span>
              <article className="process-card current"><div className="process-card-top"><span className="stage-number">۰۲</span><span className="equipment-icon"><Icon name="ladle" /></span><StatusBadge status="LF" /></div><h3>کوره پاتیلی</h3><code>LF-1 · HEAT #H-4082</code><dl><div><dt>دمای مذاب</dt><dd>1624 °C</dd></div><div><dt>دمش آرگون</dt><dd>برقرار</dd></div></dl><div className="progress"><span style={{ width: '85%' }} /></div><small>تکمیل متالورژی ۸۵٪ · آماده CCM در ۷ دقیقه</small></article>
              <span className="flow-arrow"><Icon name="arrow" /></span>
              <article className="process-card"><div className="process-card-top"><span className="stage-number">۰۳</span><span className="equipment-icon"><Icon name="cast" /></span><StatusBadge status="CASTING" /></div><h3>ریخته‌گری مداوم</h3><code>CCM-2 · CASTING #H-4081</code><dl><div><dt>سرعت کشش</dt><dd>1.45 m/min</dd></div><div><dt>تناژ تاندیش</dt><dd>24.2 t</dd></div></dl><div className="progress"><span style={{ width: '52%' }} /></div><small>پاتیل ۳ از ۶ · چهار خط فعال</small></article>
            </div>
          </section>

          <div className="dashboard-grid">
            <section className="panel trend-panel">
              <div className="panel-heading"><div><span className="section-kicker">REALTIME TREND · 60 MIN</span><h2>پارامترهای آنلاین ذوب {activeHeat?.heat_no ?? 'H-4082'}</h2></div><button className="outline-button" type="button">زوم ۱ ساعت</button></div>
              <div className="chart-legend"><span className="temperature">دمای مذاب (°C)</span><span className="power">توان الکتریکی (MW)</span><span className="argon">دمش آرگون (Nm³/h)</span></div>
              <MiniTrend />
              <div className="chart-axis"><span>۱۳:۲۰</span><span>۱۳:۳۵</span><span>۱۳:۵۰</span><span>۱۴:۰۵</span><span>۱۴:۲۲ · NOW</span></div>
              <div className="live-metrics"><div><small>دمای حمام مذاب</small><strong>1,624.8 °C</strong><em>+12°C / 10min</em></div><div><small>فشار گاز آرگون</small><strong>6.4 bar</strong><em>180 Nl/min</em></div><div><small>کربن معادل</small><strong>0.182%</strong><em>O₂: 24 ppm</em></div><div><small>عمر نسوز پاتیل</small><strong>42 ذوب</strong><em>مطلوب</em></div></div>
            </section>

            <section className="panel alarm-panel">
              <div className="panel-heading"><div><span className="section-kicker">ACTIVE ALARMS</span><h2>هشدارهای فرایندی</h2></div><span className="alarm-count">۳ فعال</span></div>
              <div className="alarm-list">
                <article className="alarm-item critical"><div className="alarm-title"><span><Icon name="alarm" /> بحرانی · EAF-1</span><time>۱۴:۱۹:۳۲</time></div><strong>افزایش دمای پانل خنک‌کننده سقف</strong><p>اختلاف دمای رفت و برگشت آبگرد بیشتر از ۱۸°C است.</p><button type="button">تأیید هشدار (ACK)</button></article>
                <article className="alarm-item warning"><div className="alarm-title"><span><Icon name="alarm" /> هشدار · LF-1</span><time>۱۴:۰۵:۱۱</time></div><strong>انحراف نسبت بازیسیته سرباره</strong><p>نسبت CaO/SiO₂ برابر 2.45؛ حداقل مجاز 2.8.</p><button type="button">بررسی دستور شارژ</button></article>
                <article className="alarm-item info"><div className="alarm-title"><span><Icon name="check" /> رویداد · CCM</span><time>۱۳:۵۸:۰۴</time></div><strong>استقرار پاتیل جدید توالی ذوب</strong><p>پاتیل H-4081 با موفقیت روی تارت گردان مستقر شد.</p></article>
              </div>
            </section>
          </div>

          <section className="panel heats-panel">
            <div className="panel-heading"><div><span className="section-kicker">PRODUCTION RECORD</span><h2>کارنامه متالورژیکی ذوب‌های اخیر</h2></div><button className="outline-button" type="button">مشاهده آرشیو</button></div>
            <div className="table-wrap"><table><thead><tr><th>شماره ذوب</th><th>گرید فولاد</th><th>مسیر تولید</th><th>وزن واقعی</th><th>دمای تخلیه</th><th>وضعیت کیفی</th></tr></thead><tbody>{heats.slice(0, 6).map((heat) => <tr key={heat.heat_no}><td className="heat-no">#{heat.heat_no}</td><td>{heat.grade_code ?? '—'}</td><td><code>EAF1 › LF1 › CCM2</code></td><td>{heat.actual_weight_t ?? heat.planned_weight_t ?? '—'} t</td><td>{heat.status === 'COMPLETED' ? '۱۶۳۲' : '۱۶۲۴'} °C</td><td><StatusBadge status={heat.status} /></td></tr>)}</tbody></table></div>
            <div className="table-summary"><span>مجموع تناژ شیفت: <strong>۵۲۰٫۶ تن</strong></span><span>میانگین انحراف دما: <strong>±۳٫۲°C</strong></span><span>ذوب‌های پاس‌شده: <strong>۹ پاتیل</strong></span></div>
          </section>
        </div>
      </main>
    </div>
  )
}

function App() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  const [view, setView] = useState<View>('login')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('level2-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((value) => value === 'dark' ? 'light' : 'dark')

  return view === 'login'
    ? <LoginPage theme={theme} onThemeChange={toggleTheme} onLogin={() => setView('dashboard')} />
    : <Dashboard theme={theme} onThemeChange={toggleTheme} onLogout={() => setView('login')} />
}

export default App
