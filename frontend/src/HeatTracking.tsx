import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './heat-tracking.css'

type Heat = {
  id?: number
  heat_no: string
  status: string
  grade_code?: string | null
  grade_name?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  production_order_id?: string | number | null
  planned_sequence?: number | null
  started_at?: string | null
  completed_at?: string | null
  updated_at?: string | null
}

type LiveValue = {
  tag_name: string
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
}

type HeatEvent = {
  event_type: string
  source_system?: string | null
  source_event_id?: string | null
  area?: string | null
  equipment_code?: string | null
  severity?: string | null
  occurred_at?: string | null
  payload?: Record<string, unknown> | null
}

type HeatStageRecord = {
  stage: string
  equipment_code?: string | null
  status?: string | null
  started_at?: string | null
  ended_at?: string | null
  attributes?: Record<string, unknown> | null
}

type HeatTimeline = {
  heat_no: string
  status: string
  started_at?: string | null
  completed_at?: string | null
  updated_at?: string | null
  stages: HeatStageRecord[]
  events: HeatEvent[]
  source?: string | null
}

type MaterialSummary = {
  material_code: string
  material_name?: string | null
  unit?: string | null
  total_quantity?: number | null
  additions?: number | null
}

type Alarm = {
  alarm_code: string
  severity: string
  state?: string | null
  message: string
  active_at?: string | null
  cleared_at?: string | null
}

type HeatOverview = {
  heat: Heat
  live_values: LiveValue[]
  material_summary: MaterialSummary[]
  recent_events: HeatEvent[]
  active_alarms: Alarm[]
}

type StageId = 'CHARGE' | 'EAF' | 'LF' | 'CCM'
type StageState = 'done' | 'active' | 'pending'
type TimingSource = 'HEAT_STAGE' | 'STATUS_EVENT' | 'AREA_EVENT' | 'NONE'

type Stage = {
  id: StageId
  title: string
  equipment: string
  aliases: string[]
}

type StageTiming = {
  start?: string
  end?: string
  source: TimingSource
}

const STAGES: Stage[] = [
  { id: 'CHARGE', title: 'Charge', equipment: 'Raw Materials', aliases: ['CHARGE', 'CHARGING'] },
  { id: 'EAF', title: 'Electric Arc Furnace', equipment: 'EAF-01', aliases: ['EAF', 'MELTING', 'TAPPING'] },
  { id: 'LF', title: 'Ladle Furnace', equipment: 'LF-01', aliases: ['LF', 'REFINING'] },
  { id: 'CCM', title: 'Continuous Casting', equipment: 'CCM-01', aliases: ['CCM', 'CASTING'] },
]

const STATUS_RANK: Record<string, number> = {
  PLANNED: -1,
  CREATED: -1,
  CHARGING: 0,
  CHARGE: 0,
  EAF: 1,
  MELTING: 1,
  TAPPING: 1,
  LF: 2,
  REFINING: 2,
  CASTING: 3,
  CCM: 3,
  COMPLETED: 4,
  ABORTED: 4,
  CANCELLED: 4,
}

const ACTIVE_TERMINAL = new Set(['COMPLETED', 'ABORTED', 'CANCELLED'])

