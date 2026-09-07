import { useEffect, useMemo, useState } from 'react'

type Heat = {
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  started_at?: string | null
}

type ApiMeta = {
  name: string
  api_version: string
  framework?: string
  process_flow?: string[]
}

const activeStates = new Set(['CREATED', 'CHARGING', 'EAF', 'TAPPING', 'LF', 'CASTING'])

function App() {
  const [heats, setHeats] = useState<Heat[]>([])
  const [meta, setMeta] = useState<ApiMeta | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/meta').then((res) => {
        if (!res.ok) throw new Error('Metadata API unavailable')
        return res.json()
      }),
      fetch('/api/v1/heats?limit=12').then((res) => {
        if (!res.ok) throw new Error('Heat API unavailable')
        return res.json()
      }),
    ])
      .then(([metaResponse, heatResponse]) => {
        setMeta(metaResponse)
        setHeats(heatResponse)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const activeHeat = useMemo(
    () => heats.find((heat) => activeStates.has(heat.status)),
    [heats],
  )

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">STEELMAKING LEVEL 2</p>
          <h1>Production Control Dashboard</h1>
        </div>
        <div className={`health-pill ${error ? 'offline' : 'online'}`}>
          <span className="status-dot" />
          {error ? 'API Offline' : 'System Online'}
        </div>
      </header>

      <section className="process-strip">
        {(meta?.process_flow ?? ['EAF', 'LF', 'CCM']).map((stage, index, stages) => (
          <div className="process-stage" key={stage}>
            <span>{stage}</span>
            {index < stages.length - 1 && <strong>→</strong>}
          </div>
        ))}
      </section>

      {error && <div className="error-card">{error}</div>}

      <section className="stats-grid">
        <article className="metric-card">
          <span>Active Heat</span>
          <strong>{loading ? '…' : activeHeat?.heat_no ?? '—'}</strong>
          <small>{activeHeat?.status ?? 'No active heat'}</small>
        </article>
        <article className="metric-card">
          <span>Steel Grade</span>
          <strong>{activeHeat?.grade_code ?? '—'}</strong>
          <small>Current production grade</small>
        </article>
        <article className="metric-card">
          <span>Recent Heats</span>
          <strong>{loading ? '…' : heats.length}</strong>
          <small>Latest API records</small>
        </article>
        <article className="metric-card">
          <span>Platform</span>
          <strong>{meta?.api_version?.toUpperCase() ?? 'V1'}</strong>
          <small>{meta?.framework ?? 'Django REST Framework'}</small>
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">PRODUCTION</p>
            <h2>Recent Heats</h2>
          </div>
          <span>{heats.length} records</span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Heat No.</th>
                <th>Status</th>
                <th>Grade</th>
                <th>Planned Weight</th>
                <th>Actual Weight</th>
              </tr>
            </thead>
            <tbody>
              {heats.map((heat) => (
                <tr key={heat.heat_no}>
                  <td className="heat-no">{heat.heat_no}</td>
                  <td><span className="state-badge">{heat.status}</span></td>
                  <td>{heat.grade_code ?? '—'}</td>
                  <td>{heat.planned_weight_t ?? '—'} t</td>
                  <td>{heat.actual_weight_t ?? '—'} t</td>
                </tr>
              ))}
              {!loading && heats.length === 0 && (
                <tr><td colSpan={5} className="empty-state">No heat data available.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}

export default App
