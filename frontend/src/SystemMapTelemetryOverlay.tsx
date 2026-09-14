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

type RawPacket = {
  sequence: number
  captured_at: string
  controller: string
  direction: 'PLC_TO_GATEWAY' | 'GATEWAY_TO_PLC'
  src_ip: string
  src_port: number
  dst_ip: string
  dst_port: number
  payload_length: number
  protocol: string
  raw_hex: string
}

type PacketController = {
  host?: string | null
  resolved_ip?: string | null
  packets: RawPacket[]
}

type PacketSnapshot = {
  available: boolean
  capture_mode: string
  generated_at?: string | null
  controllers: Record<string, PacketController>
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

function displayTime(value?: string | null, fractional = false): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  const base = parsed.toLocaleTimeString(undefined, { hour12: false })
  return fractional ? `${base}.${String(parsed.getMilliseconds()).padStart(3, '0')}` : base
}

function chooseValues(area: string, values: HistorianValue[]): HistorianValue[] {
  const byTag = new Map(values.map((value) => [value.tag_name, value]))
  const selected = (preferredTags[area] ?? [])
    .map((tag) => byTag.get(tag))
    .filter((value): value is HistorianValue => value !== undefined)
  return selected.length > 0 ? selected : values.slice(0, 6)
}

function directionLabel(direction: RawPacket['direction']): string {
  return direction === 'PLC_TO_GATEWAY' ? 'PLC → GW' : 'GW → PLC'
}

export function SystemMapTelemetryOverlay() {
  const [targets, setTargets] = useState<HTMLElement[]>([])
  const [valuesByArea, setValuesByArea] = useState<Record<string, HistorianValue[]>>({})
  const [packetSnapshot, setPacketSnapshot] = useState<PacketSnapshot | null>(null)

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
    if (targets.length === 0) return

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
  }, [targets.length])

  useEffect(() => {
    if (targets.length === 0) return

    let cancelled = false
    let timer: number | null = null

    const refreshPackets = async () => {
      try {
        const response = await authorizedFetch('/api/v1/plc-packets?limit=6')
        if (!response.ok) return
        const payload = await response.json() as PacketSnapshot
        if (!cancelled) setPacketSnapshot(payload)
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refreshPackets() }, 1000)
      }
    }

    void refreshPackets()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [targets.length])

  return (
    <>
      {CONTROLLERS.map((controller, index) => {
        const target = targets[index]
        if (!target) return null
        const values = chooseValues(controller.area, valuesByArea[controller.area] ?? [])
        const packetController = packetSnapshot?.controllers?.[controller.area]
        const packets = packetController?.packets ?? []
        const latestPacket = packets[0]

        return createPortal(
          <div className="system-map-telemetry-anchor" tabIndex={0}>
            <span>LIVE DATA</span>
            <div className="system-map-telemetry-popup" role="tooltip">
              <header>
                <small>PLC LIVE TRAFFIC</small>
                <strong>{controller.label}</strong>
                <span>READ ONLY</span>
              </header>

              <div className="system-map-telemetry-grid">
                <section className="system-map-live-panel">
                  <div className="system-map-panel-title"><strong>DECODED LIVE VALUES</strong><small>Historian</small></div>
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
                </section>

                <section className="system-map-raw-panel">
                  <div className="system-map-panel-title">
                    <strong>RAW S7 TRAFFIC</strong>
                    <small>{packetSnapshot?.available ? 'TCP/102 LIVE' : 'WARMING UP'}</small>
                  </div>

                  <div className="system-map-packet-list">
                    {packets.length > 0 ? packets.slice(0, 4).map((packet) => (
                      <div className="system-map-packet-row" key={packet.sequence}>
                        <time>{displayTime(packet.captured_at, true)}</time>
                        <strong>{directionLabel(packet.direction)}</strong>
                        <span>{packet.payload_length} B</span>
                      </div>
                    )) : <div className="system-map-telemetry-empty">Waiting for TCP/102 packets…</div>}
                  </div>

                  {latestPacket && (
                    <div className="system-map-raw-detail">
                      <div className="system-map-packet-route">
                        <span>{latestPacket.src_ip}:{latestPacket.src_port}</span>
                        <b>→</b>
                        <span>{latestPacket.dst_ip}:{latestPacket.dst_port}</span>
                      </div>
                      <div className="system-map-raw-label">RAW ETHERNET FRAME · HEX</div>
                      <code className="system-map-raw-hex">{latestPacket.raw_hex || 'No frame bytes captured yet.'}</code>
                    </div>
                  )}
                </section>
              </div>

              <footer>
                Left: decoded values consumed by Level 2. Right: passive raw TCP/102 capture from the Gateway network namespace.
              </footer>
            </div>
          </div>,
          target,
          `system-map-telemetry-${controller.id}`,
        )
      })}
    </>
  )
}
