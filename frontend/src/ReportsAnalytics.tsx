import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './reports-analytics.css'

type ReportSummary = {
  heat_count: number
  completed_heats: number
  avg_cycle_minutes?: number | null
  avg_eaf_minutes?: number | null
  avg_lf_minutes?: number | null
  avg_ccm_minutes?: number | null
  avg_specific_energy_kwh_t_est?: number | null
  total_material_tonnes_equiv: number
  total_alarms: number
  high_alarms: number
  avg_good_quality_pct?: number | null
}

type HeatAnalytics = {
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  started_at?: string | null
  completed_at?: string | null
  updated_at?: string | null
  cycle_minutes?: number | null
  eaf_minutes: number
  lf_minutes: number
  ccm_minutes: number
  material_tonnes_equiv: number
  material_additions: number
  alarm_count: number
  high_alarm_count: number
  total_samples: number
  good_samples: number
  avg_eaf_power_mw?: number | null
  eaf_energy_mwh_est?: number | null
  specific_energy_kwh_t_est?: number | null
  good_quality_pct?: number | null
}

type StageBreakdown = {
  stage: string
  equipment_code: string
  status: string
  started_at: string
  ended_at?: string | null
  duration_minutes: number
}

type MaterialBreakdown = {
  material_code: string
  material_name?: string | null
  additions: number
  tonnes_equivalent: number
}

type AlarmSeverity = {
  severity: string
  count: number
}

type ReportsResponse = {
  generated_at: string
  limit: number
  summary: ReportSummary
  heats: HeatAnalytics[]
  selected_heat?: HeatAnalytics | null
  stage_breakdown: StageBreakdown[]
  top_materials: MaterialBreakdown[]
  alarm_severity: AlarmSeverity[]
  energy_method: string
  source: string
  mode: string
}

function formatNumber(value?: number | null, digits = 1): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function formatMinutes(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  if (value < 60) return `${formatNumber(value, 1)} min`
  const hours = Math.floor(value / 60)
  const minutes = Math.round(value - hours * 60)
  return `${hours}h ${minutes}m`
}

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return parsed.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/[^a-z0-9-]+/g, '-')
}

