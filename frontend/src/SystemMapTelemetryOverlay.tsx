import { KeyboardEvent, MouseEvent, useEffect, useState } from 'react'
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
  phase?: string | null
}

type PacketController = {
  host?: string | null
  resolved_ip?: string | null
  packets: RawPacket[]
  read_only?: boolean
  probe_mode?: string | null
  error?: string | null
}

type PacketSnapshot = {
  available: boolean
  capture_mode: string
  generated_at?: string | null
  controllers: Record<string, PacketController>
}

type SystemNode = {
  id: string
  label: string
  role: string
  status: 'online' | 'degraded' | 'offline' | 'idle'
  detail: string
  host?: string | null
  ip?: string | null
  port?: number | null
}

type SystemMapSnapshot = {
  nodes: SystemNode[]
}

type ControllerDefinition = {
  id: string
  area: string | null
  packetKey: string
  label: string
  isReal?: boolean
}

const CONTROLLERS: ControllerDefinition[] = [
  { id: 'eaf', area: 'EAF', packetKey: 'EAF', label: 'EAF PLC / S7-400' },
  { id: 'lf', area: 'LF', packetKey: 'LF', label: 'LF PLC / S7-400' },
  { id: 'ccm', area: 'CCM', packetKey: 'CCM', label: 'CCM PLC / S7-400' },
  { id: 'real-plc', area: null, packetKey: 'REAL', label: 'REAL PLC / CPU 417-4H', isReal: true },
]

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
  return direction === 'PLC_TO_GATEWAY' ? 'PLC → LVL2' : 'LVL2 → PLC'
}

function endpoint(node?: SystemNode): string {
  if (!node) return '—'
  const address = node.ip ?? node.host ?? '—'
  return node.port ? `${address}:${node.port}` : address
}

function phaseLabel(packet: RawPacket): string {
  if (!packet.phase) return directionLabel(packet.direction)
  if (packet.phase === 'COTP_CONNECT_CONFIRM') return 'COTP CONNECT CONFIRM'
  if (packet.phase === 'S7_SETUP_COMM_ACK') return 'S7 SETUP ACK'
  return packet.phase.split('_').join(' ')
}

