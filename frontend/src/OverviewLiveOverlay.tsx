import { useEffect, useRef } from 'react'
import { authorizedFetch } from './auth'

type Station = {
  area: 'EAF' | 'LF' | 'CCM'
  stage_code: number
  stage_name?: string | null
  state: 'active' | 'complete' | 'ready' | 'standby'
  progress_percent?: number | null
  elapsed_seconds?: number | null
  planned_seconds?: number | null
}

type TrendPoint = { ts: string; value: number }
type RecentHeat = {
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  peak_eaf_temperature?: number | null
}

type OverviewLive = {
  generated_at: string
  process_heat_number?: number | null
  active_area?: 'EAF' | 'LF' | 'CCM' | null
  heat?: { heat_no?: string; grade_code?: string | null } | null
  stations: Station[]
  temperature: { tag_name: string; value?: number | null; quality?: string | null }
  latest: Record<string, number | null>
  kpis: {
    tap_to_tap_minutes?: number | null
    current_eaf_elapsed_minutes?: number | null
    eaf_energy_kwh?: number | null
    specific_energy_kwh_t?: number | null
    reference_weight_t?: number | null
    reference_weight_source?: string | null
    charged_weight_t?: number | null
    actual_weight_t?: number | null
    yield_percent?: number | null
    critical_alarm_count: number
  }
  trend: { wall_window_seconds: number; series: Record<string, TrendPoint[]> }
  recent_heats: RecentHeat[]
}

function num(value: number | null | undefined, digits = 1): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function clock(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number') return '—'
  const value = Math.max(0, Math.round(seconds))
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`
}

function setText(element: Element | null | undefined, value: string) {
  if (element && element.textContent !== value) element.textContent = value
}

function directChild(root: Element, selector: string): Element | null {
  return Array.from(root.children).find((child) => child.matches(selector)) ?? null
}

function station(data: OverviewLive, area: string): Station | undefined {
  return data.stations.find((item) => item.area === area)
}

function stageLabel(value?: Station): string {
  if (!value) return 'NO DATA'
  if (value.state === 'active') return value.stage_name ?? `Stage ${value.stage_code}`
  if (value.state === 'complete') return 'Complete'
  if (value.state === 'ready') return 'Ready'
  return 'Standby'
}

function heatNumber(data: OverviewLive): string {
  if (typeof data.process_heat_number === 'number') return String(data.process_heat_number)
  return data.heat?.heat_no ?? '—'
}

function trendDefinitions(area: OverviewLive['active_area']) {
  if (area === 'LF') return [
    ['LF.SteelTemperature', 'Steel Temperature (°C)', 'temperature'],
    ['LF.ArgonFlow', 'Argon Flow (NL/min)', 'argon'],
  ] as const
  if (area === 'CCM') return [
    ['CCM.TundishTemperature', 'Tundish Temperature (°C)', 'temperature'],
    ['CCM.CastingSpeed', 'Casting Speed (m/min)', 'power'],
  ] as const
  return [
    ['EAF.SteelTemperature', 'Steel Temperature (°C)', 'temperature'],
    ['EAF.PowerMW', 'Electrical Power (MW)', 'power'],
    ['EAF.OxygenFlow', 'Oxygen Flow (Nm³/h)', 'argon'],
  ] as const
}

function svgPath(points: TrendPoint[], startMs: number, endMs: number): string {
  const valid = points
    .map((point) => ({ x: Date.parse(point.ts), y: point.value }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
  if (valid.length < 2 || endMs <= startMs) return ''
  const values = valid.map((point) => point.y)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(0.0001, max - min)
  return valid.map((point, index) => {
    const x = Math.max(0, Math.min(760, (point.x - startMs) / (endMs - startMs) * 760))
    const y = 10 + (1 - (point.y - min) / span) * 190
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
}

function applyKpis(data: OverviewLive) {
  const cards = Array.from(document.querySelectorAll<HTMLElement>('.kpi-grid .kpi-card'))
  if (cards.length < 6) return
  const active = data.active_area ? station(data, data.active_area) : undefined
  setText(directChild(cards[0], 'strong'), `#${heatNumber(data)}`)
  setText(directChild(cards[0], 'small'), `Grade: ${data.heat?.grade_code ?? '—'} · ${data.active_area ?? 'WAITING'}`)
  setText(directChild(cards[1], 'strong'), data.active_area ?? '—')
  setText(directChild(cards[1], 'small'), `${stageLabel(active)} · ${active?.state === 'active' ? 'RUNNING' : 'IDLE'}`)
  setText(directChild(cards[2], 'strong'), `${num(data.kpis.tap_to_tap_minutes, 1)} min`)
  setText(directChild(cards[2], 'small'), data.kpis.tap_to_tap_minutes == null ? `Collecting completed cycle · current EAF ${num(data.kpis.current_eaf_elapsed_minutes, 1)} min` : 'Last completed cycle · Historian')
  setText(directChild(cards[3], 'strong'), `${num(data.temperature.value, 1)} °C`)
  setText(directChild(cards[3], 'small'), `${data.temperature.tag_name} · ${data.temperature.quality ?? 'NO DATA'}`)
  setText(directChild(cards[4], 'strong'), `${num(data.kpis.specific_energy_kwh_t, 1)} kWh/t`)
  setText(directChild(cards[4], 'small'), data.kpis.eaf_energy_kwh == null ? 'Collecting EAF power samples' : `${num(data.kpis.eaf_energy_kwh, 0)} kWh integrated · ${num(data.kpis.reference_weight_t, 1)} t basis · ${data.kpis.reference_weight_source ?? 'COLLECTING'}`)
  setText(directChild(cards[5], 'strong'), `${num(data.kpis.yield_percent, 2)} %`)
  setText(directChild(cards[5], 'small'), data.kpis.yield_percent == null ? `Collecting charged/output mass · ${data.kpis.critical_alarm_count} critical alarms` : `${num(data.kpis.actual_weight_t, 2)} t / ${num(data.kpis.charged_weight_t, 2)} t · ${data.kpis.critical_alarm_count} critical alarms`)
}