function fmtClock(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function duration(from?: string | null, to?: string | null): string {
  if (!from) return '—'
  const start = new Date(from).getTime()
  const end = to ? new Date(to).getTime() : Date.now()
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '—'
  const total = Math.floor((end - start) / 1000)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return hours > 0
    ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function number(value?: number | null, digits = 1): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function liveValue(values: LiveValue[], ...tags: string[]): LiveValue | undefined {
  for (const tag of tags) {
    const found = values.find((item) => item.tag_name === tag)
    if (found) return found
  }
  return undefined
}

function valueText(value?: LiveValue): string {
  if (!value) return '—'
  const raw = value.value_double ?? value.value_text
  if (raw === null || raw === undefined || raw === '') return '—'
  const rendered = typeof raw === 'number' ? number(raw, 2) : String(raw)
  return `${rendered}${value.engineering_unit ? ` ${value.engineering_unit}` : ''}`
}

function currentRank(status?: string | null): number {
  return STATUS_RANK[(status ?? '').toUpperCase()] ?? -1
}

function stageState(stageIndex: number, status?: string | null): StageState {
  const rank = currentRank(status)
  if (rank >= 4) return 'done'
  if (stageIndex < rank) return 'done'
  if (stageIndex === rank) return 'active'
  return 'pending'
}

function normalizedStatus(value: unknown): string {
  return typeof value === 'string' ? value.trim().toUpperCase() : ''
}

function payloadStatus(event: HeatEvent, key: 'from' | 'to'): string {
  return normalizedStatus(event.payload?.[key])
}

function stageOwnsStatus(stage: Stage, status: string): boolean {
  return stage.aliases.some((alias) => alias === status)
}

function stageTiming(stage: Stage, records: HeatStageRecord[], events: HeatEvent[]): StageTiming {
  const persisted = records
    .filter((record) => {
      const name = normalizedStatus(record.stage)
      return stage.aliases.some((alias) => name === alias || name.includes(alias))
    })
    .filter((record) => Boolean(record.started_at))
    .sort((left, right) => String(left.started_at).localeCompare(String(right.started_at)))

  if (persisted.length > 0) {
    const first = persisted[0]
    const ended = persisted
      .map((record) => record.ended_at)
      .filter((value): value is string => Boolean(value))
      .sort()
    return {
      start: first.started_at ?? undefined,
      end: ended.length > 0 ? ended[ended.length - 1] : undefined,
      source: 'HEAT_STAGE',
    }
  }

  const ordered = events
    .filter((event) => Boolean(event.occurred_at))
    .slice()
    .sort((left, right) => String(left.occurred_at).localeCompare(String(right.occurred_at)))

  let start: string | undefined
  let end: string | undefined
  for (const event of ordered) {
    if ((event.event_type ?? '').toUpperCase() !== 'STATUS_CHANGED' || !event.occurred_at) continue
    const from = payloadStatus(event, 'from')
    const to = payloadStatus(event, 'to')
    if (!start && stageOwnsStatus(stage, to) && !stageOwnsStatus(stage, from)) {
      start = event.occurred_at
      continue
    }
    if (start && stageOwnsStatus(stage, from) && !stageOwnsStatus(stage, to)) {
      end = event.occurred_at
      break
    }
  }
  if (start) return { start, end, source: 'STATUS_EVENT' }

  const areaEvidence = ordered.filter((event) => {
    const area = normalizedStatus(event.area)
    const eventType = normalizedStatus(event.event_type)
    return stage.aliases.some((alias) => area.includes(alias) || eventType.includes(alias))
  })
  if (areaEvidence.length > 0) {
    return {
      start: areaEvidence[0].occurred_at ?? undefined,
      end: areaEvidence.length > 1 ? areaEvidence[areaEvidence.length - 1].occurred_at ?? undefined : undefined,
      source: 'AREA_EVENT',
    }
  }

  return { source: 'NONE' }
}

function resolvedStageState(stageIndex: number, status: string, timing: StageTiming): StageState {
  if (timing.start && timing.end) return 'done'
  if (timing.start && !timing.end && !ACTIVE_TERMINAL.has(status.toUpperCase())) return 'active'
  return stageState(stageIndex, status)
}

function timingSourceLabel(source: TimingSource): string {
  if (source === 'HEAT_STAGE') return 'persisted stage timestamps'
  if (source === 'STATUS_EVENT') return 'lifecycle event timestamps'
  if (source === 'AREA_EVENT') return 'Level 1 area event timestamps'
  return 'awaiting lifecycle evidence'
}

function stageMetrics(stage: StageId, values: LiveValue[]): Array<[string, string]> {
  if (stage === 'EAF') {
    return [
      ['Power', valueText(liveValue(values, 'EAF.PowerMW'))],
      ['Current', valueText(liveValue(values, 'EAF.CurrentKA'))],
      ['Temperature', valueText(liveValue(values, 'EAF.SteelTemperature'))],
    ]
  }
  if (stage === 'LF') {
    return [
      ['Temperature', valueText(liveValue(values, 'LF.SteelTemperature'))],
      ['Argon', valueText(liveValue(values, 'LF.ArgonFlow'))],
      ['Power', valueText(liveValue(values, 'LF.PowerMW'))],
    ]
  }
  if (stage === 'CCM') {
    return [
      ['Casting speed', valueText(liveValue(values, 'CCM.CastingSpeed'))],
      ['Tundish temp.', valueText(liveValue(values, 'CCM.TundishTemperature'))],
      ['Mold level', valueText(liveValue(values, 'CCM.MoldLevelPercent'))],
    ]
  }
  return []
}

function statusLabel(status: string): string {
  const normalized = status.toUpperCase()
  if (normalized === 'LF') return 'REFINING'
  if (normalized === 'EAF') return 'MELTING'
  if (normalized === 'CASTING') return 'CASTING'
  return normalized
}

export function HeatTracking() {
  const [heats, setHeats] = useState<Heat[]>([])
  const [selectedHeatNo, setSelectedHeatNo] = useState<string | null>(null)
  const [overview, setOverview] = useState<HeatOverview | null>(null)
  const [timeline, setTimeline] = useState<HeatTimeline | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [loading, setLoading] = useState(true)
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
        const response = await authorizedFetch('/api/v1/heats?limit=80')
        if (!response.ok) throw new Error(`Heat list returned ${response.status}`)
        const payload = await response.json() as Heat[]
        if (cancelled) return
        setHeats(payload)
        setError(null)
        setSelectedHeatNo((current) => {
          if (current && payload.some((heat) => heat.heat_no === current)) return current
          return payload.find((heat) => !ACTIVE_TERMINAL.has(heat.status.toUpperCase()))?.heat_no ?? payload[0]?.heat_no ?? null
        })
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Heat Tracking API unavailable')
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

  useEffect(() => {
    if (!selectedHeatNo) {
      setOverview(null)
      setTimeline(null)
      return
    }
    let cancelled = false
    let timer: number | null = null

    const refresh = async () => {
      try {
        const heatPath = encodeURIComponent(selectedHeatNo)
        const [overviewResponse, timelineResponse] = await Promise.all([
          authorizedFetch(`/api/v1/heats/${heatPath}/overview`),
          authorizedFetch(`/api/v1/heats/${heatPath}/timeline`),
        ])
        if (!overviewResponse.ok) throw new Error(`Heat overview returned ${overviewResponse.status}`)
        if (!timelineResponse.ok) throw new Error(`Heat timeline returned ${timelineResponse.status}`)
        const [overviewPayload, timelinePayload] = await Promise.all([
          overviewResponse.json() as Promise<HeatOverview>,
          timelineResponse.json() as Promise<HeatTimeline>,
        ])
        if (!cancelled) {
          setOverview(overviewPayload)
          setTimeline(timelinePayload)
          setError(null)
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Heat detail unavailable')
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refresh() }, 3000)
      }
    }

    void refresh()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [selectedHeatNo])

  const filteredHeats = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return heats.filter((heat) => {
      const statusMatches = statusFilter === 'ALL'
        || (statusFilter === 'ACTIVE' && !ACTIVE_TERMINAL.has(heat.status.toUpperCase()))
        || heat.status.toUpperCase() === statusFilter
      const textMatches = !needle || `${heat.heat_no} ${heat.grade_code ?? ''} ${heat.status}`.toLowerCase().includes(needle)
      return statusMatches && textMatches
    })
  }, [heats, search, statusFilter])

  const selected = overview?.heat ?? heats.find((heat) => heat.heat_no === selectedHeatNo) ?? null
  const values = overview?.live_values ?? []
  const lifecycleEvents = timeline?.events ?? overview?.recent_events ?? []
  const recentEvents = lifecycleEvents.slice().reverse()
  const stageRecords = timeline?.stages ?? []
  const materials = overview?.material_summary ?? []
  const alarms = overview?.active_alarms ?? []
  const liveTemperature = selected?.status?.toUpperCase() === 'CASTING'
    ? liveValue(values, 'CCM.TundishTemperature', 'LF.SteelTemperature')
    : selected?.status?.toUpperCase() === 'LF'
      ? liveValue(values, 'LF.SteelTemperature', 'EAF.SteelTemperature')
      : liveValue(values, 'EAF.SteelTemperature', 'LF.SteelTemperature', 'CCM.TundishTemperature')
  const activeCount = heats.filter((heat) => !ACTIVE_TERMINAL.has(heat.status.toUpperCase())).length
  const completedCount = heats.filter((heat) => heat.status.toUpperCase() === 'COMPLETED').length

  return (
    <section className="heat-tracking-page">
      <header className="heat-tracking-heading">
        <div>
          <span className="section-kicker">HEAT LIFECYCLE · LEVEL 2</span>
          <h1>Heat Tracking</h1>
          <p>Follow each heat from charge through EAF, LF and continuous casting using live Level 2 data.</p>
        </div>
        <div className="heat-tracking-health">
          <span className={`heat-tracking-pulse ${error ? 'warning' : 'online'}`} />
          <span><strong>{error ? 'DATA RETRYING' : 'LIVE HEAT MODEL'}</strong><small>{heats.length} heats · {activeCount} active</small></span>
        </div>
      </header>

      {error && <div className="heat-tracking-notice"><strong>Heat Tracking:</strong> {error}. Existing data remains visible while the dashboard retries.</div>}

      <div className="heat-tracking-layout">
        <aside className="heat-queue-panel">
          <div className="heat-queue-title">
            <div><span>HEAT QUEUE</span><strong>{filteredHeats.length}</strong></div>
            <small>{completedCount} completed in loaded history</small>
          </div>
          <div className="heat-queue-controls">
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search heat or grade…" aria-label="Search heats" />
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter heats by status">
              <option value="ALL">All statuses</option>
              <option value="ACTIVE">Active only</option>
              <option value="EAF">EAF</option>
              <option value="LF">LF</option>
              <option value="CASTING">Casting</option>
              <option value="COMPLETED">Completed</option>
            </select>
          </div>
          <div className="heat-queue-list">
            {loading && heats.length === 0 ? <div className="heat-queue-empty">Loading heat queue…</div> : null}
            {!loading && filteredHeats.length === 0 ? <div className="heat-queue-empty">No heats match this filter.</div> : null}
            {filteredHeats.map((heat) => {
              const selectedItem = heat.heat_no === selectedHeatNo
              const active = !ACTIVE_TERMINAL.has(heat.status.toUpperCase())
              return (
                <button key={heat.heat_no} className={`heat-queue-item ${selectedItem ? 'selected' : ''}`} type="button" onClick={() => setSelectedHeatNo(heat.heat_no)}>
                  <span className={`heat-queue-dot ${active ? 'active' : 'done'}`} />
                  <span className="heat-queue-copy">
                    <strong>{heat.heat_no}</strong>
                    <small>{heat.grade_code ?? 'GRADE —'} · {fmtDateTime(heat.started_at)}</small>
                  </span>
                  <span className={`heat-queue-status status-${heat.status.toLowerCase()}`}>{statusLabel(heat.status)}</span>
                </button>
              )
            })}
          </div>
        </aside>

        <main className="heat-detail-panel">
          {!selected ? <div className="heat-detail-empty">Select a heat from the queue to inspect its lifecycle.</div> : <>
            <section className="heat-summary-card">
              <div className="heat-summary-id">
                <span>SELECTED HEAT</span>
                <strong>{selected.heat_no}</strong>
                <small>{selected.grade_code ?? 'Grade not assigned'}{selected.grade_name ? ` · ${selected.grade_name}` : ''}</small>
              </div>
              <div className="heat-summary-metrics">
                <div><span>Status</span><strong className="heat-accent">{statusLabel(selected.status)}</strong><small>Current lifecycle state</small></div>
                <div><span>Elapsed</span><strong>{duration(selected.started_at, selected.completed_at)}</strong><small>Since heat start</small></div>
                <div><span>Temperature</span><strong>{valueText(liveTemperature)}</strong><small>{liveTemperature?.quality ?? 'NO LIVE SAMPLE'}</small></div>
                <div><span>Weight</span><strong>{number(selected.actual_weight_t ?? selected.planned_weight_t)} t</strong><small>Plan {number(selected.planned_weight_t)} t</small></div>
                <div><span>Alarms</span><strong className={alarms.length ? 'heat-danger' : ''}>{alarms.length}</strong><small>Currently active</small></div>
              </div>
            </section>

            <section className="heat-route-card">
              <div className="heat-section-heading"><div><span className="section-kicker">PROCESS ROUTE · EVENT DERIVED</span><h2>Charge → EAF → LF → CCM</h2></div><span className="heat-route-state">EVENT TIMELINE · Updated {fmtClock(timeline?.updated_at ?? selected.updated_at)}</span></div>
              <div className="heat-route-timeline">
                {STAGES.map((stage, index) => {
                  const timing = stageTiming(stage, stageRecords, lifecycleEvents)
                  const state = resolvedStageState(index, selected.status, timing)
                  const metrics = stageMetrics(stage.id, values)
                  const fallbackStart = stage.id === 'EAF' && index === currentRank(selected.status) ? selected.started_at ?? undefined : undefined
                  const stageStart = timing.start ?? fallbackStart
                  const stageEnd = state === 'active' ? undefined : timing.end
                  return (
                    <article className={`heat-stage ${state}`} key={stage.id}>
                      <div className="heat-stage-marker"><span>{index + 1}</span></div>
                      <div className="heat-stage-body">
                        <header><div><strong>{stage.title}</strong><small>{stage.equipment} · {timingSourceLabel(timing.source)}</small></div><em>{state.toUpperCase()}</em></header>
                        <div className="heat-stage-time"><span>START <b>{fmtClock(stageStart)}</b></span><span>END <b>{state === 'active' ? 'LIVE' : fmtClock(stageEnd)}</b></span><span>DURATION <b>{duration(stageStart, stageEnd)}</b></span></div>
                        {metrics.length > 0 && <div className="heat-stage-metrics">{metrics.map(([label, value]) => <span key={label}><small>{label}</small><strong>{value}</strong></span>)}</div>}
                      </div>
                    </article>
                  )
                })}
              </div>
            </section>

            <div className="heat-detail-grid">
              <section className="heat-side-card">
                <div className="heat-section-heading compact"><div><span className="section-kicker">LIFECYCLE EVENTS</span><h2>Complete Event Log</h2></div><span>{lifecycleEvents.length}</span></div>
                <div className="heat-event-list">
                  {recentEvents.length === 0 ? <div className="heat-card-empty">No heat events have been recorded yet.</div> : recentEvents.slice(0, 10).map((event, index) => (
                    <div className="heat-event-row" key={`${event.source_event_id ?? event.event_type}-${event.occurred_at ?? index}`}>
                      <span className="heat-event-time">{fmtClock(event.occurred_at)}</span>
                      <span><strong>{event.event_type}</strong><small>{event.area ?? event.equipment_code ?? event.source_system ?? 'LEVEL 2'} · {event.severity ?? 'INFO'}</small></span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="heat-side-card">
                <div className="heat-section-heading compact"><div><span className="section-kicker">MATERIALS / ALARMS</span><h2>Heat Context</h2></div><span>{materials.length + alarms.length}</span></div>
                <div className="heat-context-columns">
                  <div>
                    <h3>Material summary</h3>
                    {materials.length === 0 ? <div className="heat-card-empty small">No material additions linked yet.</div> : materials.slice(0, 6).map((item) => (
                      <div className="heat-context-row" key={`${item.material_code}-${item.unit ?? ''}`}><span><strong>{item.material_name ?? item.material_code}</strong><small>{item.additions ?? 0} additions</small></span><b>{number(item.total_quantity)} {item.unit ?? ''}</b></div>
                    ))}
                  </div>
                  <div>
                    <h3>Active alarms</h3>
                    {alarms.length === 0 ? <div className="heat-good-state">No active alarms for this heat</div> : alarms.slice(0, 6).map((alarm) => (
                      <div className="heat-alarm-row" key={`${alarm.alarm_code}-${alarm.active_at ?? ''}`}><span><strong>{alarm.alarm_code}</strong><small>{alarm.message}</small></span><b>{alarm.severity}</b></div>
                    ))}
                  </div>
                </div>
              </section>
            </div>
          </>}
        </main>
      </div>
    </section>
  )
}
