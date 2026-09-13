import { useEffect, useMemo, useState } from 'react'
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
  area: string
  label: string
  equipment: string
  short_label: string
  activities: string[]
  state: 'active' | 'complete' | 'ready' | 'standby'
  current_activity?: string | null
  stage_started_at?: string | null
  stage_age_seconds?: number | null
  stage_duration_seconds?: number | null
  stage_progress_percent?: number | null
  heat_number?: number | null
  metrics: FlowMetric[]
}

type ProductionFlowSnapshot = {
  generated_at: string
  current_heat?: { heat_no?: string; grade_code?: string; status?: string } | null
  l1_link: { online: boolean; age_seconds?: number | null; last_sample_at?: string | null }
  simulation?: { time_scale?: number; heat_pitch_minutes?: number }
  pipeline_heats?: Record<string, number | null>
  stations: FlowStation[]
}

const stateCopy: Record<FlowStation['state'], string> = {
  active: 'IN PROGRESS',
  complete: 'COMPLETE',
  ready: 'READY',
  standby: 'STANDBY',
}

function durationValue(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number') return '—'
  const rounded = Math.max(0, Math.round(seconds))
  const hours = Math.floor(rounded / 3600)
  const minutes = Math.floor((rounded % 3600) / 60)
  const secs = rounded % 60
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${secs}s`
  return `${secs}s`
}

function stageTiming(station: FlowStation): string {
  if (station.state !== 'active') {
    if (station.state === 'complete') return 'Heat transferred downstream'
    if (station.state === 'ready') return 'Ready for the next heat'
    return 'Waiting for upstream process'
  }
  if (typeof station.stage_age_seconds !== 'number') return 'Stage timing is collecting'
  const elapsed = durationValue(station.stage_age_seconds)
  if (typeof station.stage_duration_seconds !== 'number') return `${elapsed} in stage`
  const duration = durationValue(station.stage_duration_seconds)
  const progress = typeof station.stage_progress_percent === 'number'
    ? ` · ${station.stage_progress_percent.toFixed(0)}%`
    : ''
  return `${elapsed} / ${duration}${progress}`
}

function metricValue(metric: FlowMetric): string {
  if (metric.value === null || metric.value === undefined) return '—'
  if (typeof metric.value === 'number') {
    return metric.value.toLocaleString(undefined, { maximumFractionDigits: 1 })
  }
  return String(metric.value)
}

function metricLabel(tagName: string): string {
  const segments = tagName.split('.')
  return segments[segments.length - 1] ?? tagName
}

function Station({ station, index }: { station: FlowStation; index: number }) {
  const activeActivityIndex = station.current_activity
    ? station.activities.indexOf(station.current_activity)
    : -1

  return (
    <article className={`production-station ${station.state}`}>
      <header>
        <span className="production-step">0{index + 1}</span>
        <span className="production-state">{stateCopy[station.state]}</span>
      </header>

      <div className="production-equipment-mark">{station.short_label}</div>
      <h2>{station.label}</h2>
      <code>
        {station.equipment}
        {typeof station.heat_number === 'number' ? ` · Heat ${station.heat_number}` : ''}
      </code>

      <div className="production-activities" aria-label={`${station.label} activities`}>
        {station.activities.map((activity, activityIndex) => (
          <span
            className={'production-activity ' + (
              station.current_activity === activity
                ? 'current'
                : station.state === 'complete'
                  || (station.state === 'active' && activeActivityIndex > activityIndex)
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

      <p className="production-stage-label">
        {station.state === 'active'
          ? station.current_activity ?? 'Process active'
          : station.state === 'complete'
            ? 'Stage completed'
            : station.state === 'ready'
              ? 'Ready for next heat'
              : 'Waiting for upstream process'}
      </p>
      <small className="production-stage-time">{stageTiming(station)}</small>

      <dl className="production-metrics">
        {station.metrics.length > 0
          ? station.metrics.map((metric) => (
              <div key={metric.tag_name}>
                <dt>{metricLabel(metric.tag_name)}</dt>
                <dd>{metricValue(metric)} <i>{metric.unit ?? ''}</i></dd>
              </div>
            ))
          : (
              <div className="metric-empty">
                <dt>Live values</dt>
                <dd>Waiting for telemetry</dd>
              </div>
            )}
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
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Production flow is unavailable',
          )
        }
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

  const pipelineLabel = useMemo(() => {
    if (!snapshot) return 'No PLC pipeline data received'
    const entries = ['EAF', 'LF', 'CCM']
      .map((area) => {
        const heat = snapshot.pipeline_heats?.[area]
        return typeof heat === 'number' ? `${area} ${heat}` : null
      })
      .filter((value): value is string => value !== null)

    const scale = snapshot.simulation?.time_scale
    const speed = typeof scale === 'number' ? ` · x${scale} simulation` : ''
    if (entries.length > 0) return `${entries.join(' · ')}${speed}`

    if (snapshot.current_heat?.heat_no) {
      return `Heat ${snapshot.current_heat.heat_no}${speed}`
    }
    return `No active heat received${speed}`
  }, [snapshot])

  const online = snapshot?.l1_link.online ?? false

  return (
    <section className="live-production-flow" aria-live="polite">
      <header className="production-heading">
        <div>
          <span className="section-kicker">LIVE STEELMAKING PROCESS</span>
          <h1>Production Flow</h1>
          <p>
            Charge to End Cast, driven by the synchronized EAF, LF and CCM PLC simulators.
          </p>
        </div>
        <div className={`production-link-state ${online ? 'online' : 'degraded'}`}>
          <span />
          <div>
            <strong>{online ? 'LIVE PROCESS DATA' : 'PROCESS DATA DELAYED'}</strong>
            <small>{pipelineLabel}</small>
          </div>
        </div>
      </header>

      {error && (
        <div className="production-error">
          {error}. The page will retry automatically.
        </div>
      )}
      {!snapshot && !error && (
        <div className="production-loading">Loading live production flow…</div>
      )}

      {snapshot && (
        <div className="production-canvas">
          <div className="production-route-label">
            <span>SCRAP / DRI</span><i /><span>MOLTEN STEEL</span><i /><span>BILLETS</span>
          </div>
          <div className="production-route">
            {snapshot.stations.map((station, index) => (
              <div className="production-route-item" key={station.id}>
                <Station station={station} index={index} />
                {index < snapshot.stations.length - 1 && (
                  <span
                    className={`production-arrow ${
                      station.state === 'complete' || station.state === 'active'
                        ? 'flowing'
                        : ''
                    }`}
                    aria-hidden="true"
                  >
                    <i />
                  </span>
                )}
              </div>
            ))}
          </div>
          <footer className="production-footer">
            <span><i className="legend-dot active" /> Active stage</span>
            <span><i className="legend-dot complete" /> Completed</span>
            <span><i className="legend-dot ready" /> Ready / turnaround</span>
            <span><i className="legend-dot standby" /> Waiting</span>
            <span>
              Stage times are process-time values; the PLC demo may run accelerated.
            </span>
          </footer>
        </div>
      )}
    </section>
  )
}
