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
  activity_durations_seconds?: Record<string, number>
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

type ActivityInfo = {
  description: string
  focus: string
}

const stateCopy: Record<FlowStation['state'], string> = {
  active: 'IN PROGRESS',
  complete: 'COMPLETE',
  ready: 'READY',
  standby: 'STANDBY',
}

const activityInfo: Record<string, ActivityInfo> = {
  'EAF:Charge': {
    description: 'Metallic charge is loaded and furnace readiness is confirmed before electrical melting begins.',
    focus: 'Confirm charge completion and verify roof, door, cooling and permissive interlocks before energizing.',
  },
  'EAF:Melting': {
    description: 'Arc power, current and oxygen input melt the charge and establish the liquid steel bath.',
    focus: 'Watch power/current stability, oxygen flow, cooling condition and furnace interlocks.',
  },
  'EAF:Refining': {
    description: 'The molten bath is refined while temperature, slag practice and process stability are controlled.',
    focus: 'Watch the steel-temperature trend, oxygen input and any loss of process or safety permissives.',
  },
  'EAF:Superheat': {
    description: 'The bath is brought to the required tapping temperature before transfer to the ladle.',
    focus: 'Watch temperature approach to target and avoid unnecessary thermal overshoot.',
  },
  'EAF:Tapping': {
    description: 'Molten steel is transferred from the EAF into the ladle for secondary metallurgy.',
    focus: 'Confirm safe tapping conditions and downstream ladle readiness before transfer.',
  },
  'LF:Ladle received': {
    description: 'The incoming ladle is received, identified and prepared for secondary-metallurgy treatment.',
    focus: 'Confirm the correct heat, ladle readiness and basic treatment permissives.',
  },
  'LF:Heating': {
    description: 'Arc heating raises or maintains steel temperature for the downstream casting requirement.',
    focus: 'Watch steel temperature, electrical load, argon flow and cooling/interlock status.',
  },
  'LF:Alloying': {
    description: 'Alloy additions trim steel chemistry toward the target grade specification.',
    focus: 'Verify addition sequence and ensure mixing conditions are suitable for chemistry correction.',
  },
  'LF:Argon stirring': {
    description: 'Argon stirring promotes bath homogenization of temperature and chemistry.',
    focus: 'Watch argon flow and pressure, bath stability and treatment time.',
  },
  'LF:Sampling': {
    description: 'A process sample is taken to verify steel chemistry and treatment readiness.',
    focus: 'Confirm sample quality and review chemistry/temperature results before release.',
  },
  'LF:Ready to cast': {
    description: 'LF treatment is complete and the ladle is released toward the continuous caster.',
    focus: 'Confirm target temperature/chemistry and CCM readiness before transfer.',
  },
  'CCM:Prepare': {
    description: 'Tundish, mold, cooling and casting systems are prepared for the incoming heat.',
    focus: 'Confirm cooling-water, mold-level control, emergency-stop and casting permissives.',
  },
  'CCM:Start cast': {
    description: 'Casting begins and speed, mold level and strand conditions are stabilized.',
    focus: 'Watch mold level, casting-speed ramp, tundish temperature and cooling response.',
  },
  'CCM:Steady cast': {
    description: 'Continuous casting runs at stable production conditions while the strand is formed.',
    focus: 'Watch casting speed, mold level, tundish temperature and primary/secondary cooling stability.',
  },
  'CCM:End cast': {
    description: 'Casting speed is reduced and the heat is completed in a controlled end-of-cast sequence.',
    focus: 'Watch final mold/tundish conditions and confirm the casting sequence ends safely.',
  },
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

function compactDurationValue(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds))
  const hours = Math.floor(rounded / 3600)
  const minutes = Math.floor((rounded % 3600) / 60)
  const secs = rounded % 60
  const mm = String(minutes).padStart(2, '0')
  const ss = String(secs).padStart(2, '0')
  if (hours > 0) return `${String(hours).padStart(2, '0')}:${mm}:${ss}`
  return `${mm}:${ss}`
}

function plannedStageDuration(station: FlowStation): number | null {
  if (typeof station.stage_duration_seconds === 'number') {
    return station.stage_duration_seconds
  }
  if (!station.current_activity) return null
  const planned = station.activity_durations_seconds?.[station.current_activity]
  return typeof planned === 'number' ? planned : null
}

function liveStageElapsedSeconds(
  station: FlowStation,
  nowMs: number,
  generatedAt: string,
  timeScale: number,
): number | null {
  if (station.state !== 'active' || typeof station.stage_age_seconds !== 'number') {
    return typeof station.stage_age_seconds === 'number' ? station.stage_age_seconds : null
  }

  let elapsed = station.stage_age_seconds
  const generatedAtMs = Date.parse(generatedAt)
  if (Number.isFinite(generatedAtMs) && nowMs > generatedAtMs) {
    const wallSeconds = (nowMs - generatedAtMs) / 1000
    elapsed += wallSeconds * Math.max(0.1, timeScale)
  }

  const planned = plannedStageDuration(station)
  return planned === null ? elapsed : Math.min(planned, elapsed)
}

function stageTiming(
  station: FlowStation,
  nowMs: number,
  generatedAt: string,
  timeScale: number,
): string {
  if (station.state !== 'active') {
    if (station.state === 'complete') return 'Heat transferred downstream'
    if (station.state === 'ready') return 'Ready for the next heat'
    return 'Waiting for upstream process'
  }

  const liveElapsed = liveStageElapsedSeconds(station, nowMs, generatedAt, timeScale)
  if (liveElapsed === null) return 'Stage timing is collecting'

  const elapsed = durationValue(liveElapsed)
  const durationSeconds = plannedStageDuration(station)
  if (durationSeconds === null) return `${elapsed} in stage`

  const duration = durationValue(durationSeconds)
  const progress = durationSeconds > 0
    ? ` · ${Math.min(100, liveElapsed / durationSeconds * 100).toFixed(0)}%`
    : ''
  return `${elapsed} / ${duration}${progress}`
}

