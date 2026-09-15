import { KeyboardEvent, MouseEvent, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { authorizedFetch } from './auth'
import './system-map-telemetry-overlay.css'
import './system-map-real-plc.css'

type HistorianValue = {
  tag_name: string
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
  heat_no?: string | null
  source_kind?: string | null
  source_endpoint?: string | null
  node_id?: string | null
}

type RealPlcSnapshot = {
  area: string
  source_kind: string
  verified: boolean
  fresh: boolean
  stale_after_seconds: number
  age_seconds?: number | null
  latest_sample_at?: string | null
  source_endpoint?: string | null
  values: HistorianValue[]
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

const realPreferredTags = [
  'EAF.HeatNumber',
  'EAF.StageCode',
  'EAF.SteelTemperature',
  'EAF.PowerMW',
  'EAF.CurrentKA',
  'EAF.OxygenFlow',
  'EAF.TransformerTap',
  'EAF.Ready',
  'EAF.Running',
  'EAF.Fault',
  'EAF.ArcOn',
  'EAF.OxygenOn',
  'EAF.BurnerOn',
  'EAF.InterlockOK',
  'EAF.CoolingWaterOK',
  'EAF.HydraulicOK',
  'EAF.PLC.CycleTimeMs',
  'EAF.PLC.WatchdogOK',
  'EAF.PLC.Heartbeat',
]

const realTagLabels: Record<string, string> = {
  'EAF.HeatNumber': 'Heat Number',
  'EAF.StageCode': 'Stage Code',
  'EAF.SteelTemperature': 'Steel Temperature',
  'EAF.PowerMW': 'Power',
  'EAF.CurrentKA': 'Current',
  'EAF.OxygenFlow': 'Oxygen Flow',
  'EAF.TransformerTap': 'Transformer Tap',
  'EAF.Ready': 'Ready',
  'EAF.Running': 'Running',
  'EAF.Fault': 'Fault',
  'EAF.ArcOn': 'Arc On',
  'EAF.OxygenOn': 'Oxygen On',
  'EAF.BurnerOn': 'Burner On',
  'EAF.InterlockOK': 'Interlock',
  'EAF.CoolingWaterOK': 'Cooling Water',
  'EAF.HydraulicOK': 'Hydraulic',
  'EAF.PLC.CycleTimeMs': 'PLC Cycle Time',
  'EAF.PLC.WatchdogOK': 'Watchdog',
  'EAF.PLC.Heartbeat': 'Heartbeat',
}

function displayValue(value: HistorianValue): string {
  const raw = value.value_double ?? value.value_text
  if (raw === null || raw === undefined || raw === '') return '—'
  if (typeof raw === 'number') return raw.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return String(raw)
}

function isBooleanTag(tagName: string): boolean {
  return /(?:Ready|Running|Fault|ArcOn|OxygenOn|BurnerOn|Closed|OK|Heartbeat)$/.test(tagName)
}

function displayRealValue(value: HistorianValue): string {
  const raw = value.value_double ?? value.value_text
  if (isBooleanTag(value.tag_name)) {
    const enabled = typeof raw === 'number'
      ? raw !== 0
      : ['1', 'true', 'on', 'yes'].includes(String(raw ?? '').toLowerCase())
    return enabled ? 'ON' : 'OFF'
  }
  return displayValue(value)
}

function displayTime(value?: string | null, fractional = false): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  const base = parsed.toLocaleTimeString(undefined, { hour12: false })
  return fractional ? `${base}.${String(parsed.getMilliseconds()).padStart(3, '0')}` : base
}

function displayAge(age?: number | null): string {
  if (age === null || age === undefined || Number.isNaN(age)) return '—'
  if (age < 1) return `${Math.round(age * 1000)} ms`
  if (age < 60) return `${age.toFixed(1)} s`
  return `${Math.floor(age / 60)}m ${Math.round(age % 60)}s`
}

function chooseValues(area: string, values: HistorianValue[]): HistorianValue[] {
  const byTag = new Map(values.map((value) => [value.tag_name, value]))
  const selected = (preferredTags[area] ?? [])
    .map((tag) => byTag.get(tag))
    .filter((value): value is HistorianValue => value !== undefined)
  return selected.length > 0 ? selected : values.slice(0, 6)
}

function chooseRealValues(values: HistorianValue[]): HistorianValue[] {
  const byTag = new Map(values.map((value) => [value.tag_name, value]))
  const selected = realPreferredTags
    .map((tag) => byTag.get(tag))
    .filter((value): value is HistorianValue => value !== undefined)
  return selected.length > 0 ? selected : values.slice(0, 20)
}

function realTagLabel(tagName: string): string {
  return realTagLabels[tagName] ?? tagName.replace(/^EAF\./, '').replace(/^PLC\./, 'PLC ')
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
  const [realSnapshot, setRealSnapshot] = useState<RealPlcSnapshot | null>(null)
  const [realError, setRealError] = useState<string | null>(null)
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

    const refreshRealValues = async () => {
      try {
        const response = await authorizedFetch('/api/v1/real-plc/latest?area=EAF')
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const payload = await response.json() as RealPlcSnapshot
        if (!cancelled) {
          setRealSnapshot(payload)
          setRealError(null)
        }
      } catch (error) {
        if (!cancelled) {
          setRealError(error instanceof Error ? error.message : 'Real PLC endpoint unavailable')
        }
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refreshRealValues() }, 1000)
      }
    }

    void refreshRealValues()
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
        const realValues = controller.isReal ? chooseRealValues(realSnapshot?.values ?? []) : []
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
            <span>{controller.isReal ? 'REAL DATA' : 'LIVE DATA'}</span>
            <div className="system-map-telemetry-popup" role="dialog" aria-label={`${controller.label} diagnostics`} onClick={keepPopupOpen}>
              <header>
                <small>{controller.isReal ? 'VERIFIED PHYSICAL PLC TELEMETRY' : 'PLC LIVE TRAFFIC'}</small>
                <strong>{controller.label}</strong>
                <span>READ ONLY</span>
              </header>

              <div className="system-map-telemetry-grid">
                <section className="system-map-live-panel">
                  <div className="system-map-panel-title">
                    <strong>{controller.isReal ? 'REAL PROCESS VALUES' : 'DECODED LIVE VALUES'}</strong>
                    <small>
                      {controller.isReal
                        ? (realSnapshot?.verified ? `${realSnapshot.source_kind} · ${realSnapshot.fresh ? 'LIVE' : 'STALE'}` : 'NO VERIFIED DATA')
                        : 'Historian'}
                    </small>
                  </div>

                  {controller.isReal ? (
                    <>
                      <div className="system-map-real-summary">
                        <div><span>Endpoint</span><code>{endpoint(node)}</code></div>
                        <div><span>PLC</span><code>{node?.role ?? 'Siemens S7-400H · Rack 0 / Slot 3'}</code></div>
                        <div><span>Link</span><code>{node?.status?.toUpperCase() ?? 'UNKNOWN'}</code></div>
                        <div><span>Sample Age</span><code>{displayAge(realSnapshot?.age_seconds)}</code></div>
                      </div>

                      <div className={`system-map-real-source ${realSnapshot?.verified ? (realSnapshot.fresh ? 'fresh' : 'stale') : 'empty'}`}>
                        <div>
                          <strong>{realSnapshot?.verified ? 'PHYSICAL SOURCE VERIFIED' : 'NO REAL PROCESS DATA'}</strong>
                          <span>
                            {realSnapshot?.verified
                              ? `${realSnapshot.source_kind} · ${realSnapshot.source_endpoint ?? 'OPC UA gateway'}`
                              : (realError ?? 'Waiting for historian samples marked source_kind=REAL_S7.')}
                          </span>
                        </div>
                        <b>{realSnapshot?.verified ? (realSnapshot.fresh ? 'LIVE' : 'STALE') : 'WAITING'}</b>
                      </div>

                      <div className="system-map-telemetry-table system-map-real-values">
                        <div className="system-map-telemetry-head"><span>TAG</span><span>VALUE</span><span>Q</span><span>TIME</span></div>
                        {realValues.length > 0 ? realValues.map((value) => (
                          <div className="system-map-telemetry-row" key={value.tag_name} title={value.tag_name}>
                            <code>{realTagLabel(value.tag_name)}</code>
                            <strong>{displayRealValue(value)} {isBooleanTag(value.tag_name) ? '' : (value.engineering_unit ?? '')}</strong>
                            <span className={`quality-${(value.quality ?? 'unknown').toLowerCase()}`}>{value.quality ?? '—'}</span>
                            <time>{displayTime(value.ts)}</time>
                          </div>
                        )) : (
                          <div className="system-map-telemetry-empty">
                            Real values will appear here only after a reviewed S7 DB/tag map is connected to the physical PLC.
                          </div>
                        )}
                      </div>
                    </>
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

                  {controller.isReal && (
                    <div className="system-map-real-diagnostics">
                      <div><span>Mode</span><code>READ ONLY</code></div>
                      <div><span>Historian</span><code>{realSnapshot?.verified ? 'REAL_S7 ONLY' : 'WAITING'}</code></div>
                      <div><span>Last Sample</span><code>{displayTime(realSnapshot?.latest_sample_at, true)}</code></div>
                      <p>{node?.detail ?? 'Waiting for current connection diagnostics.'}</p>
                    </div>
                  )}
                </section>
              </div>

              <footer>
                {controller.isReal
                  ? 'Only historian samples explicitly marked source_kind=REAL_S7 are shown above. Simulator/OPC-UA test values are rejected from this panel. Raw traffic remains read-only; no Write, Force, Start, Stop, or PLC-control request is sent.'
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
