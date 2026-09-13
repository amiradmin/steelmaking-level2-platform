import { useEffect, useState } from 'react'
import { authorizedFetch } from './auth'
import './production-flow.css'

type FlowMetric = {
  tag_name: string
  value: number | string | null
  unit?: string | null
  quality?: string | null
}

type FlowStation = {
  id: string
  label: string
  equipment: string
  short_label: string
  activities: string[]
  state: 'active' | 'complete' | 'ready' | 'standby'
  current_activity?: string | null
  stage_started_at?: string | null
  stage_age_seconds?: number | null
  metrics: FlowMetric[]
}

type ProductionFlowSnapshot = {
  generated_at: string
  current_heat?: { heat_no?: string; grade_code?: string; status?: string } | null
  l1_link: { online: boolean; age_seconds?: number | null; last_sample_at?: string | null }
  stations: FlowStation[]
}

const stateCopy: Record<FlowStation['state'], string> = {
  active: 'IN PROGRESS',
  complete: 'COMPLETE',
  ready: 'READY',
  standby: 'STANDBY',
}

function stageDuration(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number') return 'Waiting for stage timing'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return hours > 0 ? `${hours}h ${minutes}m in stage` : `${minutes}m in stage`
}

function metricValue(metric: FlowMetric): string {
  if (metric.value === null || metric.value === undefined) return '—'
  if (typeof metric.value === 'number') return metric.value.toLocaleString(undefined, { maximumFractionDigits: 1 })
  return String(metric.value)
}

function metricLabel(tagName: string): string {
  const segments = tagName.split('.')
  return segments[segments.length - 1] ?? tagName
}

function Station({ station, index }: { station: FlowStation; index: number }) {
  const activeActivityIndex = station.current_activity ? station.activities.indexOf(station.current_activity) : -1
  return (
    <article className={`production-station ${station.state}`}>
      <header>
        <span className="production-step">0{index + 1}</span>
        <span className="production-state">{stateCopy[station.state]}</span>
      </header>
      <div className="production-equipment-mark">{station.short_label}</div>
      <h2>{station.label}</h2>
      <code>{station.equipment}</code>
      <div className="production-activities" aria-label={`${station.label} activities`}>
        {station.activities.map((activity, activityIndex) => (
          <span
            className={'production-activity ' + (
              station.current_activity === activity
                ? 'current'
                : station.state === 'complete' || (station.state === 'active' && activeActivityIndex > activityIndex)
                  ? 'complete'
                  : 'upcoming'
            )}
            key={activity}
          >
            <i aria-hidden="true" />
            <span>{activity}</span>
          </span>
        ))}
      </div>
      <p className="production-stage-label">{station.state === 'active' ? station.current_activity ?? 'Process active' : station.state === 'complete' ? 'Stage completed' : station.state === 'ready' ? 'Next production stage' : 'Waiting for upstream process'}</p>
      <small className="production-stage-time">{station.state === 'active' ? stageDuration(station.stage_age_seconds) : station.state === 'complete' ? 'Heat transferred downstream' : 'No active heat at this station'}</small>
      <dl className="production-metrics">
        {station.metrics.length > 0 ? station.metrics.map((metric) => <div key={metric.tag_name}><dt>{metricLabel(metric.tag_name)}</dt><dd>{metricValue(metric)} <i>{metric.unit ?? ''}</i></dd></div>) : <div className="metric-empty"><dt>Live values</dt><dd>Waiting for telemetry</dd></div>}
      </dl>
    </article>
  )
}

export function LiveProductionFlow() {
  const [snapshot, setSnapshot] = useState<ProductionFlowSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null
    const refresh = async () => {
      try {
        const response = await authorizedFetch('/api/v1/production-flow')
        if (!response.ok) throw new Error('Production flow data is unavailable')
        const next = await response.json() as ProductionFlowSnapshot
        if (!cancelled) {
          setSnapshot(next)
          setError(null)
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Production flow is unavailable')
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refresh() }, 3000)
      }
    }
    void refresh()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [])

  const online = snapshot?.l1_link.online ?? false
  return (
    <section className="live-production-flow" aria-live="polite">
      <header className="production-heading">
        <div><span className="section-kicker">LIVE STEELMAKING PROCESS</span><h1>Production Flow</h1><p>Current heat position and the live operating condition of each steelmaking station.</p></div>
        <div className={`production-link-state ${online ? 'online' : 'degraded'}`}><span /><div><strong>{online ? 'LIVE PROCESS DATA' : 'PROCESS DATA DELAYED'}</strong><small>{snapshot?.current_heat?.heat_no ? `Heat ${snapshot.current_heat.heat_no}${snapshot.current_heat.grade_code ? ` · ${snapshot.current_heat.grade_code}` : ''}` : 'No active heat received'}</small></div></div>
      </header>

      {error && <div className="production-error">{error}. The page will retry automatically.</div>}
      {!snapshot && !error && <div className="production-loading">Loading live production flow…</div>}

      {snapshot && <div className="production-canvas">
        <div className="production-route-label"><span>SCRAP / DRI</span><i /><span>MOLTEN STEEL</span><i /><span>BILLETS</span></div>
        <div className="production-route">
          {snapshot.stations.map((station, index) => <div className="production-route-item" key={station.id}><Station station={station} index={index} />{index < snapshot.stations.length - 1 && <span className={`production-arrow ${station.state === 'complete' || station.state === 'active' ? 'flowing' : ''}`} aria-hidden="true"><i /></span>}</div>)}
        </div>
        <footer className="production-footer"><span><i className="legend-dot active" /> Active stage</span><span><i className="legend-dot complete" /> Completed</span><span><i className="legend-dot ready" /> Ready for transfer</span><span><i className="legend-dot standby" /> Waiting</span><span>Refreshes every 3 seconds from the Level 2 Historian.</span></footer>
      </div>}
    </section>
  )
}
