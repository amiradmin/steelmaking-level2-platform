import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import './data-historian.css'

type LatestValue = {
  tag_name: string
  equipment_code?: string | null
  area?: string | null
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
  heat_no?: string | null
}

type TagMeta = {
  tag_name: string
  engineering_unit?: string | null
  data_type?: string | null
  sampling_mode?: string | null
  expected_period_ms?: number | null
}

type Sample = {
  ts: string
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  heat_no?: string | null
}

type SampleResponse = {
  tag: TagMeta
  samples: Sample[]
}

type RangeKey = '15m' | '1h' | '4h' | '24h'

const RANGE_MINUTES: Record<RangeKey, number> = {
  '15m': 15,
  '1h': 60,
  '4h': 240,
  '24h': 1440,
}

function formatValue(value?: number | null, text?: string | null, digits = 2): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toLocaleString(undefined, { maximumFractionDigits: digits })
  }
  return text ?? '—'
}

function formatClock(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function sampleAge(value?: string | null): string {
  if (!value) return '—'
  const ts = new Date(value).getTime()
  if (!Number.isFinite(ts)) return '—'
  const age = Math.max(0, (Date.now() - ts) / 1000)
  if (age < 60) return `${age.toFixed(1)} s`
  if (age < 3600) return `${Math.floor(age / 60)} min`
  return `${(age / 3600).toFixed(1)} h`
}

function numericSamples(samples: Sample[]): Array<{ ts: string; value: number }> {
  return samples
    .filter((sample): sample is Sample & { value_double: number } => typeof sample.value_double === 'number' && Number.isFinite(sample.value_double))
    .map((sample) => ({ ts: sample.ts, value: sample.value_double }))
    .reverse()
}

function TrendChart({ samples, unit }: { samples: Sample[]; unit?: string | null }) {
  const points = numericSamples(samples)
  if (points.length < 2) {
    return <div className="historian-chart-empty">Waiting for enough numeric historian samples…</div>
  }

  const values = points.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const padding = Math.max((max - min) * 0.08, Math.abs(max) * 0.003, 0.01)
  const lo = min - padding
  const hi = max + padding
  const range = Math.max(hi - lo, 0.000001)
  const polyline = points
    .map((point, index) => {
      const x = 48 + (index / (points.length - 1)) * 902
      const y = 24 + (1 - (point.value - lo) / range) * 226
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')

  const last = points[points.length - 1]
  const lastX = 950
  const lastY = 24 + (1 - (last.value - lo) / range) * 226
  const yTicks = [hi, lo + range * 0.75, lo + range * 0.5, lo + range * 0.25, lo]
  const xTicks = [0, 0.25, 0.5, 0.75, 1]
  const startTs = new Date(points[0].ts).getTime()
  const endTs = new Date(last.ts).getTime()

  return (
    <div className="historian-chart-wrap">
      <svg className="historian-chart" viewBox="0 0 1000 300" preserveAspectRatio="none" role="img" aria-label="Historian trend">
        <g className="historian-grid-lines">
          {[24, 80.5, 137, 193.5, 250].map((y) => <line key={`y-${y}`} x1="48" y1={y} x2="950" y2={y} />)}
          {[48, 273.5, 499, 724.5, 950].map((x) => <line key={`x-${x}`} x1={x} y1="24" x2={x} y2="250" />)}
        </g>
        <polyline className="historian-trend-line" points={polyline} />
        <circle className="historian-trend-now" cx={lastX} cy={lastY} r="5" />
        {yTicks.map((tick, index) => (
          <text className="historian-axis-label" x="42" y={29 + index * 56.5} textAnchor="end" key={`yt-${index}`}>{formatValue(tick, null, 2)}</text>
        ))}
        {xTicks.map((fraction, index) => {
          const ts = startTs + (endTs - startTs) * fraction
          return <text className="historian-axis-label" x={48 + fraction * 902} y="278" textAnchor={index === 0 ? 'start' : index === 4 ? 'end' : 'middle'} key={`xt-${index}`}>{formatClock(new Date(ts).toISOString())}</text>
        })}
        {unit && <text className="historian-unit-label" x="952" y="17" textAnchor="end">{unit}</text>}
      </svg>
    </div>
  )
}

export function DataHistorian() {
  const [latest, setLatest] = useState<LatestValue[]>([])
  const [selectedTag, setSelectedTag] = useState('')
  const [range, setRange] = useState<RangeKey>('1h')
  const [samplePayload, setSamplePayload] = useState<SampleResponse | null>(null)
  const [search, setSearch] = useState('')
  const [area, setArea] = useState('ALL')
  const [quality, setQuality] = useState('ALL')
  const [loadingCatalog, setLoadingCatalog] = useState(true)
  const [loadingSamples, setLoadingSamples] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [, setTick] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const loadCatalog = async () => {
      try {
        const response = await authorizedFetch('/api/v1/historian/latest')
        if (!response.ok) throw new Error(`Historian catalog returned ${response.status}`)
        const payload = await response.json() as LatestValue[]
        if (!cancelled) {
          setLatest(payload)
          setSelectedTag((current) => {
            if (current && payload.some((item) => item.tag_name === current)) return current
            return payload.find((item) => item.tag_name === 'EAF.PowerMW')?.tag_name ?? payload[0]?.tag_name ?? ''
          })
          setLoadingCatalog(false)
          setError(null)
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : 'Historian catalog unavailable')
          setLoadingCatalog(false)
        }
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void loadCatalog() }, 5000)
      }
    }

    void loadCatalog()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (!selectedTag) return
    let cancelled = false
    let timer: number | null = null

    const loadSamples = async () => {
      setLoadingSamples(true)
      try {
        const end = new Date()
        const start = new Date(end.getTime() - RANGE_MINUTES[range] * 60_000)
        const query = new URLSearchParams({
          start: start.toISOString(),
          end: end.toISOString(),
          limit: range === '24h' ? '5000' : '1800',
        })
        const response = await authorizedFetch(`/api/v1/historian/tags/${encodeURIComponent(selectedTag)}/samples?${query.toString()}`)
        if (!response.ok) throw new Error(`Historian samples returned ${response.status}`)
        const payload = await response.json() as SampleResponse
        if (!cancelled) {
          setSamplePayload(payload)
          setError(null)
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'Historian samples unavailable')
      } finally {
        if (!cancelled) {
          setLoadingSamples(false)
          timer = window.setTimeout(() => { void loadSamples() }, 5000)
        }
      }
    }

    void loadSamples()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [selectedTag, range])

  const areas = useMemo(() => ['ALL', ...Array.from(new Set(latest.map((item) => item.area).filter((item): item is string => Boolean(item)))).sort()], [latest])
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return latest.filter((item) => {
      if (area !== 'ALL' && item.area !== area) return false
      if (quality !== 'ALL' && (item.quality ?? 'UNKNOWN').toUpperCase() !== quality) return false
      if (!needle) return true
      return [item.tag_name, item.equipment_code, item.area, item.engineering_unit, item.heat_no]
        .some((value) => String(value ?? '').toLowerCase().includes(needle))
    })
  }, [latest, search, area, quality])

  const selectedLatest = latest.find((item) => item.tag_name === selectedTag)
  const samples = samplePayload?.samples ?? []
  const numeric = numericSamples(samples)
  const numbers = numeric.map((sample) => sample.value)
  const goodCount = samples.filter((sample) => (sample.quality ?? '').toUpperCase() === 'GOOD').length
  const badCount = samples.length - goodCount
  const min = numbers.length ? Math.min(...numbers) : null
  const max = numbers.length ? Math.max(...numbers) : null
  const avg = numbers.length ? numbers.reduce((sum, value) => sum + value, 0) / numbers.length : null
  const latestSample = samples[0]
  const unit = samplePayload?.tag.engineering_unit ?? selectedLatest?.engineering_unit

  const qualityCounts = useMemo(() => {
    const counts = new Map<string, number>()
    latest.forEach((item) => {
      const key = (item.quality ?? 'UNKNOWN').toUpperCase()
      counts.set(key, (counts.get(key) ?? 0) + 1)
    })
    return counts
  }, [latest])

  return (
    <section className="historian-page">
      <header className="historian-heading">
        <div>
          <span className="section-kicker">TIMESCALEDB · PROCESS HISTORY</span>
          <h1>Data Historian</h1>
          <p>Browse live Level 2 tags, inspect data quality, trend process values, and review raw samples.</p>
        </div>
        <div className="historian-live-state">
          <span className={`historian-live-dot ${error ? 'warning' : ''}`} />
          <span><strong>{error ? 'HISTORIAN DEGRADED' : 'HISTORIAN LIVE'}</strong><small>{latest.length} current tags · auto refresh 5 s</small></span>
        </div>
      </header>

      {error && <div className="historian-error">{error}. Last valid historian data remains visible.</div>}

      <section className="historian-summary-grid">
        <article><span>ACTIVE TAGS</span><strong>{latest.length}</strong><small>EAF / LF / CCM / system</small></article>
        <article><span>GOOD QUALITY</span><strong className="good">{qualityCounts.get('GOOD') ?? 0}</strong><small>latest values</small></article>
        <article><span>NON-GOOD</span><strong className={(latest.length - (qualityCounts.get('GOOD') ?? 0)) > 0 ? 'bad' : ''}>{latest.length - (qualityCounts.get('GOOD') ?? 0)}</strong><small>bad / uncertain / unknown</small></article>
        <article><span>SELECTED TAG</span><strong className="tag-name">{selectedTag || '—'}</strong><small>{selectedLatest?.equipment_code ?? 'No equipment'} · {selectedLatest?.area ?? '—'}</small></article>
        <article><span>LATEST VALUE</span><strong>{formatValue(selectedLatest?.value_double, selectedLatest?.value_text, 3)} {unit ?? ''}</strong><small>{selectedLatest?.quality ?? '—'}</small></article>
        <article><span>SAMPLE AGE</span><strong>{sampleAge(selectedLatest?.ts)}</strong><small>{formatClock(selectedLatest?.ts)}</small></article>
      </section>

      <div className="historian-workspace">
        <aside className="historian-tag-browser">
          <div className="historian-panel-title"><div><span className="section-kicker">TAG BROWSER</span><h2>Process Tags</h2></div><b>{filtered.length}</b></div>
          <input className="historian-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search tag, area, equipment…" />
          <div className="historian-filter-row">
            <select value={area} onChange={(event) => setArea(event.target.value)} aria-label="Filter by area">
              {areas.map((item) => <option value={item} key={item}>{item === 'ALL' ? 'All areas' : item}</option>)}
            </select>
            <select value={quality} onChange={(event) => setQuality(event.target.value)} aria-label="Filter by quality">
              <option value="ALL">All quality</option>
              <option value="GOOD">GOOD</option>
              <option value="UNCERTAIN">UNCERTAIN</option>
              <option value="BAD">BAD</option>
              <option value="UNKNOWN">UNKNOWN</option>
            </select>
          </div>
          <div className="historian-tag-list">
            {loadingCatalog && latest.length === 0 ? <div className="historian-empty">Loading historian tags…</div> : filtered.map((item) => (
              <button type="button" className={selectedTag === item.tag_name ? 'selected' : ''} key={item.tag_name} onClick={() => setSelectedTag(item.tag_name)}>
                <span className={`historian-quality-dot q-${(item.quality ?? 'unknown').toLowerCase()}`} />
                <span><strong>{item.tag_name}</strong><small>{item.area ?? '—'} · {item.equipment_code ?? '—'} · {sampleAge(item.ts)} ago</small></span>
                <span className="historian-tag-value"><b>{formatValue(item.value_double, item.value_text, 2)}</b><small>{item.engineering_unit ?? ''}</small></span>
              </button>
            ))}
            {!loadingCatalog && filtered.length === 0 && <div className="historian-empty">No tags match the current filters.</div>}
          </div>
        </aside>

        <div className="historian-main">
          <section className="historian-panel historian-trend-panel">
            <div className="historian-panel-title historian-trend-heading">
              <div><span className="section-kicker">TREND EXPLORER</span><h2>{selectedTag || 'Select a tag'}</h2><small>{samplePayload?.tag.data_type ?? '—'} · {samplePayload?.tag.sampling_mode ?? '—'} · expected {samplePayload?.tag.expected_period_ms ?? '—'} ms</small></div>
              <div className="historian-range-buttons">
                {(Object.keys(RANGE_MINUTES) as RangeKey[]).map((key) => <button type="button" className={range === key ? 'active' : ''} key={key} onClick={() => setRange(key)}>{key.toUpperCase()}</button>)}
              </div>
            </div>
            <TrendChart samples={samples} unit={unit} />
            <div className="historian-stats">
              <div><span>MIN</span><strong>{formatValue(min, null, 3)}</strong></div>
              <div><span>MAX</span><strong>{formatValue(max, null, 3)}</strong></div>
              <div><span>AVG</span><strong>{formatValue(avg, null, 3)}</strong></div>
              <div><span>SAMPLES</span><strong>{samples.length}</strong></div>
              <div><span>GOOD</span><strong className="good">{goodCount}</strong></div>
              <div><span>NON-GOOD</span><strong className={badCount ? 'bad' : ''}>{badCount}</strong></div>
            </div>
          </section>

          <section className="historian-panel historian-sample-panel">
            <div className="historian-panel-title">
              <div><span className="section-kicker">RAW SAMPLE VIEW</span><h2>Historian Samples</h2></div>
              <span className="historian-readonly">READ ONLY · {loadingSamples ? 'REFRESHING' : 'LIVE'}</span>
            </div>
            <div className="historian-table-wrap">
              <table>
                <thead><tr><th>Timestamp</th><th>Value</th><th>Unit</th><th>Quality</th><th>Heat</th></tr></thead>
                <tbody>
                  {samples.slice(0, 200).map((sample, index) => (
                    <tr key={`${sample.ts}-${index}`}>
                      <td><time>{formatDateTime(sample.ts)}</time></td>
                      <td className="historian-number">{formatValue(sample.value_double, sample.value_text, 4)}</td>
                      <td>{unit ?? '—'}</td>
                      <td><span className={`historian-quality-chip q-${(sample.quality ?? 'unknown').toLowerCase()}`}>{sample.quality ?? 'UNKNOWN'}</span></td>
                      <td>{sample.heat_no ?? '—'}</td>
                    </tr>
                  ))}
                  {!samples.length && <tr><td colSpan={5} className="historian-table-empty">No samples in the selected time window.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="historian-table-footer">
              <span>Latest: <strong>{formatValue(latestSample?.value_double, latestSample?.value_text, 4)} {unit ?? ''}</strong></span>
              <span>Timestamp: <strong>{formatDateTime(latestSample?.ts)}</strong></span>
              <span>Showing: <strong>{Math.min(samples.length, 200)} / {samples.length}</strong></span>
            </div>
          </section>
        </div>
      </div>
    </section>
  )
}
