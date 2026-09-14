import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './eaf-dashboard.css'

type Heat = {
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  started_at?: string | null
  updated_at?: string | null
}

type EafValue = {
  tag_name: string
  source_system?: string | null
  source_tag?: string | null
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
  heat_no?: string | null
}

type TrendSample = {
  tag_name: string
  engineering_unit?: string | null
  ts: string
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
}

type EafEvent = {
  event_type: string
  source_system?: string | null
  area?: string | null
  equipment_code?: string | null
  severity?: string | null
  occurred_at?: string | null
  payload?: Record<string, unknown> | null
  heat_no?: string | null
}

type EafAlarm = {
  alarm_code: string
  severity: string
  state: string
  message?: string | null
  active_at?: string | null
  cleared_at?: string | null
  equipment_code?: string | null
  heat_no?: string | null
}

type Equipment = {
  code: string
  name: string
  area: string
  equipment_type: string
}

type EafSnapshot = {
  generated_at: string
  equipment?: Equipment | null
  active_heat?: Heat | null
  values: EafValue[]
  trends: TrendSample[]
  events: EafEvent[]
  alarms: EafAlarm[]
  mode: string
}

const EAF_STAGES = ['CHARGE', 'MELTING', 'REFINING', 'SUPERHEAT', 'TAPPING']
const STAGE_BY_CODE: Record<number, string> = {
  1: 'CHARGE',
  2: 'MELTING',
  3: 'REFINING',
  4: 'SUPERHEAT',
  5: 'TAPPING',
}

const BOOL_TAGS = [
  ['EAF.Ready', 'Ready'],
  ['EAF.Running', 'Running'],
  ['EAF.Fault', 'Fault'],
  ['EAF.ArcOn', 'Arc'],
  ['EAF.OxygenOn', 'Oxygen'],
  ['EAF.BurnerOn', 'Burner'],
  ['EAF.RoofClosed', 'Roof closed'],
  ['EAF.DoorClosed', 'Door closed'],
  ['EAF.HydraulicOK', 'Hydraulic'],
  ['EAF.CoolingWaterOK', 'Cooling water'],
  ['EAF.TransformerReady', 'Transformer'],
  ['EAF.InterlockOK', 'Interlock'],
] as const

