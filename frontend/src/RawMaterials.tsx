import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './raw-materials.css'

type HeatRow = {
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  material_additions?: number | null
  total_tonnes?: number | null
  total_kg?: number | null
  updated_at?: string | null
}

type SelectedHeat = {
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  started_at?: string | null
  completed_at?: string | null
  updated_at?: string | null
}

type MaterialSummary = {
  material_code: string
  material_name?: string | null
  unit: string
  total_quantity: number
  additions: number
  first_addition_at?: string | null
  last_addition_at?: string | null
}

type MaterialAddition = {
  id: string
  material_code: string
  material_name?: string | null
  quantity: number
  unit: string
  addition_time: string
  source_system: string
  batch_no?: string | null
  equipment_code?: string | null
  equipment_area?: string | null
  attributes?: unknown
}

type EquipmentTotal = {
  equipment_code: string
  area: string
  unit: string
  total_quantity: number
  additions: number
}

type DashboardResponse = {
  generated_at: string
  selected_heat?: SelectedHeat | null
  heats: HeatRow[]
  summary: MaterialSummary[]
  additions: MaterialAddition[]
  equipment_totals: EquipmentTotal[]
  source: string
  mode: string
}

function formatNumber(value?: number | null, digits = 1): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function materialFamily(item: MaterialSummary | MaterialAddition): string {
  const text = `${item.material_code} ${item.material_name ?? ''}`.toUpperCase()
  if (/SCRAP|DRI|HBI|PIG|IRON|METALLIC/.test(text)) return 'METALLICS'
  if (/LIME|DOLOMITE|FLUX|CaO/i.test(text)) return 'FLUXES'
  if (/CARBON|COKE|GRAPHITE/.test(text)) return 'CARBON'
  if (/FE(MN|SI|CR|V|TI)|ALLOY|FERRO/.test(text)) return 'ALLOYS'
  return 'OTHER'
}

