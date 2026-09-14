import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './alarm-management.css'

type Alarm = {
  alarm_code: string
  source_system?: string | null
  equipment_code?: string | null
  heat_no?: string | null
  severity: string
  state: string
  message: string
  active_at?: string | null
  cleared_at?: string | null
  acknowledged_at?: string | null
  acknowledged_by?: string | null
  payload?: unknown
}

type ViewMode = 'active' | 'acknowledged' | 'cleared' | 'all'
type SeverityFilter = 'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'WARNING' | 'LOW' | 'INFO'
type AreaFilter = 'ALL' | 'EAF' | 'LF' | 'CCM' | 'OTHER'

const ACTIVE_STATES = new Set(['ACTIVE_UNACKNOWLEDGED', 'ACTIVE_ACKNOWLEDGED'])

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatAge(value?: string | null): string {
  if (!value) return '—'
  const start = new Date(value).getTime()
  if (!Number.isFinite(start)) return '—'
  const seconds = Math.max(0, Math.floor((Date.now() - start) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m`
  const days = Math.floor(hours / 24)
  return `${days}d ${hours % 24}h`
}

function areaOf(alarm: Alarm): AreaFilter {
  const code = String(alarm.equipment_code ?? '').toUpperCase()
  if (code.startsWith('EAF')) return 'EAF'
  if (code.startsWith('LF')) return 'LF'
  if (code.startsWith('CCM')) return 'CCM'
  return 'OTHER'
}

function severityClass(severity: string): string {
  const normalized = severity.toUpperCase()
  if (normalized === 'CRITICAL' || normalized === 'HIGH') return 'critical'
  if (normalized === 'MEDIUM' || normalized === 'WARNING') return 'warning'
  return 'info'
}

function stateLabel(state: string): string {
  return state.split('_').join(' ')
}

function payloadText(payload: unknown): string {
  if (payload === null || payload === undefined) return '—'
  if (typeof payload === 'string') return payload
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return String(payload)
  }
}

export function AlarmManagement() {
  const [alarms, setAlarms] = useState<Alarm[]>([])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [mode, setMode] = useState<ViewMode>('active')
  const [severity, setSeverity] = useState<SeverityFilter>('ALL')
  const [area, setArea] = useState<AreaFilter>('ALL')
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [, setTick] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const refresh = async () => {
      try {
        const response = await authorizedFetch('/api/v1/alarms?limit=1000')
        if (!response.ok) throw new Error(`Alarm API returned ${response.status}`)
        const payload = await response.json() as Alarm[]
        if (cancelled) return
        setAlarms(payload)
        setError(null)
        setLastRefresh(new Date())
        setSelectedKey((current) => {
          if (current && payload.some((alarm) => `${alarm.alarm_code}|${alarm.active_at ?? ''}` === current)) return current
          const firstActive = payload.find((alarm) => ACTIVE_STATES.has(alarm.state)) ?? payload[0]
          return firstActive ? `${firstActive.alarm_code}|${firstActive.active_at ?? ''}` : null
        })
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Alarm data unavailable')
      } finally {
        if (!cancelled) {
          setLoading(false)
          timer = window.setTimeout(() => { void refresh() }, 5000)
        }
      }
    }

    void refresh()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [])

  const counts = useMemo(() => {
    const active = alarms.filter((alarm) => ACTIVE_STATES.has(alarm.state))
    return {
      total: alarms.length,
      active: active.length,
      unack: active.filter((alarm) => alarm.state === 'ACTIVE_UNACKNOWLEDGED').length,
      ack: active.filter((alarm) => alarm.state === 'ACTIVE_ACKNOWLEDGED').length,
      critical: active.filter((alarm) => ['CRITICAL', 'HIGH'].includes(alarm.severity.toUpperCase())).length,
      cleared: alarms.filter((alarm) => !ACTIVE_STATES.has(alarm.state)).length,
    }
  }, [alarms])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return alarms.filter((alarm) => {
      if (mode === 'active' && !ACTIVE_STATES.has(alarm.state)) return false
      if (mode === 'acknowledged' && alarm.state !== 'ACTIVE_ACKNOWLEDGED') return false
      if (mode === 'cleared' && ACTIVE_STATES.has(alarm.state)) return false
      if (severity !== 'ALL' && alarm.severity.toUpperCase() !== severity) return false
      if (area !== 'ALL' && areaOf(alarm) !== area) return false
      if (needle) {
        const haystack = [alarm.alarm_code, alarm.message, alarm.equipment_code, alarm.heat_no, alarm.source_system]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        if (!haystack.includes(needle)) return false
      }
      return true
    })
  }, [alarms, mode, severity, area, search])

  const selected = useMemo(() => {
    if (!selectedKey) return filtered[0] ?? null
    return alarms.find((alarm) => `${alarm.alarm_code}|${alarm.active_at ?? ''}` === selectedKey) ?? filtered[0] ?? null
  }, [alarms, filtered, selectedKey])

  const areaStats = useMemo(() => {
    const active = alarms.filter((alarm) => ACTIVE_STATES.has(alarm.state))
    return (['EAF', 'LF', 'CCM', 'OTHER'] as AreaFilter[]).map((name) => ({
      name,
      count: active.filter((alarm) => areaOf(alarm) === name).length,
    }))
  }, [alarms])

  return (
    <section className="alarm-management-page">
      <header className="alarm-management-heading">
        <div>
          <span className="section-kicker">ALARM & EVENT OPERATIONS</span>
          <h1>Alarm Management</h1>
          <p>Live Level 2 alarm supervision across EAF, LF and CCM. This screen is read-only; acknowledgement state shown here is sourced from the alarm database.</p>
        </div>
        <div className={`alarm-stream-health ${error ? 'warning' : 'online'}`}>
          <span className="alarm-stream-dot" />
          <span><strong>{error ? 'ALARM STREAM DEGRADED' : 'ALARM STREAM LIVE'}</strong><small>{lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : 'Waiting for first refresh'} · 5 s poll</small></span>
        </div>
      </header>

      {error && <div className="alarm-management-notice"><strong>Alarm API:</strong> {error}. Last valid alarm list remains visible.</div>}

      <section className="alarm-summary-grid">
        <article className="active"><span>Active Alarms</span><strong>{counts.active}</strong><small>{counts.unack} unacknowledged</small></article>
        <article className="critical"><span>Critical / High</span><strong>{counts.critical}</strong><small>Active safety/process priority</small></article>
        <article className="ack"><span>Acknowledged Active</span><strong>{counts.ack}</strong><small>Still active in process</small></article>
        <article><span>Historical / Cleared</span><strong>{counts.cleared}</strong><small>{counts.total} records loaded</small></article>
      </section>

      <section className="alarm-area-strip" aria-label="Active alarms by plant area">
        {areaStats.map((item) => <button type="button" key={item.name} className={area === item.name ? 'selected' : ''} onClick={() => setArea(item.name)}><span>{item.name}</span><strong>{item.count}</strong><small>ACTIVE</small></button>)}
        <button type="button" className={area === 'ALL' ? 'selected' : ''} onClick={() => setArea('ALL')}><span>ALL AREAS</span><strong>{counts.active}</strong><small>ACTIVE</small></button>
      </section>

      <section className="alarm-toolbar">
        <div className="alarm-mode-tabs">
          <button className={mode === 'active' ? 'active' : ''} type="button" onClick={() => setMode('active')}>Active</button>
          <button className={mode === 'acknowledged' ? 'active' : ''} type="button" onClick={() => setMode('acknowledged')}>Acknowledged</button>
          <button className={mode === 'cleared' ? 'active' : ''} type="button" onClick={() => setMode('cleared')}>Historical</button>
          <button className={mode === 'all' ? 'active' : ''} type="button" onClick={() => setMode('all')}>All</button>
        </div>
        <div className="alarm-filter-controls">
          <input aria-label="Search alarms" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search code, message, heat…" />
          <select aria-label="Severity filter" value={severity} onChange={(event) => setSeverity(event.target.value as SeverityFilter)}>
            <option value="ALL">All severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="WARNING">Warning</option>
            <option value="LOW">Low</option>
            <option value="INFO">Info</option>
          </select>
          <button type="button" onClick={() => { setSearch(''); setSeverity('ALL'); setArea('ALL') }}>Reset</button>
        </div>
      </section>

      <div className="alarm-main-grid">
        <section className="alarm-list-panel">
          <div className="alarm-panel-title"><div><span className="section-kicker">ALARM QUEUE</span><h2>{filtered.length} matching records</h2></div><span>{loading ? 'LOADING…' : 'AUTO REFRESH'}</span></div>
          <div className="alarm-record-list">
            {filtered.map((alarm) => {
              const key = `${alarm.alarm_code}|${alarm.active_at ?? ''}`
              const tone = severityClass(alarm.severity)
              const isSelected = selected && `${selected.alarm_code}|${selected.active_at ?? ''}` === key
              return (
                <button type="button" className={`alarm-record ${tone} ${isSelected ? 'selected' : ''}`} key={key} onClick={() => setSelectedKey(key)}>
                  <span className="alarm-record-indicator" />
                  <span className="alarm-record-copy">
                    <span className="alarm-record-meta"><b>{alarm.severity.toUpperCase()}</b><code>{alarm.alarm_code}</code><em>{areaOf(alarm)}</em></span>
                    <strong>{alarm.message}</strong>
                    <small>{alarm.equipment_code ?? 'UNASSIGNED'} · Heat {alarm.heat_no ?? '—'} · {stateLabel(alarm.state)}</small>
                  </span>
                  <span className="alarm-record-time"><time>{formatDateTime(alarm.active_at)}</time><small>{formatAge(alarm.active_at)}</small></span>
                </button>
              )
            })}
            {!loading && filtered.length === 0 && <div className="alarm-empty-state"><strong>No alarms match the current filters.</strong><small>Change the state, severity, area or search filter.</small></div>}
          </div>
        </section>

        <aside className="alarm-detail-panel">
          <div className="alarm-panel-title"><div><span className="section-kicker">ALARM DETAILS</span><h2>{selected?.alarm_code ?? 'No selection'}</h2></div>{selected && <span className={`alarm-detail-severity ${severityClass(selected.severity)}`}>{selected.severity.toUpperCase()}</span>}</div>
          {selected ? <>
            <div className="alarm-detail-message"><span>MESSAGE</span><strong>{selected.message}</strong></div>
            <dl className="alarm-detail-grid">
              <div><dt>State</dt><dd>{stateLabel(selected.state)}</dd></div>
              <div><dt>Area</dt><dd>{areaOf(selected)}</dd></div>
              <div><dt>Equipment</dt><dd>{selected.equipment_code ?? '—'}</dd></div>
              <div><dt>Heat</dt><dd>{selected.heat_no ?? '—'}</dd></div>
              <div><dt>Source</dt><dd>{selected.source_system ?? '—'}</dd></div>
              <div><dt>Active for</dt><dd>{formatAge(selected.active_at)}</dd></div>
              <div><dt>Activated</dt><dd>{formatDateTime(selected.active_at)}</dd></div>
              <div><dt>Cleared</dt><dd>{formatDateTime(selected.cleared_at)}</dd></div>
              <div><dt>Acknowledged</dt><dd>{formatDateTime(selected.acknowledged_at)}</dd></div>
              <div><dt>Acknowledged by</dt><dd>{selected.acknowledged_by ?? '—'}</dd></div>
            </dl>
            <div className="alarm-lifecycle">
              <div className="alarm-lifecycle-step done"><i>1</i><span><strong>Activated</strong><small>{formatDateTime(selected.active_at)}</small></span></div>
              <div className={`alarm-lifecycle-step ${selected.acknowledged_at ? 'done' : ACTIVE_STATES.has(selected.state) ? 'current' : ''}`}><i>2</i><span><strong>Acknowledged</strong><small>{selected.acknowledged_at ? `${formatDateTime(selected.acknowledged_at)} · ${selected.acknowledged_by ?? 'operator'}` : 'Not acknowledged'}</small></span></div>
              <div className={`alarm-lifecycle-step ${selected.cleared_at ? 'done' : !ACTIVE_STATES.has(selected.state) ? 'done' : 'current'}`}><i>3</i><span><strong>Cleared</strong><small>{selected.cleared_at ? formatDateTime(selected.cleared_at) : 'Alarm remains active'}</small></span></div>
            </div>
            <div className="alarm-payload"><span>RAW PAYLOAD</span><pre>{payloadText(selected.payload)}</pre></div>
            <div className="alarm-readonly-note">READ ONLY · Alarm acknowledgement and clearing are not issued from this Level 2 monitoring screen.</div>
          </> : <div className="alarm-empty-state"><strong>Select an alarm.</strong><small>Details, lifecycle and raw payload will appear here.</small></div>}
        </aside>
      </div>
    </section>
  )
}