function fmtClock(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function elapsed(value?: string | null): string {
  if (!value) return '—'
  const start = new Date(value).getTime()
  if (!Number.isFinite(start)) return '—'
  const seconds = Math.max(0, Math.floor((Date.now() - start) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return hours > 0
    ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

function ageSeconds(value?: string | null): number | null {
  if (!value) return null
  const parsed = new Date(value).getTime()
  if (!Number.isFinite(parsed)) return null
  return Math.max(0, (Date.now() - parsed) / 1000)
}

function fmtNumber(value?: number | null, digits = 1): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function rawValue(value?: EafValue): string {
  if (!value) return '—'
  if (typeof value.value_double === 'number') return fmtNumber(value.value_double, 2)
  if (value.value_text !== null && value.value_text !== undefined && value.value_text !== '') return value.value_text
  return '—'
}

function withUnit(value?: EafValue, digits = 1): string {
  if (!value) return '—'
  const rendered = typeof value.value_double === 'number'
    ? fmtNumber(value.value_double, digits)
    : value.value_text ?? '—'
  if (rendered === '—') return rendered
  return `${rendered}${value.engineering_unit ? ` ${value.engineering_unit}` : ''}`
}

function truthy(value?: EafValue): boolean | null {
  if (!value) return null
  if (typeof value.value_double === 'number') return value.value_double !== 0
  const normalized = String(value.value_text ?? '').trim().toLowerCase()
  if (['true', '1', 'on', 'yes', 'ok', 'ready', 'running'].includes(normalized)) return true
  if (['false', '0', 'off', 'no', 'fault', 'bad'].includes(normalized)) return false
  return null
}

function Sparkline({ samples }: { samples: TrendSample[] }) {
  const numeric = samples
    .filter((sample) => typeof sample.value_double === 'number' && Number.isFinite(sample.value_double))
    .map((sample) => sample.value_double as number)
  if (numeric.length < 2) return <div className="eaf-no-trend">Waiting for historian samples…</div>

  const min = Math.min(...numeric)
  const max = Math.max(...numeric)
  const range = Math.max(max - min, 0.0001)
  const points = numeric.map((value, index) => {
    const x = numeric.length === 1 ? 0 : (index / (numeric.length - 1)) * 100
    const y = 34 - ((value - min) / range) * 28
    return `${x.toFixed(2)},${y.toFixed(2)}`
  }).join(' ')

  return (
    <svg className="eaf-sparkline" viewBox="0 0 100 38" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 8H100M0 19H100M0 30H100" className="eaf-spark-grid" />
      <polyline points={points} className="eaf-spark-line" />
    </svg>
  )
}

export function EafDashboard() {
  const [snapshot, setSnapshot] = useState<EafSnapshot | null>(null)
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
        const response = await authorizedFetch('/api/v1/eaf/dashboard')
        if (!response.ok) throw new Error(`EAF dashboard returned ${response.status}`)
        const payload = await response.json() as EafSnapshot
        if (!cancelled) {
          setSnapshot(payload)
          setError(null)
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'EAF dashboard unavailable')
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refresh() }, 2000)
      }
    }

    void refresh()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [])

  const valueMap = useMemo(() => new Map(snapshot?.values.map((value) => [value.tag_name, value]) ?? []), [snapshot])
  const trendMap = useMemo(() => {
    const map = new Map<string, TrendSample[]>()
    for (const sample of snapshot?.trends ?? []) {
      const values = map.get(sample.tag_name) ?? []
      values.push(sample)
      map.set(sample.tag_name, values)
    }
    return map
  }, [snapshot])

  const get = (tag: string) => valueMap.get(tag)
  const stageCode = get('EAF.StageCode')?.value_double ?? Number(get('EAF.StageCode')?.value_text ?? NaN)
  const explicitStage = get('EAF.StageName')?.value_text?.trim().toUpperCase()
  const stageName = explicitStage || (Number.isFinite(stageCode) ? STAGE_BY_CODE[Number(stageCode)] : undefined) || 'IDLE'
  const stageIndex = EAF_STAGES.indexOf(stageName)
  const running = truthy(get('EAF.Running'))
  const fault = truthy(get('EAF.Fault'))
  const ready = truthy(get('EAF.Ready'))
  const interlock = truthy(get('EAF.InterlockOK'))
  const latestTs = snapshot?.values.map((value) => value.ts).filter((value): value is string => Boolean(value)).sort().at(-1)
  const sampleAge = ageSeconds(latestTs)
  const healthy = !error && fault !== true && sampleAge !== null && sampleAge < 10
  const heatNumber = rawValue(get('EAF.HeatNumber')) !== '—'
    ? rawValue(get('EAF.HeatNumber'))
    : snapshot?.active_heat?.heat_no ?? '—'

  const trendCards = [
    ['EAF.PowerMW', 'Electrical Power', 'MW'],
    ['EAF.CurrentKA', 'Arc Current', 'kA'],
    ['EAF.SteelTemperature', 'Steel Temperature', '°C'],
    ['EAF.OxygenFlow', 'Oxygen Flow', 'Nm³/h'],
  ] as const

  return (
    <section className="eaf-page">
      <header className="eaf-heading">
        <div>
          <span className="section-kicker">PRIMARY STEELMAKING · LIVE OPERATIONS</span>
          <h1>Electric Arc Furnace · EAF-01</h1>
          <p>Read-only Level 2 operating view sourced from PLC telemetry and the Timescale historian.</p>
        </div>
        <div className={`eaf-health ${healthy ? 'online' : 'warning'}`}>
          <span className="eaf-health-dot" />
          <span><strong>{error ? 'DATA RETRYING' : healthy ? 'LIVE EAF TELEMETRY' : 'TELEMETRY DEGRADED'}</strong><small>{sampleAge === null ? 'No recent sample' : `${sampleAge.toFixed(1)} s sample age`} · {snapshot?.mode ?? 'READ ONLY'}</small></span>
        </div>
      </header>

      {error && <div className="eaf-notice"><strong>EAF Dashboard:</strong> {error}. Last valid operating snapshot remains visible.</div>}

      <section className="eaf-state-strip">
        <div><span>HEAT</span><strong>{heatNumber}</strong><small>{snapshot?.active_heat?.grade_code ?? 'Grade —'}</small></div>
        <div><span>PROCESS STAGE</span><strong className="accent">{stageName}</strong><small>{running === true ? 'RUNNING' : running === false ? 'NOT RUNNING' : 'STATE UNKNOWN'}</small></div>
        <div><span>ELAPSED</span><strong>{elapsed(snapshot?.active_heat?.started_at)}</strong><small>Heat start</small></div>
        <div><span>READY</span><strong className={ready === true ? 'ok' : ready === false ? 'bad' : ''}>{ready === null ? '—' : ready ? 'YES' : 'NO'}</strong><small>EAF.Ready</small></div>
        <div><span>INTERLOCK</span><strong className={interlock === true ? 'ok' : interlock === false ? 'bad' : ''}>{interlock === null ? '—' : interlock ? 'OK' : 'NOT OK'}</strong><small>EAF.InterlockOK</small></div>
        <div><span>FAULT</span><strong className={fault === true ? 'bad' : fault === false ? 'ok' : ''}>{fault === null ? '—' : fault ? 'ACTIVE' : 'CLEAR'}</strong><small>Alarm code {rawValue(get('EAF.AlarmCode'))}</small></div>
      </section>

      <section className="eaf-kpi-grid">
        <article><span>Electrical Power</span><strong>{withUnit(get('EAF.PowerMW'), 1)}</strong><small>EAF.PowerMW</small></article>
        <article><span>Arc Current</span><strong>{withUnit(get('EAF.CurrentKA'), 1)}</strong><small>EAF.CurrentKA</small></article>
        <article><span>Steel Temperature</span><strong>{withUnit(get('EAF.SteelTemperature'), 1)}</strong><small>EAF.SteelTemperature</small></article>
        <article><span>Oxygen Flow</span><strong>{withUnit(get('EAF.OxygenFlow'), 0)}</strong><small>EAF.OxygenFlow</small></article>
        <article><span>Electrode Position</span><strong>{withUnit(get('EAF.ElectrodePositionPercent'), 1)}</strong><small>EAF.ElectrodePositionPercent</small></article>
        <article><span>Cooling Water</span><strong>{withUnit(get('EAF.CoolingWaterFlowM3h'), 1)}</strong><small>EAF.CoolingWaterFlowM3h</small></article>
        <article><span>Transformer Tap</span><strong>{rawValue(get('EAF.TransformerTap'))}</strong><small>EAF.TransformerTap</small></article>
        <article><span>PLC Cycle Time</span><strong>{withUnit(get('EAF.PLC.CycleTimeMs'), 2)}</strong><small>EAF.PLC.CycleTimeMs</small></article>
      </section>

      <div className="eaf-main-grid">
        <section className="eaf-panel eaf-process-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">FURNACE PROCESS</span><h2>Melting Sequence</h2></div><span className={`eaf-mode-chip ${running ? 'live' : ''}`}>{running ? 'PROCESS ACTIVE' : 'STANDBY'}</span></div>
          <div className="eaf-process-body">
            <div className={`eaf-furnace ${truthy(get('EAF.ArcOn')) ? 'arc-on' : ''}`} aria-hidden="true">
              <div className="eaf-electrodes"><i /><i /><i /></div>
              <div className="eaf-roof" />
              <div className="eaf-vessel"><div className="eaf-bath" /></div>
              <div className="eaf-arc"><i /><i /><i /></div>
              <span>{withUnit(get('EAF.SteelTemperature'), 0)}</span>
            </div>
            <div className="eaf-stage-sequence">
              {EAF_STAGES.map((stage, index) => {
                const state = stageIndex < 0 ? 'pending' : index < stageIndex ? 'done' : index === stageIndex ? 'active' : 'pending'
                return <div className={`eaf-stage-step ${state}`} key={stage}><i>{index + 1}</i><span><strong>{stage}</strong><small>{state === 'active' ? 'CURRENT SUB-PROCESS' : state.toUpperCase()}</small></span></div>
              })}
            </div>
          </div>
          <div className="eaf-actuator-strip">
            <span className={truthy(get('EAF.ArcOn')) ? 'on' : ''}>ARC <b>{truthy(get('EAF.ArcOn')) ? 'ON' : 'OFF'}</b></span>
            <span className={truthy(get('EAF.OxygenOn')) ? 'on' : ''}>OXYGEN <b>{truthy(get('EAF.OxygenOn')) ? 'ON' : 'OFF'}</b></span>
            <span className={truthy(get('EAF.BurnerOn')) ? 'on' : ''}>BURNER <b>{truthy(get('EAF.BurnerOn')) ? 'ON' : 'OFF'}</b></span>
            <span>ROOF <b>{truthy(get('EAF.RoofClosed')) === null ? '—' : truthy(get('EAF.RoofClosed')) ? 'CLOSED' : 'OPEN'}</b></span>
            <span>DOOR <b>{truthy(get('EAF.DoorClosed')) === null ? '—' : truthy(get('EAF.DoorClosed')) ? 'CLOSED' : 'OPEN'}</b></span>
          </div>
        </section>

        <section className="eaf-panel eaf-interlock-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">SAFETY STATUS</span><h2>Interlocks & Permissives</h2></div><span>{BOOL_TAGS.length} signals</span></div>
          <div className="eaf-interlock-list">
            {BOOL_TAGS.map(([tag, label]) => {
              const state = truthy(get(tag))
              const isFaultSemantic = tag === 'EAF.Fault'
              const good = state === null ? null : isFaultSemantic ? !state : state
              return <div className="eaf-interlock-row" key={tag}><span className={`eaf-state-light ${good === null ? 'unknown' : good ? 'good' : 'bad'}`} /><span><strong>{label}</strong><small>{tag}</small></span><b>{state === null ? '—' : state ? 'TRUE' : 'FALSE'}</b></div>
            })}
          </div>
        </section>
      </div>

      <section className="eaf-panel eaf-trends-panel">
        <div className="eaf-panel-heading"><div><span className="section-kicker">TIMESCALE HISTORIAN · LAST 60 MIN</span><h2>Live Process Trends</h2></div><span>{snapshot?.trends.length ?? 0} samples loaded</span></div>
        <div className="eaf-trend-grid">
          {trendCards.map(([tag, label, fallbackUnit]) => {
            const samples = trendMap.get(tag) ?? []
            const latest = get(tag)
            return <article className="eaf-trend-card" key={tag}><div><span>{label}</span><strong>{withUnit(latest, tag === 'EAF.OxygenFlow' ? 0 : 1)}</strong><small>{latest?.engineering_unit ?? fallbackUnit} · {latest?.quality ?? 'NO DATA'}</small></div><Sparkline samples={samples} /></article>
          })}
        </div>
      </section>

      <div className="eaf-bottom-grid">
        <section className="eaf-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">EAF EVENTS</span><h2>Recent Process Events</h2></div><span>{snapshot?.events.length ?? 0}</span></div>
          <div className="eaf-event-list">
            {(snapshot?.events ?? []).length === 0 ? <div className="eaf-empty">No EAF events recorded.</div> : snapshot?.events.slice(0, 10).map((event, index) => <div className="eaf-event-row" key={`${event.event_type}-${event.occurred_at ?? index}`}><time>{fmtClock(event.occurred_at)}</time><span><strong>{event.event_type}</strong><small>{event.source_system ?? 'LEVEL 2'} · {event.heat_no ?? 'NO HEAT'} · {event.severity ?? 'INFO'}</small></span></div>)}
          </div>
        </section>

        <section className="eaf-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">ACTIVE ALARMS</span><h2>EAF Alarm State</h2></div><span className={(snapshot?.alarms.length ?? 0) > 0 ? 'eaf-alarm-count' : ''}>{snapshot?.alarms.length ?? 0}</span></div>
          <div className="eaf-alarm-list">
            {(snapshot?.alarms ?? []).length === 0 ? <div className="eaf-good-state">No active EAF alarms</div> : snapshot?.alarms.slice(0, 8).map((alarm) => <div className={`eaf-alarm-row sev-${alarm.severity.toLowerCase()}`} key={`${alarm.alarm_code}-${alarm.active_at ?? ''}`}><div><strong>{alarm.alarm_code}</strong><small>{alarm.message ?? 'No alarm message'}</small></div><span><b>{alarm.severity}</b><time>{fmtClock(alarm.active_at)}</time></span></div>)}
          </div>
        </section>
      </div>

      <section className="eaf-panel eaf-raw-panel">
        <div className="eaf-panel-heading"><div><span className="section-kicker">RAW LEVEL 2 VALUES</span><h2>EAF Tag Inspector</h2></div><span>{snapshot?.values.length ?? 0} current tags</span></div>
        <div className="eaf-raw-table-wrap"><table className="eaf-raw-table"><thead><tr><th>Tag</th><th>Value</th><th>Unit</th><th>Quality</th><th>Source</th><th>Timestamp</th></tr></thead><tbody>{(snapshot?.values ?? []).map((value) => <tr key={value.tag_name}><td><code>{value.tag_name}</code></td><td>{rawValue(value)}</td><td>{value.engineering_unit ?? '—'}</td><td><span className={`eaf-quality ${(value.quality ?? 'unknown').toLowerCase()}`}>{value.quality ?? 'UNKNOWN'}</span></td><td>{value.source_system ?? '—'}</td><td>{fmtClock(value.ts)}</td></tr>)}</tbody></table></div>
      </section>
    </section>
  )
}