export function RawMaterials() {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [selectedHeatNo, setSelectedHeatNo] = useState<string>('')
  const [search, setSearch] = useState('')
  const [family, setFamily] = useState('ALL')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const refresh = async () => {
      try {
        const query = selectedHeatNo ? `?heat_no=${encodeURIComponent(selectedHeatNo)}` : ''
        const response = await authorizedFetch(`/api/v1/materials/dashboard${query}`)
        if (!response.ok) throw new Error(`Materials API returned ${response.status}`)
        const payload = await response.json() as DashboardResponse
        if (cancelled) return
        setData(payload)
        setError(null)
        if (!selectedHeatNo && payload.selected_heat?.heat_no) setSelectedHeatNo(payload.selected_heat.heat_no)
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Material data unavailable')
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
  }, [selectedHeatNo])

  const filteredSummary = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (data?.summary ?? []).filter((item) => {
      if (family !== 'ALL' && materialFamily(item) !== family) return false
      if (!needle) return true
      return `${item.material_code} ${item.material_name ?? ''}`.toLowerCase().includes(needle)
    })
  }, [data, search, family])

  const totalAdditions = data?.additions.length ?? 0
  const totalTonnes = useMemo(() => (data?.summary ?? [])
    .filter((item) => ['t', 'ton', 'tons', 'tonne', 'tonnes'].includes(item.unit.toLowerCase()))
    .reduce((sum, item) => sum + Number(item.total_quantity || 0), 0), [data])
  const totalKg = useMemo(() => (data?.summary ?? [])
    .filter((item) => ['kg', 'kilogram', 'kilograms'].includes(item.unit.toLowerCase()))
    .reduce((sum, item) => sum + Number(item.total_quantity || 0), 0), [data])
  const maxSummary = Math.max(1, ...filteredSummary.map((item) => Number(item.total_quantity || 0)))

  return (
    <section className="materials-page">
      <header className="materials-heading">
        <div>
          <span className="section-kicker">CHARGE & MATERIAL TRACEABILITY</span>
          <h1>Raw Materials & Charging</h1>
          <p>Heat-linked charge, flux, carbon and alloy consumption from the Level 2 material record.</p>
        </div>
        <div className={`materials-stream ${error ? 'warning' : 'online'}`}>
          <span className="materials-stream-dot" />
          <span><strong>{error ? 'MATERIAL DATA DEGRADED' : 'MATERIAL RECORD ONLINE'}</strong><small>{data ? `Updated ${formatDateTime(data.generated_at)}` : 'Waiting for data'} · READ ONLY</small></span>
        </div>
      </header>

      {error && <div className="materials-notice"><strong>Materials API:</strong> {error}. Last valid record remains visible.</div>}

      <section className="materials-heat-strip">
        <label>
          <span>Selected Heat</span>
          <select value={selectedHeatNo} onChange={(event) => setSelectedHeatNo(event.target.value)}>
            {(data?.heats ?? []).map((heat) => <option key={heat.heat_no} value={heat.heat_no}>{heat.heat_no} · {heat.status} · {heat.grade_code ?? '—'}</option>)}
          </select>
        </label>
        <div><span>Status</span><strong>{data?.selected_heat?.status ?? '—'}</strong></div>
        <div><span>Grade</span><strong>{data?.selected_heat?.grade_code ?? '—'}</strong></div>
        <div><span>Planned Weight</span><strong>{formatNumber(data?.selected_heat?.planned_weight_t, 1)} <small>t</small></strong></div>
        <div><span>Actual Weight</span><strong>{formatNumber(data?.selected_heat?.actual_weight_t, 1)} <small>t</small></strong></div>
      </section>

      <section className="materials-kpis">
        <article><span>Recorded Additions</span><strong>{totalAdditions}</strong><small>individual charging events</small></article>
        <article><span>Ton-Based Materials</span><strong>{formatNumber(totalTonnes, 2)} <i>t</i></strong><small>sum of tonne-unit records</small></article>
        <article><span>Kg-Based Materials</span><strong>{formatNumber(totalKg, 1)} <i>kg</i></strong><small>sum of kilogram-unit records</small></article>
        <article><span>Material Types</span><strong>{data?.summary.length ?? 0}</strong><small>unique code / unit combinations</small></article>
      </section>

      <div className="materials-layout">
        <section className="materials-panel materials-summary-panel">
          <div className="materials-panel-heading">
            <div><span className="section-kicker">HEAT MATERIAL BALANCE</span><h2>Consumption by Material</h2></div>
            <span>{filteredSummary.length} MATERIALS</span>
          </div>
          <div className="materials-toolbar">
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search material code or name…" />
            <select value={family} onChange={(event) => setFamily(event.target.value)}>
              <option value="ALL">All families</option>
              <option value="METALLICS">Metallics</option>
              <option value="FLUXES">Fluxes</option>
              <option value="CARBON">Carbon</option>
              <option value="ALLOYS">Alloys</option>
              <option value="OTHER">Other</option>
            </select>
          </div>
          <div className="material-card-list">
            {filteredSummary.map((item) => {
              const width = Math.max(3, (Number(item.total_quantity || 0) / maxSummary) * 100)
              return <article className="material-balance-card" key={`${item.material_code}-${item.unit}`}>
                <div className="material-balance-top"><span><b>{item.material_code}</b><small>{item.material_name ?? item.material_code}</small></span><em>{materialFamily(item)}</em></div>
                <div className="material-balance-value"><strong>{formatNumber(item.total_quantity, 2)}</strong><span>{item.unit}</span><small>{item.additions} additions</small></div>
                <div className="material-bar"><span style={{ width: `${width}%` }} /></div>
                <footer><span>First {formatDateTime(item.first_addition_at)}</span><span>Last {formatDateTime(item.last_addition_at)}</span></footer>
              </article>
            })}
            {!loading && filteredSummary.length === 0 && <div className="materials-empty"><strong>No material additions recorded for this heat.</strong><small>The screen is ready for Level 1 charging/scale records in material_consumptions; no values are fabricated.</small></div>}
          </div>
        </section>

        <aside className="materials-panel materials-area-panel">
          <div className="materials-panel-heading"><div><span className="section-kicker">EQUIPMENT BALANCE</span><h2>Additions by Station</h2></div></div>
          <div className="equipment-material-list">
            {(data?.equipment_totals ?? []).map((item) => <article key={`${item.equipment_code}-${item.unit}`}>
              <span><b>{item.equipment_code}</b><small>{item.area}</small></span>
              <strong>{formatNumber(item.total_quantity, 2)} <i>{item.unit}</i></strong>
              <em>{item.additions} additions</em>
            </article>)}
            {!loading && (data?.equipment_totals.length ?? 0) === 0 && <div className="materials-empty compact"><strong>No station material totals yet.</strong><small>Records will appear when additions are linked to EAF/LF/CCM equipment.</small></div>}
          </div>
          <div className="materials-source-card"><span>Source of Truth</span><strong>material_consumptions</strong><small>PostgreSQL / TimescaleDB · {data?.mode ?? 'READ_ONLY'}</small></div>
        </aside>
      </div>

      <section className="materials-panel materials-log-panel">
        <div className="materials-panel-heading"><div><span className="section-kicker">CHARGING EVENT LOG</span><h2>Individual Material Additions</h2></div><span>{totalAdditions} RECORDS</span></div>
        <div className="materials-table-wrap">
          <table>
            <thead><tr><th>Time</th><th>Material</th><th>Family</th><th>Quantity</th><th>Station</th><th>Batch</th><th>Source</th></tr></thead>
            <tbody>
              {(data?.additions ?? []).map((item) => <tr key={item.id}>
                <td>{formatDateTime(item.addition_time)}</td>
                <td><strong>{item.material_code}</strong><small>{item.material_name ?? ''}</small></td>
                <td><span className="material-family-pill">{materialFamily(item)}</span></td>
                <td className="material-qty">{formatNumber(item.quantity, 2)} {item.unit}</td>
                <td>{item.equipment_code ?? '—'}</td>
                <td><code>{item.batch_no ?? '—'}</code></td>
                <td>{item.source_system}</td>
              </tr>)}
            </tbody>
          </table>
          {!loading && totalAdditions === 0 && <div className="materials-table-empty">No individual additions are stored for the selected heat.</div>}
        </div>
      </section>
    </section>
  )
}