function activityTiming(
  station: FlowStation,
  activity: string,
  activityIndex: number,
  activeActivityIndex: number,
  nowMs: number,
  generatedAt: string,
  timeScale: number,
): string {
  const planned = station.activity_durations_seconds?.[activity]
  if (typeof planned !== 'number') return '—'

  const completed = station.state === 'complete'
    || (station.state === 'active' && activeActivityIndex > activityIndex)
  const current = station.state === 'active' && activeActivityIndex === activityIndex

  let elapsed = 0
  if (completed) {
    elapsed = planned
  } else if (current) {
    elapsed = liveStageElapsedSeconds(station, nowMs, generatedAt, timeScale) ?? 0
    elapsed = Math.min(planned, elapsed)
  }

  return `${compactDurationValue(elapsed)} / ${compactDurationValue(planned)}`
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

function Station({
  station,
  index,
  nowMs,
  generatedAt,
  timeScale,
}: {
  station: FlowStation
  index: number
  nowMs: number
  generatedAt: string
  timeScale: number
}) {
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
        {station.activities.map((activity, activityIndex) => {
          const activityState = station.current_activity === activity
            ? 'current'
            : station.state === 'complete'
              || (station.state === 'active' && activeActivityIndex > activityIndex)
              ? 'complete'
              : 'upcoming'
          const planned = station.activity_durations_seconds?.[activity]
          const completed = activityState === 'complete'
          const current = activityState === 'current'
          const elapsed = typeof planned !== 'number'
            ? null
            : completed
              ? planned
              : current
                ? Math.min(
                    planned,
                    liveStageElapsedSeconds(station, nowMs, generatedAt, timeScale) ?? 0,
                  )
                : 0
          const progress = typeof planned === 'number' && planned > 0 && typeof elapsed === 'number'
            ? Math.min(100, Math.max(0, elapsed / planned * 100))
            : null
          const statusLabel = current
            ? 'IN PROGRESS'
            : completed
              ? 'COMPLETE'
              : 'UPCOMING'
          const info = activityInfo[`${station.area}:${activity}`] ?? {
            description: `${activity} is part of the ${station.label} operating sequence.`,
            focus: 'Monitor the live process values and equipment permissives for this stage.',
          }
          const tooltipId = `${station.id}-activity-${activityIndex}-tooltip`

          return (
            <span
              className={`production-activity ${activityState}`}
              key={activity}
              tabIndex={0}
              aria-describedby={tooltipId}
            >
              <i aria-hidden="true" />
              <span className="production-activity-name">{activity}</span>
              <time className="production-activity-time">
                {activityTiming(
                  station,
                  activity,
                  activityIndex,
                  activeActivityIndex,
                  nowMs,
                  generatedAt,
                  timeScale,
                )}
              </time>

              <div
                className={`production-activity-tooltip ${activityState}`}
                id={tooltipId}
                role="tooltip"
              >
                <div className="production-tooltip-heading">
                  <div>
                    <small>{station.short_label} SUB PROCESS</small>
                    <strong>{activity}</strong>
                  </div>
                  <span>{statusLabel}</span>
                </div>

                <p className="production-tooltip-description">{info.description}</p>

                <div className="production-tooltip-facts">
                  <div>
                    <span>Equipment</span>
                    <strong>{station.equipment}</strong>
                  </div>
                  <div>
                    <span>Heat</span>
                    <strong>{station.heat_number ?? '—'}</strong>
                  </div>
                  <div>
                    <span>Elapsed</span>
                    <strong>{typeof elapsed === 'number' ? compactDurationValue(elapsed) : '—'}</strong>
                  </div>
                  <div>
                    <span>Planned</span>
                    <strong>{typeof planned === 'number' ? compactDurationValue(planned) : '—'}</strong>
                  </div>
                  <div>
                    <span>Progress</span>
                    <strong>{progress === null ? '—' : `${progress.toFixed(0)}%`}</strong>
                  </div>
                  <div>
                    <span>Simulation</span>
                    <strong>x{timeScale}</strong>
                  </div>
                </div>

                {station.metrics.length > 0 && (
                  <div className="production-tooltip-live">
                    <small>LIVE AREA VALUES</small>
                    <div>
                      {station.metrics.slice(0, 2).map((metric) => (
                        <span key={metric.tag_name}>
                          <em>{metricLabel(metric.tag_name)}</em>
                          <strong>
                            {metricValue(metric)} {metric.unit ?? ''}
                          </strong>
                          {metric.quality && <i>{metric.quality}</i>}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="production-tooltip-focus">
                  <small>OPERATOR FOCUS</small>
                  <p>{info.focus}</p>
                </div>
              </div>
            </span>
          )
        })}
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
      <small className="production-stage-time">
        {stageTiming(station, nowMs, generatedAt, timeScale)}
      </small>

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
  const [nowMs, setNowMs] = useState(() => Date.now())

  useEffect(() => {
    const clock = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(clock)
  }, [])

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
          setNowMs(Date.now())
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
  const timeScale = snapshot?.simulation?.time_scale ?? 1

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
                <Station
                  station={station}
                  index={index}
                  nowMs={nowMs}
                  generatedAt={snapshot.generated_at}
                  timeScale={timeScale}
                />
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
              Stage timers show elapsed / planned process time; accelerated demo time is applied live.
            </span>
          </footer>
        </div>
      )}
    </section>
  )
}
