import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { authorizedFetch } from './auth'
import './system-map-telemetry-overlay.css'

type HistorianValue = {
  tag_name: string
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
}

const CONTROLLERS = [
  { id: 'eaf', area: 'EAF', label: 'EAF PLC / S7-400' },
  { id: 'lf', area: 'LF', label: 'LF PLC / S7-400' },
  { id: 'ccm', area: 'CCM', label: 'CCM PLC / S7-400' },
] as const

const preferredTags: Record<string, string[]> = {
  EAF: ['EAF.StageCode', 'EAF.HeatNumber', 'EAF.PowerMW', 'EAF.CurrentKA', 'EAF.OxygenFlow', 'EAF.SteelTemperature'],
  LF: ['LF.StageCode', 'LF.HeatNumber', 'LF.SteelTemperature', 'LF.ArgonFlow', 'LF.PowerMW', 'LF.CurrentKA'],
  CCM: ['CCM.StageCode', 'CCM.HeatNumber', 'CCM.CastingSpeed', 'CCM.TundishTemperature', 'CCM.MoldLevelPercent', 'CCM.TundishWeightTon'],
}

function displayValue(value: HistorianValue): string {
  const raw = value.value_double ?? value.value_text
  if (raw === null || raw === undefined || raw === '') return '—'
  if (typeof raw === 'number') return raw.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return String(raw)
}

function displayTime(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return parsed.toLocaleTimeString(undefined, { hour12: false })
}

function chooseValues(area: string, values: HistorianValue[]): HistorianValue[] {
  const byTag = new Map(values.map((value) => [value.tag_name, value]))
  const selected = (preferredTags[area] ?? [])
    .map((tag) => byTag.get(tag))
    .filter((value): value is HistorianValue => value !== undefined)
  return selected.length > 0 ? selected : values.slice(0, 6)
}

export function SystemMapTelemetryOverlay() {
  const [targets, setTargets] = useState<HTMLElement[]>([])
  const [valuesByArea, setValuesByArea] = useState<Record<string, HistorianValue[]>>({})

  useEffect(() => {
    const root = document.getElementById('root')
    if (!root) return

    const sync = () => {
      setTargets(Array.from(document.querySelectorAll<HTMLElement>('.system-map-row.plc-row .system-map-node')))
    }

    sync()
    const observer = new MutationObserver(sync)
    observer.observe(root, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const refresh = async () => {
      try {
        const responses = await Promise.all(
          CONTROLLERS.map(async ({ area }) => {
            const response = await authorizedFetch(`/api/v1/historian/latest?area=${area}`)
            if (!response.ok) return [area, []] as const
            const values = await response.json() as HistorianValue[]
            return [area, values] as const
          }),
        )
        if (!cancelled) setValuesByArea(Object.fromEntries(responses))
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

  return (
    <>
      {CONTROLLERS.map((controller, index) => {
        const target = targets[index]
        if (!target) return null
        const values = chooseValues(controller.area, valuesByArea[controller.area] ?? [])

        return createPortal(
          <div className="system-map-telemetry-anchor" tabIndex={0}>
            <span>LIVE DATA</span>
            <div className="system-map-telemetry-popup" role="tooltip">
              <header>
                <small>PLC DATA PREVIEW</small>
                <strong>{controller.label}</strong>
                <span>READ ONLY</span>
              </header>
              <div className="system-map-telemetry-table">
                <div className="system-map-telemetry-head"><span>TAG</span><span>VALUE</span><span>Q</span><span>TIME</span></div>
                {values.length > 0 ? values.map((value) => (
                  <div className="system-map-telemetry-row" key={value.tag_name}>
                    <code>{value.tag_name}</code>
                    <strong>{displayValue(value)} {value.engineering_unit ?? ''}</strong>
                    <span>{value.quality ?? '—'}</span>
                    <time>{displayTime(value.ts)}</time>
                  </div>
                )) : <div className="system-map-telemetry-empty">Waiting for historian values…</div>}
              </div>
              <footer>Latest decoded Level 1 values received by the historian.</footer>
            </div>
          </div>,
          target,
          `system-map-telemetry-${controller.id}`,
        )
      })}
    </>
  )
}
