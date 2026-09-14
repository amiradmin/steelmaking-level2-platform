import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './eaf-dashboard.css'
import './lf-dashboard.css'

type Heat = {
  heat_no: string
  status: string
  grade_code?: string | null
  started_at?: string | null
}

type Value = {
  tag_name: string
  source_system?: string | null
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
}

type TrendSample = {
  tag_name: string
  engineering_unit?: string | null
  ts: string
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
}

type Event = {
  event_type: string
  source_system?: string | null
  severity?: string | null
  occurred_at?: string | null
  heat_no?: string | null
}

type Alarm = {
  alarm_code: string
  severity: string
  message?: string | null
  active_at?: string | null
}

type Snapshot = {
  generated_at: string
  active_heat?: Heat | null
  values: Value[]
  trends: TrendSample[]
  events: Event[]
  alarms: Alarm[]
  mode: string
}

const STAGES = ['LADLE_RECEIVED', 'HEATING', 'ALLOYING', 'STIRRING', 'SAMPLE', 'READY_TO_CAST']
const STAGE_BY_CODE: Record<number, string> = {
  1: 'LADLE_RECEIVED',
  2: 'HEATING',
  3: 'ALLOYING',
  4: 'STIRRING',
  5: 'SAMPLE',
  6: 'READY_TO_CAST',
}

const BOOLEAN_TAGS = [
  ['LF.Ready', 'Ready'],
  ['LF.Running', 'Running'],
  ['LF.Fault', 'Fault'],
  ['LF.ArcOn', 'Arc'],
  ['LF.ArgonOn', 'Argon'],
  ['LF.RoofClosed', 'Roof closed'],
  ['LF.CoolingWaterOK', 'Cooling water'],
  ['LF.ArgonPressureOK', 'Argon pressure'],
  ['LF.TransformerReady', 'Transformer'],
  ['LF.InterlockOK', 'Interlock'],
] as const