export function ReportsAnalytics() {
  const [data, setData] = useState<ReportsResponse | null>(null)
  const [limit, setLimit] = useState(24)
  const [selectedHeatNo, setSelectedHeatNo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const refresh = async () => {
      try {
        const params = new URLSearchParams({ limit: String(limit) })
        if (selectedHeatNo) params.set('heat_no', selectedHeatNo)
        const response = await authorizedFetch(`/api/v1/reports/dashboard?${params.toString()}`)
        if (!response.ok) throw new Error(`Reports API returned ${response.status}`)
        const payload = await response.json() as ReportsResponse
        if (cancelled) return
        setData(payload)
        setError(null)
        if (!selectedHeatNo && payload.selected_heat?.heat_no) setSelectedHeatNo(payload.selected_heat.heat_no)
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Analytics data unavailable')
      } finally {
        if (!cancelled) {
          setLoading(false)
          timer = window.setTimeout(() => { void refresh() }, 10000)
        }
      }
    }

    void refresh()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [limit, selectedHeatNo])

  const heats = data?.heats ?? []
  const selected = data?.selected_heat ?? null
  const summary = data?.summary
  const maxCycle = Math.max(1, ...heats.map((heat) => Number(heat.cycle_minutes || 0)))
  const stageTotal = useMemo(
    () => (data?.stage_breakdown ?? []).reduce((sum, stage) => sum + Number(stage.duration_minutes || 0), 0),
    [data],
  )
  const maxMaterial = Math.max(0.001, ...(data?.top_materials ?? []).map((item) => Number(item.tonnes_equivalent || 0)))
  const alarmTotal = (data?.alarm_severity ?? []).reduce((sum, item) => sum + Number(item.count || 0), 0)

  return (
    <section className="reports-page">
      <header className="reports-heading">
        <div>
          <span className="section-kicker">HEAT PERFORMANCE INTELLIGENCE</span>
          <h1>Reports & Analytics</h1>
          <p>Read-only heat comparison across cycle time, process stages, energy estimate, material consumption, alarms and historian quality.</p>
        </div>
        <div className={`reports-stream ${error ? 'warning' : 'online'}`}>
          <span className="reports-stream-dot" />
          <span><strong>{error ? 'ANALYTICS DEGRADED' : 'ANALYTICS ONLINE'}</strong><small>{data ? `Updated ${formatDateTime(data.generated_at)}` : 'Waiting for analytics'} · READ ONLY</small></span>
        </div>
      </header>

      {error && <div className="reports-notice"><strong>Reports API:</strong> {error}. Last successful analytics snapshot remains visible.</div>}

      <section className="reports-controls">
        <label>
          <span>Analysis Window</span>
          <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
            <option value={12}>Recent 12 heats</option>
            <option value={24}>Recent 24 heats</option>
            <option value={40}>Recent 40 heats</option>
            <option value={50}>Recent 50 heats</option>
          </select>
        </label>
        <label>
          <span>Selected Heat</span>
          <select value={selectedHeatNo} onChange={(event) => setSelectedHeatNo(event.target.value)}>
            {heats.map((heat) => <option key={heat.heat_no} value={heat.heat_no}>{heat.heat_no} · {heat.status} · {heat.grade_code ?? '—'}</option>)}
          </select>
        </label>
        <div><span>Status</span><strong>{selected?.status ?? '—'}</strong></div>
        <div><span>Grade</span><strong>{selected?.grade_code ?? '—'}</strong></div>
      </section>

      <section className="reports-kpis">
        <article><span>Completed Heats</span><strong>{summary?.completed_heats ?? 0}<i> / {summary?.heat_count ?? 0}</i></strong><small>inside selected analysis window</small></article>
        <article><span>Average Cycle</span><strong>{formatNumber(summary?.avg_cycle_minutes, 1)} <i>min</i></strong><small>completed heats only</small></article>
        <article><span>Average EAF Stage</span><strong>{formatNumber(summary?.avg_eaf_minutes, 1)} <i>min</i></strong><small>recorded heat_stages</small></article>
        <article><span>Specific Energy</span><strong>{formatNumber(summary?.avg_specific_energy_kwh_t_est, 0)} <i>kWh/t</i></strong><small>estimated from EAF.PowerMW</small></article>
        <article><span>Material Mass</span><strong>{formatNumber(summary?.total_material_tonnes_equiv, 1)} <i>t eq.</i></strong><small>tonnes + converted kilograms</small></article>
        <article><span>Historian Quality</span><strong>{formatNumber(summary?.avg_good_quality_pct, 1)} <i>%</i></strong><small>GOOD heat-linked samples</small></article>
      </section>

      <div className="reports-layout">
        <section className="reports-panel reports-cycle-panel">
          <div className="reports-panel-heading"><div><span className="section-kicker">RECENT HEAT COMPARISON</span><h2>Tap-to-End Cycle Time</h2></div><span>{heats.length} HEATS</span></div>
          <div className="reports-cycle-list">
            {heats.map((heat) => {
              const cycle = Number(heat.cycle_minutes || 0)
              const width = cycle > 0 ? Math.max(3, cycle * 100 / maxCycle) : 0
              return <button type="button" className={heat.heat_no === selectedHeatNo ? 'selected' : ''} key={heat.heat_no} onClick={() => setSelectedHeatNo(heat.heat_no)}>
                <span className="reports-cycle-label"><b>{heat.heat_no}</b><small>{heat.grade_code ?? '—'} · {heat.status}</small></span>
                <span className="reports-cycle-track"><i style={{ width: `${width}%` }} /></span>
                <strong>{formatMinutes(heat.cycle_minutes)}</strong>
              </button>
            })}
            {!loading && heats.length === 0 && <div className="reports-empty">No heat analytics are available yet.</div>}
          </div>
        </section>

        <section className="reports-panel reports-stage-panel">
          <div className="reports-panel-heading"><div><span className="section-kicker">SELECTED HEAT</span><h2>Stage Duration Breakdown</h2></div><span>{selected?.heat_no ?? '—'}</span></div>
          <div className="reports-stage-list">
            {(data?.stage_breakdown ?? []).map((stage, index) => {
              const width = stageTotal > 0 ? Math.max(4, stage.duration_minutes * 100 / stageTotal) : 0
              return <article key={`${stage.stage}-${stage.started_at}-${index}`}>
                <div><span><b>{stage.stage}</b><small>{stage.equipment_code} · {stage.status}</small></span><strong>{formatMinutes(stage.duration_minutes)}</strong></div>
                <div className="reports-stage-track"><span style={{ width: `${width}%` }} /></div>
                <footer><span>{formatDateTime(stage.started_at)}</span><span>{stage.ended_at ? formatDateTime(stage.ended_at) : 'ACTIVE'}</span></footer>
              </article>
            })}
            {!loading && (data?.stage_breakdown.length ?? 0) === 0 && <div className="reports-empty">No recorded heat stages for this heat.</div>}
          </div>
          <div className="reports-selected-metrics">
            <div><span>EAF</span><strong>{formatMinutes(selected?.eaf_minutes)}</strong></div>
            <div><span>LF</span><strong>{formatMinutes(selected?.lf_minutes)}</strong></div>
            <div><span>CCM</span><strong>{formatMinutes(selected?.ccm_minutes)}</strong></div>
            <div><span>Cycle</span><strong>{formatMinutes(selected?.cycle_minutes)}</strong></div>
          </div>
        </section>
      </div>

      <div className="reports-layout secondary">
        <section className="reports-panel">
          <div className="reports-panel-heading"><div><span className="section-kicker">MATERIAL INTENSITY</span><h2>Material Mix · {selected?.heat_no ?? '—'}</h2></div><span>{formatNumber(selected?.material_tonnes_equiv, 2)} t eq.</span></div>
          <div className="reports-material-list">
            {(data?.top_materials ?? []).map((item) => <article key={item.material_code}>
              <span><b>{item.material_code}</b><small>{item.material_name ?? item.material_code} · {item.additions} additions</small></span>
              <div className="reports-material-track"><i style={{ width: `${Math.max(3, item.tonnes_equivalent * 100 / maxMaterial)}%` }} /></div>
              <strong>{formatNumber(item.tonnes_equivalent, 3)} t</strong>
            </article>)}
            {!loading && (data?.top_materials.length ?? 0) === 0 && <div className="reports-empty">No material records for this heat.</div>}
          </div>
        </section>

        <section className="reports-panel reports-quality-panel">
          <div className="reports-panel-heading"><div><span className="section-kicker">QUALITY & RISK</span><h2>Historian / Alarm Health</h2></div><span>{selected?.alarm_count ?? 0} ALARMS</span></div>
          <div className="reports-health-grid">
            <article><span>GOOD Samples</span><strong>{formatNumber(selected?.good_quality_pct, 1)}%</strong><small>{selected?.good_samples ?? 0} / {selected?.total_samples ?? 0} samples</small></article>
            <article><span>High / Critical</span><strong>{selected?.high_alarm_count ?? 0}</strong><small>of {selected?.alarm_count ?? 0} heat alarms</small></article>
            <article><span>EAF Energy</span><strong>{formatNumber(selected?.eaf_energy_mwh_est, 2)} MWh</strong><small>calculated estimate</small></article>
            <article><span>Specific Energy</span><strong>{formatNumber(selected?.specific_energy_kwh_t_est, 0)} kWh/t</strong><small>estimated, not a revenue meter</small></article>
          </div>
          <div className="reports-severity-list">
            {(data?.alarm_severity ?? []).map((item) => <div key={item.severity}><span className={`severity-dot severity-${item.severity.toLowerCase()}`} /><span>{item.severity}</span><strong>{item.count}</strong><i style={{ width: `${alarmTotal > 0 ? Math.max(5, item.count * 100 / alarmTotal) : 0}%` }} /></div>)}
            {alarmTotal === 0 && <div className="reports-no-alarms">No alarms linked to the selected heat.</div>}
          </div>
          <div className="reports-method"><span>Energy Calculation</span><small>{data?.energy_method ?? 'Waiting for method metadata'}</small></div>
        </section>
      </div>

      <section className="reports-panel reports-table-panel">
        <div className="reports-panel-heading"><div><span className="section-kicker">HEAT KPI MATRIX</span><h2>Recent Heat Performance</h2></div><span>{data?.mode ?? 'READ_ONLY'} · {data?.source ?? 'LEVEL2'}</span></div>
        <div className="reports-table-wrap">
          <table>
            <thead><tr><th>Heat</th><th>Status</th><th>Cycle</th><th>EAF</th><th>LF</th><th>CCM</th><th>Energy Est.</th><th>Material</th><th>Alarms</th><th>GOOD Quality</th></tr></thead>
            <tbody>{heats.map((heat) => <tr key={heat.heat_no} className={heat.heat_no === selectedHeatNo ? 'selected' : ''} onClick={() => setSelectedHeatNo(heat.heat_no)}>
              <td><strong>{heat.heat_no}</strong><small>{heat.grade_code ?? '—'} · {formatDateTime(heat.updated_at)}</small></td>
              <td><span className={`reports-status reports-status-${statusClass(heat.status)}`}>{heat.status}</span></td>
              <td>{formatMinutes(heat.cycle_minutes)}</td>
              <td>{formatNumber(heat.eaf_minutes, 1)} min</td>
              <td>{formatNumber(heat.lf_minutes, 1)} min</td>
              <td>{formatNumber(heat.ccm_minutes, 1)} min</td>
              <td>{formatNumber(heat.specific_energy_kwh_t_est, 0)} kWh/t</td>
              <td>{formatNumber(heat.material_tonnes_equiv, 2)} t eq.</td>
              <td>{heat.alarm_count}<small>{heat.high_alarm_count} high+</small></td>
              <td>{formatNumber(heat.good_quality_pct, 1)}%</td>
            </tr>)}</tbody>
          </table>
        </div>
      </section>
    </section>
  )
}