function applyProcessCards(data: OverviewLive) {
  const cards = Array.from(document.querySelectorAll<HTMLElement>('.process-flow .process-card'))
  ;(['EAF', 'LF', 'CCM'] as const).forEach((area, index) => {
    const card = cards[index]
    const current = station(data, area)
    if (!card || !current) return
    card.classList.toggle('current', current.state === 'active')
    setText(card.querySelector('.status-badge'), stageLabel(current))
    setText(directChild(card, 'code'), `${area}-01 · ${current.state === 'active' ? `HEAT #${heatNumber(data)}` : stageLabel(current).toUpperCase()}`)
    const dd = card.querySelectorAll('dl dd')
    if (area === 'EAF') {
      setText(dd[0], stageLabel(current))
      setText(dd[1], `${num(data.latest['EAF.PowerMW'], 1)} MW`)
    } else if (area === 'LF') {
      setText(dd[0], `${num(data.latest['LF.SteelTemperature'], 1)} °C`)
      setText(dd[1], `${num(data.latest['LF.ArgonFlow'], 1)} NL/min`)
    } else {
      setText(dd[0], `${num(data.latest['CCM.CastingSpeed'], 2)} m/min`)
      setText(dd[1], `${num(data.latest['CCM.TundishTemperature'], 1)} °C`)
    }
    const progress = current.progress_percent ?? (current.state === 'complete' ? 100 : 0)
    const bar = card.querySelector<HTMLElement>('.progress span')
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, progress))}%`
    setText(directChild(card, 'small'), current.state === 'active' ? `${stageLabel(current)} · ${clock(current.elapsed_seconds)} / ${clock(current.planned_seconds)} · ${num(progress, 0)}% · Historian` : `${stageLabel(current)} · Historian`)
  })
}

function applyTrend(data: OverviewLive) {
  const panel = document.querySelector<HTMLElement>('.trend-panel')
  if (!panel) return
  const definitions = trendDefinitions(data.active_area)
  const legend = panel.querySelectorAll<HTMLElement>('.chart-legend span')
  definitions.forEach((definition, index) => setText(legend[index], definition[1]))
  for (let index = definitions.length; index < legend.length; index += 1) setText(legend[index], '')
  const endMs = Date.parse(data.generated_at)
  const startMs = endMs - data.trend.wall_window_seconds * 1000
  const paths = {
    temperature: panel.querySelector<SVGPathElement>('.trend-line.temperature'),
    power: panel.querySelector<SVGPathElement>('.trend-line.power'),
    argon: panel.querySelector<SVGPathElement>('.trend-line.argon'),
  }
  Object.values(paths).forEach((path) => path?.setAttribute('d', ''))
  definitions.forEach(([tag, , tone]) => paths[tone]?.setAttribute('d', svgPath(data.trend.series[tag] ?? [], startMs, endMs)))
  const metrics = panel.querySelectorAll<HTMLElement>('.live-metrics > div')
  if (metrics.length >= 4) {
    setText(metrics[0].querySelector('strong'), `${num(data.temperature.value, 1)} °C`)
    setText(metrics[0].querySelector('em'), data.temperature.tag_name)
    setText(metrics[1].querySelector('strong'), `${num(data.latest['LF.ArgonFlow'], 1)} NL/min`)
    setText(metrics[2].querySelector('strong'), `${num(data.latest['EAF.PowerMW'], 1)} MW`)
    setText(metrics[3].querySelector('strong'), `${num(data.latest['CCM.CastingSpeed'], 2)} m/min`)
  }
  const zoom = panel.querySelector<HTMLButtonElement>('.outline-button')
  if (zoom) { setText(zoom, 'LIVE 60 MIN'); zoom.disabled = true }
}

function applyRecentHeats(data: OverviewLive) {
  const panel = document.querySelector<HTMLElement>('.heats-panel')
  if (!panel) return
  const headers = panel.querySelectorAll('thead th')
  setText(headers[4], 'Peak EAF Temperature')
  const rows = Array.from(panel.querySelectorAll<HTMLTableRowElement>('tbody tr'))
  rows.forEach((row, index) => {
    const heat = data.recent_heats[index]
    if (!heat) { row.style.display = 'none'; return }
    row.style.display = ''
    const cells = row.querySelectorAll('td')
    setText(cells[0], `#${heat.heat_no}`)
    setText(cells[1], heat.grade_code ?? '—')
    setText(cells[2], 'EAF1 › LF1 › CCM1')
    setText(cells[3], heat.actual_weight_t != null ? `${num(heat.actual_weight_t, 1)} t` : heat.planned_weight_t != null ? `${num(heat.planned_weight_t, 1)} t planned` : '—')
    setText(cells[4], `${num(heat.peak_eaf_temperature, 1)} °C`)
    setText(cells[5], heat.status)
  })
}

function applyOverview(data: OverviewLive) {
  applyKpis(data)
  applyProcessCards(data)
  applyTrend(data)
  applyRecentHeats(data)
}

export function OverviewLiveOverlay() {
  const latest = useRef<OverviewLive | null>(null)
  useEffect(() => {
    let cancelled = false
    let timer: number | null = null
    const refresh = async () => {
      try {
        const response = await authorizedFetch('/api/v1/overview-live')
        if (!response.ok) return
        const data = await response.json() as OverviewLive
        latest.current = data
        if (!cancelled) applyOverview(data)
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refresh() }, 3000)
      }
    }
    void refresh()
    return () => { cancelled = true; if (timer !== null) window.clearTimeout(timer) }
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (latest.current) applyOverview(latest.current)
    }, 500)
    return () => window.clearInterval(timer)
  }, [])
  return null
}