function fmtClock(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtNumber(value?: number | null, digits = 1): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function raw(value?: Value): string {
  if (!value) return '—'
  if (typeof value.value_double === 'number') return fmtNumber(value.value_double, 2)
  return value.value_text ?? '—'
}

function withUnit(value?: Value, digits = 1): string {
  if (!value) return '—'
  const rendered = typeof value.value_double === 'number' ? fmtNumber(value.value_double, digits) : value.value_text ?? '—'
  return rendered === '—' ? rendered : `${rendered}${value.engineering_unit ? ` ${value.engineering_unit}` : ''}`
}

function bool(value?: Value): boolean | null {
  if (!value) return null
  if (typeof value.value_double === 'number') return value.value_double !== 0
  const normalized = String(value.value_text ?? '').trim().toLowerCase()
  if (['true', '1', 'on', 'yes', 'ok', 'ready', 'running'].includes(normalized)) return true
  if (['false', '0', 'off', 'no', 'bad'].includes(normalized)) return false
  return null
}

function age(value?: string | null): number | null {
  if (!value) return null
  const ts = new Date(value).getTime()
  return Number.isFinite(ts) ? Math.max(0, (Date.now() - ts) / 1000) : null
}

function elapsed(value?: string | null): string {
  if (!value) return '—'
  const start = new Date(value).getTime()
  if (!Number.isFinite(start)) return '—'
  const total = Math.max(0, Math.floor((Date.now() - start) / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h > 0 ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function displayStage(value: string): string {
  return value.split('_').join(' ')
}

function Sparkline({ samples }: { samples: TrendSample[] }) {
  const numeric = samples.filter((sample) => typeof sample.value_double === 'number').map((sample) => sample.value_double as number)
  if (numeric.length < 2) return <div className="eaf-no-trend">Waiting for historian samples…</div>
  const min = Math.min(...numeric)
  const max = Math.max(...numeric)
  const range = Math.max(max - min, 0.0001)
  const points = numeric.map((value, index) => `${((index / (numeric.length - 1)) * 100).toFixed(2)},${(34 - ((value - min) / range) * 28).toFixed(2)}`).join(' ')
  return <svg className="eaf-sparkline" viewBox="0 0 100 38" preserveAspectRatio="none" aria-hidden="true"><path d="M0 8H100M0 19H100M0 30H100" className="eaf-spark-grid"/><polyline points={points} className="eaf-spark-line"/></svg>
}

export function LfDashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
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
        const response = await authorizedFetch('/api/v1/lf/dashboard')
        if (!response.ok) throw new Error(`LF dashboard returned ${response.status}`)
        const payload = await response.json() as Snapshot
        if (!cancelled) { setSnapshot(payload); setError(null) }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'LF dashboard unavailable')
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refresh() }, 2000)
      }
    }
    void refresh()
    return () => { cancelled = true; if (timer !== null) window.clearTimeout(timer) }
  }, [])

  const values = useMemo(() => new Map(snapshot?.values.map((value) => [value.tag_name, value]) ?? []), [snapshot])
  const trends = useMemo(() => {
    const result = new Map<string, TrendSample[]>()
    for (const sample of snapshot?.trends ?? []) result.set(sample.tag_name, [...(result.get(sample.tag_name) ?? []), sample])
    return result
  }, [snapshot])

  const get = (tag: string) => values.get(tag)
  const stageCode = get('LF.StageCode')?.value_double ?? Number(get('LF.StageCode')?.value_text ?? NaN)
  const stageName = Number.isFinite(stageCode) ? STAGE_BY_CODE[Number(stageCode)] ?? 'IDLE' : 'IDLE'
  const stageIndex = STAGES.indexOf(stageName)
  const running = bool(get('LF.Running'))
  const fault = bool(get('LF.Fault'))
  const ready = bool(get('LF.Ready'))
  const interlock = bool(get('LF.InterlockOK'))
  const latestTs = snapshot?.values.map((value) => value.ts).filter((value): value is string => Boolean(value)).sort().at(-1)
  const sampleAge = age(latestTs)
  const healthy = !error && fault !== true && sampleAge !== null && sampleAge < 10
  const heatNumber = raw(get('LF.HeatNumber')) !== '—' ? raw(get('LF.HeatNumber')) : snapshot?.active_heat?.heat_no ?? '—'

  const trendCards = [
    ['LF.SteelTemperature', 'Steel Temperature'],
    ['LF.ArgonFlow', 'Argon Flow'],
    ['LF.PowerMW', 'Electrical Power'],
    ['LF.CurrentKA', 'Arc Current'],
  ] as const

  return (
    <section className="eaf-page lf-page">
      <header className="eaf-heading">
        <div><span className="section-kicker">SECONDARY METALLURGY · LIVE OPERATIONS</span><h1>Ladle Furnace · LF-01</h1><p>Live read-only refining view from PLC telemetry and Timescale historian.</p></div>
        <div className={`eaf-health ${healthy ? 'online' : 'warning'}`}><span className="eaf-health-dot"/><span><strong>{error ? 'DATA RETRYING' : healthy ? 'LIVE LF TELEMETRY' : 'TELEMETRY DEGRADED'}</strong><small>{sampleAge === null ? 'No recent sample' : `${sampleAge.toFixed(1)} s sample age`} · {snapshot?.mode ?? 'READ ONLY'}</small></span></div>
      </header>

      {error && <div className="eaf-notice"><strong>LF Dashboard:</strong> {error}. Last valid snapshot remains visible.</div>}

      <section className="eaf-state-strip">
        <div><span>HEAT</span><strong>{heatNumber}</strong><small>{snapshot?.active_heat?.grade_code ?? 'Grade —'}</small></div>
        <div><span>PROCESS STAGE</span><strong className="accent">{displayStage(stageName)}</strong><small>{running === true ? 'RUNNING' : 'STANDBY'}</small></div>
        <div><span>ELAPSED</span><strong>{elapsed(snapshot?.active_heat?.started_at)}</strong><small>Heat start</small></div>
        <div><span>READY</span><strong className={ready ? 'ok' : 'bad'}>{ready === null ? '—' : ready ? 'YES' : 'NO'}</strong><small>LF.Ready</small></div>
        <div><span>INTERLOCK</span><strong className={interlock ? 'ok' : 'bad'}>{interlock === null ? '—' : interlock ? 'OK' : 'NOT OK'}</strong><small>LF.InterlockOK</small></div>
        <div><span>FAULT</span><strong className={fault ? 'bad' : 'ok'}>{fault === null ? '—' : fault ? 'ACTIVE' : 'CLEAR'}</strong><small>Alarm code {raw(get('LF.AlarmCode'))}</small></div>
      </section>

      <section className="eaf-kpi-grid">
        <article><span>Steel Temperature</span><strong>{withUnit(get('LF.SteelTemperature'), 1)}</strong><small>LF.SteelTemperature</small></article>
        <article><span>Argon Flow</span><strong>{withUnit(get('LF.ArgonFlow'), 1)}</strong><small>LF.ArgonFlow</small></article>
        <article><span>Electrical Power</span><strong>{withUnit(get('LF.PowerMW'), 1)}</strong><small>LF.PowerMW</small></article>
        <article><span>Arc Current</span><strong>{withUnit(get('LF.CurrentKA'), 1)}</strong><small>LF.CurrentKA</small></article>
        <article><span>Electrode Position</span><strong>{withUnit(get('LF.ElectrodePositionPercent'), 1)}</strong><small>LF.ElectrodePositionPercent</small></article>
        <article><span>Cooling Water</span><strong>{withUnit(get('LF.CoolingWaterFlowM3h'), 1)}</strong><small>LF.CoolingWaterFlowM3h</small></article>
        <article><span>Ladle Weight</span><strong>{withUnit(get('LF.LadleWeightTon'), 1)}</strong><small>LF.LadleWeightTon</small></article>
        <article><span>PLC Cycle Time</span><strong>{withUnit(get('LF.PLC.CycleTimeMs'), 2)}</strong><small>LF.PLC.CycleTimeMs</small></article>
      </section>

      <div className="eaf-main-grid">
        <section className="eaf-panel eaf-process-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">REFINING PROCESS</span><h2>Ladle Treatment Sequence</h2></div><span className={`eaf-mode-chip ${running ? 'live' : ''}`}>{running ? 'PROCESS ACTIVE' : 'STANDBY'}</span></div>
          <div className="eaf-process-body">
            <div className="lf-vessel-scene" aria-hidden="true">
              <div className="lf-electrodes"><i/><i/><i/></div>
              <div className="lf-roof"/>
              <div className="lf-vessel"><div className="lf-steel"/></div>
              <div className={`lf-arcs ${bool(get('LF.ArcOn')) ? 'on' : ''}`}><i/><i/><i/></div>
              <div className={`lf-argon ${bool(get('LF.ArgonOn')) ? 'on' : ''}`}><i/><i/><i/><i/></div>
              <span className="lf-ladle-weight">{withUnit(get('LF.LadleWeightTon'), 1)}</span>
              <span className="lf-temperature">{withUnit(get('LF.SteelTemperature'), 0)}</span>
            </div>
            <div className="eaf-stage-sequence">
              {STAGES.map((stage, index) => {
                const state = stageIndex < 0 ? 'pending' : index < stageIndex ? 'done' : index === stageIndex ? 'active' : 'pending'
                return <div className={`eaf-stage-step ${state}`} key={stage}><i>{index + 1}</i><span><strong>{displayStage(stage)}</strong><small>{state === 'active' ? 'CURRENT SUB-PROCESS' : state.toUpperCase()}</small></span></div>
              })}
            </div>
          </div>
          <div className="eaf-actuator-strip">
            <span className={bool(get('LF.ArcOn')) ? 'on' : ''}>ARC <b>{bool(get('LF.ArcOn')) ? 'ON' : 'OFF'}</b></span>
            <span className={bool(get('LF.ArgonOn')) ? 'on' : ''}>ARGON <b>{bool(get('LF.ArgonOn')) ? 'ON' : 'OFF'}</b></span>
            <span>ROOF <b>{bool(get('LF.RoofClosed')) === null ? '—' : bool(get('LF.RoofClosed')) ? 'CLOSED' : 'OPEN'}</b></span>
            <span>COOLING <b>{bool(get('LF.CoolingWaterOK')) ? 'OK' : 'NOT OK'}</b></span>
            <span>ARGON P <b>{bool(get('LF.ArgonPressureOK')) ? 'OK' : 'LOW'}</b></span>
          </div>
        </section>

        <section className="eaf-panel eaf-interlock-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">SAFETY STATUS</span><h2>Interlocks & Permissives</h2></div><span>{BOOLEAN_TAGS.length} signals</span></div>
          <div className="eaf-interlock-list">
            {BOOLEAN_TAGS.map(([tag, label]) => {
              const state = bool(get(tag)); const good = state === null ? null : tag === 'LF.Fault' ? !state : state
              return <div className="eaf-interlock-row" key={tag}><span className={`eaf-state-light ${good === null ? 'unknown' : good ? 'good' : 'bad'}`}/><span><strong>{label}</strong><small>{tag}</small></span><b>{state === null ? '—' : state ? 'TRUE' : 'FALSE'}</b></div>
            })}
          </div>
        </section>
      </div>

      <section className="eaf-panel eaf-trends-panel">
        <div className="eaf-panel-heading"><div><span className="section-kicker">TIMESCALE HISTORIAN · LAST 60 MIN</span><h2>Live Refining Trends</h2></div><span>{snapshot?.trends.length ?? 0} samples loaded</span></div>
        <div className="eaf-trend-grid">{trendCards.map(([tag, label]) => <article className="eaf-trend-card" key={tag}><div><span>{label}</span><strong>{withUnit(get(tag), 1)}</strong><small>{get(tag)?.quality ?? 'NO DATA'}</small></div><Sparkline samples={trends.get(tag) ?? []}/></article>)}</div>
      </section>

      <div className="eaf-bottom-grid">
        <section className="eaf-panel"><div className="eaf-panel-heading"><div><span className="section-kicker">LF EVENTS</span><h2>Recent Process Events</h2></div><span>{snapshot?.events.length ?? 0}</span></div><div className="eaf-event-list">{(snapshot?.events ?? []).length === 0 ? <div className="eaf-empty">No LF events recorded.</div> : snapshot?.events.slice(0, 10).map((event, index) => <div className="eaf-event-row" key={`${event.event_type}-${event.occurred_at ?? index}`}><time>{fmtClock(event.occurred_at)}</time><span><strong>{event.event_type}</strong><small>{event.source_system ?? 'LEVEL 2'} · {event.heat_no ?? 'NO HEAT'} · {event.severity ?? 'INFO'}</small></span></div>)}</div></section>
        <section className="eaf-panel"><div className="eaf-panel-heading"><div><span className="section-kicker">ACTIVE ALARMS</span><h2>LF Alarm State</h2></div><span>{snapshot?.alarms.length ?? 0}</span></div><div className="eaf-alarm-list">{(snapshot?.alarms ?? []).length === 0 ? <div className="eaf-good-state">No active LF alarms</div> : snapshot?.alarms.slice(0, 8).map((alarm) => <div className={`eaf-alarm-row sev-${alarm.severity.toLowerCase()}`} key={`${alarm.alarm_code}-${alarm.active_at ?? ''}`}><div><strong>{alarm.alarm_code}</strong><small>{alarm.message ?? 'No alarm message'}</small></div><span><b>{alarm.severity}</b><time>{fmtClock(alarm.active_at)}</time></span></div>)}</div></section>
      </div>

      <section className="eaf-panel eaf-raw-panel">
        <div className="eaf-panel-heading"><div><span className="section-kicker">RAW LEVEL 2 VALUES</span><h2>LF Tag Inspector</h2></div><span>{snapshot?.values.length ?? 0} current tags</span></div>
        <div className="eaf-raw-table-wrap"><table className="eaf-raw-table"><thead><tr><th>Tag</th><th>Value</th><th>Unit</th><th>Quality</th><th>Source</th><th>Timestamp</th></tr></thead><tbody>{(snapshot?.values ?? []).map((value) => <tr key={value.tag_name}><td><code>{value.tag_name}</code></td><td>{raw(value)}</td><td>{value.engineering_unit ?? '—'}</td><td><span className={`eaf-quality ${(value.quality ?? 'unknown').toLowerCase()}`}>{value.quality ?? 'UNKNOWN'}</span></td><td>{value.source_system ?? '—'}</td><td>{fmtClock(value.ts)}</td></tr>)}</tbody></table></div>
      </section>
    </section>
  )
}
