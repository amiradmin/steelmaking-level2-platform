import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './eaf-dashboard.css'
import './ccm-dashboard.css'

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

const STAGES = ['PREPARE', 'START_CAST', 'STEADY_CAST', 'END_CAST']
const STAGE_BY_CODE: Record<number, string> = {
  1: 'PREPARE',
  2: 'START_CAST',
  3: 'STEADY_CAST',
  4: 'END_CAST',
}

const BOOLEAN_TAGS = [
  ['CCM.Ready', 'Ready'],
  ['CCM.Running', 'Running'],
  ['CCM.Fault', 'Fault'],
  ['CCM.CastingActive', 'Casting active'],
  ['CCM.CoolingWaterOK', 'Cooling water'],
  ['CCM.MoldLevelControlOK', 'Mold level control'],
  ['CCM.EmergencyStopOK', 'Emergency stop circuit'],
  ['CCM.InterlockOK', 'Interlock'],
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

function Sparkline({ samples }: { samples: TrendSample[] }) {
  const numeric = samples.filter((sample) => typeof sample.value_double === 'number' && Number.isFinite(sample.value_double)).map((sample) => sample.value_double as number)
  if (numeric.length < 2) return <div className="eaf-no-trend">Waiting for historian samples…</div>
  const min = Math.min(...numeric)
  const max = Math.max(...numeric)
  const range = Math.max(max - min, 0.0001)
  const points = numeric.map((value, index) => `${((index / (numeric.length - 1)) * 100).toFixed(2)},${(34 - ((value - min) / range) * 28).toFixed(2)}`).join(' ')
  return <svg className="eaf-sparkline" viewBox="0 0 100 38" preserveAspectRatio="none" aria-hidden="true"><path d="M0 8H100M0 19H100M0 30H100" className="eaf-spark-grid"/><polyline points={points} className="eaf-spark-line"/></svg>
}

export function CcmDashboard() {
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
        const response = await authorizedFetch('/api/v1/ccm/dashboard')
        if (!response.ok) throw new Error(`CCM dashboard returned ${response.status}`)
        const payload = await response.json() as Snapshot
        if (!cancelled) { setSnapshot(payload); setError(null) }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'CCM dashboard unavailable')
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
  const stageCode = get('CCM.StageCode')?.value_double ?? Number(get('CCM.StageCode')?.value_text ?? NaN)
  const stageName = Number.isFinite(stageCode) ? STAGE_BY_CODE[Number(stageCode)] ?? 'IDLE' : 'IDLE'
  const stageIndex = STAGES.indexOf(stageName)
  const running = bool(get('CCM.Running'))
  const castingActive = bool(get('CCM.CastingActive'))
  const fault = bool(get('CCM.Fault'))
  const ready = bool(get('CCM.Ready'))
  const interlock = bool(get('CCM.InterlockOK'))
  const timestamps = snapshot?.values.map((value) => value.ts).filter((value): value is string => Boolean(value)).sort() ?? []
  const latestTs = timestamps.length > 0 ? timestamps[timestamps.length - 1] : null
  const sampleAge = age(latestTs)
  const healthy = !error && fault !== true && sampleAge !== null && sampleAge < 10
  const heatNumber = raw(get('CCM.HeatNumber')) !== '—' ? raw(get('CCM.HeatNumber')) : snapshot?.active_heat?.heat_no ?? '—'
  const moldLevel = get('CCM.MoldLevelPercent')?.value_double
  const renderedMoldLevel = typeof moldLevel === 'number' && Number.isFinite(moldLevel) ? Math.max(10, Math.min(100, moldLevel)) : 55

  const trendCards = [
    ['CCM.CastingSpeed', 'Casting Speed'],
    ['CCM.TundishTemperature', 'Tundish Temperature'],
    ['CCM.MoldLevelPercent', 'Mold Level'],
    ['CCM.TundishWeightTon', 'Tundish Weight'],
  ] as const

  return (
    <section className="eaf-page ccm-page">
      <header className="eaf-heading">
        <div><span className="section-kicker">CONTINUOUS CASTING · LIVE OPERATIONS</span><h1>Continuous Casting Machine · CCM-01</h1><p>Live read-only casting view from PLC telemetry and Timescale historian.</p></div>
        <div className={`eaf-health ${healthy ? 'online' : 'warning'}`}><span className="eaf-health-dot"/><span><strong>{error ? 'DATA RETRYING' : healthy ? 'LIVE CCM TELEMETRY' : 'TELEMETRY DEGRADED'}</strong><small>{sampleAge === null ? 'No recent sample' : `${sampleAge.toFixed(1)} s sample age`} · {snapshot?.mode ?? 'READ ONLY'}</small></span></div>
      </header>

      {error && <div className="eaf-notice"><strong>CCM Dashboard:</strong> {error}. Last valid snapshot remains visible.</div>}

      <section className="eaf-state-strip">
        <div><span>HEAT</span><strong>{heatNumber}</strong><small>{snapshot?.active_heat?.grade_code ?? 'Grade —'}</small></div>
        <div><span>CASTING STAGE</span><strong className="accent">{stageName.split('_').join(' ')}</strong><small>{castingActive === true ? 'CASTING ACTIVE' : running === true ? 'RUNNING' : 'STANDBY'}</small></div>
        <div><span>ELAPSED</span><strong>{elapsed(snapshot?.active_heat?.started_at)}</strong><small>Heat start</small></div>
        <div><span>READY</span><strong className={ready === true ? 'ok' : ready === false ? 'bad' : ''}>{ready === null ? '—' : ready ? 'YES' : 'NO'}</strong><small>CCM.Ready</small></div>
        <div><span>INTERLOCK</span><strong className={interlock === true ? 'ok' : interlock === false ? 'bad' : ''}>{interlock === null ? '—' : interlock ? 'OK' : 'NOT OK'}</strong><small>CCM.InterlockOK</small></div>
        <div><span>FAULT</span><strong className={fault === true ? 'bad' : fault === false ? 'ok' : ''}>{fault === null ? '—' : fault ? 'ACTIVE' : 'CLEAR'}</strong><small>Alarm code {raw(get('CCM.AlarmCode'))}</small></div>
      </section>

      <section className="eaf-kpi-grid">
        <article><span>Casting Speed</span><strong>{withUnit(get('CCM.CastingSpeed'), 2)}</strong><small>CCM.CastingSpeed</small></article>
        <article><span>Tundish Temperature</span><strong>{withUnit(get('CCM.TundishTemperature'), 1)}</strong><small>CCM.TundishTemperature</small></article>
        <article><span>Mold Level</span><strong>{withUnit(get('CCM.MoldLevelPercent'), 1)}</strong><small>CCM.MoldLevelPercent</small></article>
        <article><span>Tundish Weight</span><strong>{withUnit(get('CCM.TundishWeightTon'), 1)}</strong><small>CCM.TundishWeightTon</small></article>
        <article><span>Mold Cooling Flow</span><strong>{withUnit(get('CCM.MoldCoolingWaterFlowM3h'), 1)}</strong><small>CCM.MoldCoolingWaterFlowM3h</small></article>
        <article><span>Cooling Water ΔT</span><strong>{withUnit(get('CCM.MoldCoolingWaterDeltaC'), 1)}</strong><small>CCM.MoldCoolingWaterDeltaC</small></article>
        <article><span>Secondary Cooling</span><strong>{withUnit(get('CCM.SecondaryCoolingFlowM3h'), 1)}</strong><small>CCM.SecondaryCoolingFlowM3h</small></article>
        <article><span>Oscillation Frequency</span><strong>{withUnit(get('CCM.OscillationFrequencyCpm'), 1)}</strong><small>CCM.OscillationFrequencyCpm</small></article>
      </section>

      <div className="eaf-main-grid">
        <section className="eaf-panel eaf-process-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">CASTING PROCESS</span><h2>Tundish → Mold → Strand</h2></div><span className={`eaf-mode-chip ${castingActive ? 'live' : ''}`}>{castingActive ? 'CASTING ACTIVE' : 'STANDBY'}</span></div>
          <div className="eaf-process-body">
            <div className={`ccm-caster-scene ${castingActive ? 'active' : ''}`} aria-hidden="true">
              <div className="ccm-tundish"/>
              <div className="ccm-nozzle"/>
              <div className="ccm-stream"/>
              <div className="ccm-mold"><div className="ccm-mold-level" style={{ height: `${Math.min(35, renderedMoldLevel * 0.35)}px` }}/></div>
              <div className="ccm-strand"/>
              <div className="ccm-rollers"><i/><i/><i/><i/><i/><i/><i/><i/></div>
              <div className="ccm-sprays"><i/><i/><i/><i/></div>
              <span className="ccm-scene-label ccm-temp-label">{withUnit(get('CCM.TundishTemperature'), 0)}</span>
              <span className="ccm-scene-label ccm-speed-label">{withUnit(get('CCM.CastingSpeed'), 2)}</span>
              <span className="ccm-scene-label ccm-level-label">MOLD {withUnit(get('CCM.MoldLevelPercent'), 1)}</span>
            </div>
            <div className="eaf-stage-sequence">
              {STAGES.map((stage, index) => {
                const state = stageIndex < 0 ? 'pending' : index < stageIndex ? 'done' : index === stageIndex ? 'active' : 'pending'
                return <div className={`eaf-stage-step ${state}`} key={stage}><i>{index + 1}</i><span><strong>{stage.split('_').join(' ')}</strong><small>{state === 'active' ? 'CURRENT SUB-PROCESS' : state.toUpperCase()}</small></span></div>
              })}
            </div>
          </div>
          <div className="ccm-status-grid">
            <span className={castingActive ? 'on' : ''}>CAST <b>{castingActive ? 'ACTIVE' : 'OFF'}</b></span>
            <span className={bool(get('CCM.CoolingWaterOK')) ? 'on' : ''}>COOLING <b>{bool(get('CCM.CoolingWaterOK')) ? 'OK' : 'NOT OK'}</b></span>
            <span className={bool(get('CCM.MoldLevelControlOK')) ? 'on' : ''}>MOLD CTRL <b>{bool(get('CCM.MoldLevelControlOK')) ? 'OK' : 'NOT OK'}</b></span>
            <span className={bool(get('CCM.EmergencyStopOK')) ? 'on' : ''}>E-STOP <b>{bool(get('CCM.EmergencyStopOK')) ? 'OK' : 'TRIPPED'}</b></span>
            <span>STOPPER <b>{withUnit(get('CCM.StopperPositionPercent'), 1)}</b></span>
          </div>
        </section>

        <section className="eaf-panel eaf-interlock-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">SAFETY STATUS</span><h2>Interlocks & Permissives</h2></div><span>{BOOLEAN_TAGS.length} signals</span></div>
          <div className="eaf-interlock-list">
            {BOOLEAN_TAGS.map(([tag, label]) => {
              const state = bool(get(tag)); const good = state === null ? null : tag === 'CCM.Fault' ? !state : state
              return <div className="eaf-interlock-row" key={tag}><span className={`eaf-state-light ${good === null ? 'unknown' : good ? 'good' : 'bad'}`}/><span><strong>{label}</strong><small>{tag}</small></span><b>{state === null ? '—' : state ? 'TRUE' : 'FALSE'}</b></div>
            })}
          </div>
        </section>
      </div>

      <section className="eaf-panel eaf-trends-panel">
        <div className="eaf-panel-heading"><div><span className="section-kicker">TIMESCALE HISTORIAN · LAST 60 MIN</span><h2>Live Casting Trends</h2></div><span>{snapshot?.trends.length ?? 0} samples loaded</span></div>
        <div className="eaf-trend-grid">
          {trendCards.map(([tag, label]) => <article className="eaf-trend-card" key={tag}><div><span>{label}</span><strong>{withUnit(get(tag), tag === 'CCM.CastingSpeed' ? 2 : 1)}</strong><small>{get(tag)?.quality ?? 'NO DATA'} · {tag}</small></div><Sparkline samples={trends.get(tag) ?? []}/></article>)}
        </div>
      </section>

      <div className="eaf-bottom-grid">
        <section className="eaf-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">CCM EVENTS</span><h2>Recent Casting Events</h2></div><span>{snapshot?.events.length ?? 0}</span></div>
          <div className="eaf-event-list">{(snapshot?.events ?? []).length === 0 ? <div className="eaf-empty">No CCM events recorded.</div> : snapshot?.events.slice(0, 10).map((event, index) => <div className="eaf-event-row" key={`${event.event_type}-${event.occurred_at ?? index}`}><time>{fmtClock(event.occurred_at)}</time><span><strong>{event.event_type}</strong><small>{event.source_system ?? 'LEVEL 2'} · {event.heat_no ?? 'NO HEAT'} · {event.severity ?? 'INFO'}</small></span></div>)}</div>
        </section>
        <section className="eaf-panel">
          <div className="eaf-panel-heading"><div><span className="section-kicker">ACTIVE ALARMS</span><h2>CCM Alarm State</h2></div><span className={(snapshot?.alarms.length ?? 0) > 0 ? 'eaf-alarm-count' : ''}>{snapshot?.alarms.length ?? 0}</span></div>
          <div className="eaf-alarm-list">{(snapshot?.alarms ?? []).length === 0 ? <div className="eaf-good-state">No active CCM alarms</div> : snapshot?.alarms.slice(0, 8).map((alarm) => <div className={`eaf-alarm-row sev-${alarm.severity.toLowerCase()}`} key={`${alarm.alarm_code}-${alarm.active_at ?? ''}`}><div><strong>{alarm.alarm_code}</strong><small>{alarm.message ?? 'No alarm message'}</small></div><span><b>{alarm.severity}</b><time>{fmtClock(alarm.active_at)}</time></span></div>)}</div>
        </section>
      </div>

      <section className="eaf-panel eaf-raw-panel">
        <div className="eaf-panel-heading"><div><span className="section-kicker">RAW LEVEL 2 VALUES</span><h2>CCM Tag Inspector</h2></div><span>{snapshot?.values.length ?? 0} current tags</span></div>
        <div className="eaf-raw-table-wrap"><table className="eaf-raw-table"><thead><tr><th>Tag</th><th>Value</th><th>Unit</th><th>Quality</th><th>Source</th><th>Timestamp</th></tr></thead><tbody>{(snapshot?.values ?? []).map((value) => <tr key={value.tag_name}><td><code>{value.tag_name}</code></td><td>{raw(value)}</td><td>{value.engineering_unit ?? '—'}</td><td><span className={`eaf-quality ${(value.quality ?? 'unknown').toLowerCase()}`}>{value.quality ?? 'UNKNOWN'}</span></td><td>{value.source_system ?? '—'}</td><td>{fmtClock(value.ts)}</td></tr>)}</tbody></table></div>
      </section>
    </section>
  )
}