export function SystemMapTelemetryOverlay() {
  const [targets, setTargets] = useState<HTMLElement[]>([])
  const [valuesByArea, setValuesByArea] = useState<Record<string, HistorianValue[]>>({})
  const [packetSnapshot, setPacketSnapshot] = useState<PacketSnapshot | null>(null)
  const [nodes, setNodes] = useState<Record<string, SystemNode>>({})
  const [openId, setOpenId] = useState<string | null>(null)

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
        const areas = CONTROLLERS.flatMap((controller) => controller.area ? [controller.area] : [])
        const responses = await Promise.all(
          areas.map(async (area) => {
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

  useEffect(() => {
    if (targets.length === 0) return

    let cancelled = false
    let timer: number | null = null

    const refreshNodes = async () => {
      try {
        const response = await authorizedFetch('/api/v1/system-map')
        if (!response.ok) return
        const payload = await response.json() as SystemMapSnapshot
        if (!cancelled) setNodes(Object.fromEntries((payload.nodes ?? []).map((node) => [node.id, node])))
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refreshNodes() }, 3000)
      }
    }

    void refreshNodes()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [targets.length])

  const toggle = (id: string) => setOpenId((current) => current === id ? null : id)

  const handleKey = (event: KeyboardEvent<HTMLDivElement>, id: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      toggle(id)
    }
    if (event.key === 'Escape') setOpenId(null)
  }

  const keepPopupOpen = (event: MouseEvent<HTMLDivElement>) => event.stopPropagation()

  return (
    <>
      {CONTROLLERS.map((controller, index) => {
        const target = targets[index]
        if (!target) return null
        const values = controller.area ? chooseValues(controller.area, valuesByArea[controller.area] ?? []) : []
        const packetController = packetSnapshot?.controllers?.[controller.packetKey]
        const packets = packetController?.packets ?? []
        const latestPacket = packets[0]
        const node = nodes[controller.id]
        const isOpen = openId === controller.id

        return createPortal(
          <div
            className={`system-map-telemetry-anchor ${controller.isReal ? 'real' : ''} ${isOpen ? 'open' : ''}`}
            tabIndex={0}
            role="button"
            aria-expanded={isOpen}
            aria-label={`Open live diagnostics for ${controller.label}`}
            onClick={() => toggle(controller.id)}
            onKeyDown={(event) => handleKey(event, controller.id)}
          >
            <span>{controller.isReal ? 'RAW LINK' : 'LIVE DATA'}</span>
            <div className="system-map-telemetry-popup" role="dialog" aria-label={`${controller.label} diagnostics`} onClick={keepPopupOpen}>
              <header>
                <small>{controller.isReal ? 'REAL PLC DIAGNOSTICS' : 'PLC LIVE TRAFFIC'}</small>
                <strong>{controller.label}</strong>
                <span>READ ONLY</span>
              </header>

              <div className="system-map-telemetry-grid">
                <section className="system-map-live-panel">
                  <div className="system-map-panel-title">
                    <strong>{controller.isReal ? 'CONNECTION STATUS' : 'DECODED LIVE VALUES'}</strong>
                    <small>{controller.isReal ? (node?.status ?? 'UNKNOWN').toUpperCase() : 'Historian'}</small>
                  </div>

                  {controller.isReal ? (
                    <div className="system-map-real-diagnostics">
                      <div><span>Endpoint</span><code>{endpoint(node)}</code></div>
                      <div><span>PLC</span><code>{node?.role ?? 'Siemens S7-400H · Rack 0 / Slot 3'}</code></div>
                      <div><span>Status</span><code>{node?.status?.toUpperCase() ?? 'UNKNOWN'}</code></div>
                      <div><span>Mode</span><code>READ ONLY</code></div>
                      <p>{node?.detail ?? 'Waiting for current connection diagnostics.'}</p>
                    </div>
                  ) : (
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
                  )}
                </section>

                <section className="system-map-raw-panel">
                  <div className="system-map-panel-title">
                    <strong>{controller.isReal ? 'RAW PLC RESPONSES' : 'RAW S7 TRAFFIC'}</strong>
                    <small>{packets.length > 0 ? (controller.isReal ? 'S7 READ-ONLY LIVE' : 'TCP/102 LIVE') : packetController?.error ? 'PROBE ERROR' : 'WAITING'}</small>
                  </div>

                  <div className="system-map-packet-list">
                    {packets.length > 0 ? packets.slice(0, 4).map((packet) => (
                      <div className="system-map-packet-row" key={`${packet.sequence}-${packet.captured_at}`}>
                        <time>{displayTime(packet.captured_at, true)}</time>
                        <strong>{controller.isReal ? phaseLabel(packet) : directionLabel(packet.direction)}</strong>
                        <span>{packet.payload_length} B</span>
                      </div>
                    )) : (
                      <div className="system-map-telemetry-empty">
                        {controller.isReal
                          ? (packetController?.error ?? 'Waiting for the next read-only S7 session response from the physical PLC…')
                          : 'Waiting for TCP/102 packets…'}
                      </div>
                    )}
                  </div>

                  {latestPacket && (
                    <div className="system-map-raw-detail">
                      <div className="system-map-packet-route">
                        <span>{latestPacket.src_ip}:{latestPacket.src_port}</span>
                        <b>→</b>
                        <span>{latestPacket.dst_ip}:{latestPacket.dst_port}</span>
                      </div>
                      <div className="system-map-raw-label">
                        {controller.isReal ? `${phaseLabel(latestPacket)} · RAW RESPONSE · HEX` : 'RAW ETHERNET FRAME · HEX'}
                      </div>
                      <code className="system-map-raw-hex">{latestPacket.raw_hex || 'No frame bytes captured yet.'}</code>
                    </div>
                  )}
                </section>
              </div>

              <footer>
                {controller.isReal
                  ? 'Right side shows bytes returned by the physical PLC during read-only COTP/S7 session negotiation. No DB Read, Write, Force, Start, Stop, or PLC-control request is sent. Actual process DB bytes can be shown after a reviewed real DB/tag map is supplied.'
                  : 'Left: decoded values consumed by Level 2. Right: passive raw TCP/102 capture from the Gateway network namespace.'}
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
