import { useEffect, useMemo, useState } from 'react'
import { authorizedFetch } from './auth'
import { TelemetryConnectionStatus } from './telemetry'
import './system-map.css'

type HealthStatus = 'online' | 'degraded' | 'offline' | 'idle'

type SystemNode = {
  id: string
  label: string
  role: string
  status: HealthStatus
  detail: string
  last_activity: string | null
  age_seconds: number | null
  host?: string | null
  ip?: string | null
  port?: number | null
}

type SystemFlow = {
  from: string
  to: string
  status: HealthStatus
  label: string
}

type SystemMapSnapshot = {
  generated_at: string
  fresh_after_seconds: number
  nodes: SystemNode[]
  flows: SystemFlow[]
}

const statusCopy: Record<HealthStatus, string> = {
  online: 'LIVE',
  degraded: 'DEGRADED',
  offline: 'OFFLINE',
  idle: 'IDLE',
}

function elapsed(seconds: number | null): string {
  if (seconds === null) return 'no recent activity'
  if (seconds < 1) return 'just now'
  return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s ago`
}

function endpointAddress(node: SystemNode): string {
  return node.ip ?? node.host ?? '—'
}

function MapNode({ node }: { node: SystemNode }) {
  return (
    <article className={`system-map-node ${node.status}`}>
      <div className="system-map-node-top">
        <span className={`system-map-dot ${node.status}`} />
        <code>{statusCopy[node.status]}</code>
      </div>
      <strong>{node.label}</strong>
      <small>{node.role}</small>
      <div className="system-map-endpoint" aria-label={`${node.label} network endpoint`}>
        <span><b>IP</b><code>{endpointAddress(node)}</code></span>
        <span><b>PORT</b><code>{node.port ?? '—'}</code></span>
      </div>
      <p>{node.detail}</p>
      <time>{elapsed(node.age_seconds)}</time>
    </article>
  )
}

function Flow({ flow }: { flow: SystemFlow }) {
  return <span className={`system-map-flow ${flow.status}`} title={`${flow.label}: ${statusCopy[flow.status]}`}><i /><small>{flow.label}</small></span>
}

export function LiveSystemMap({ telemetryStatus }: { telemetryStatus: TelemetryConnectionStatus }) {
  const [snapshot, setSnapshot] = useState<SystemMapSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const refresh = async () => {
      try {
        const response = await authorizedFetch('/api/v1/system-map')
        if (!response.ok) throw new Error('System map endpoint is unavailable')
        const nextSnapshot = await response.json() as SystemMapSnapshot
        if (!cancelled) {
          setSnapshot(nextSnapshot)
          setError(null)
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : 'System map is unavailable')
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

  const nodeById = useMemo(() => new Map(snapshot?.nodes.map((node) => [node.id, node]) ?? []), [snapshot])
  const flowByPath = useMemo(() => new Map(snapshot?.flows.map((flow) => [`${flow.from}:${flow.to}`, flow]) ?? []), [snapshot])
  const plcIds = ['eaf', 'lf', 'ccm']
  const deliveryIds = ['heat-management', 'level2-api', 'nginx', 'operator-console']
  const isLive = telemetryStatus === 'live'

  if (!snapshot && !error) return <section className="system-map-loading"><span className="system-map-dot online" /> Loading live service map…</section>

  return (
    <section className="live-system-map" aria-live="polite">
      <header className="system-map-heading">
        <div><span className="section-kicker">LIVE PLATFORM OBSERVABILITY</span><h1>Service & Data Flow Map</h1><p>Container health and telemetry movement are refreshed every three seconds.</p></div>
        <div className={`system-map-overall ${error || !isLive ? 'degraded' : 'online'}`}><span className={`system-map-dot ${error || !isLive ? 'degraded' : 'online'}`} /><span><strong>{error ? 'MAP RETRYING' : isLive ? 'LIVE TELEMETRY' : 'WEBSOCKET RETRYING'}</strong><small>{snapshot ? `Updated ${new Date(snapshot.generated_at).toLocaleTimeString()}` : error}</small></span></div>
      </header>

      {error && <div className="system-map-error">{error}. The dashboard will retry automatically.</div>}

      {snapshot && <div className="system-map-canvas">
        <div className="system-map-row plc-row">
          {plcIds.map((id) => <MapNode key={id} node={nodeById.get(id)!} />)}
        </div>
        <div className="system-map-fan">
          {plcIds.map((id) => <Flow key={id} flow={flowByPath.get(`${id}:opcua-gateway`)!} />)}
        </div>
        <div className="system-map-row single-row"><MapNode node={nodeById.get('opcua-gateway')!} /></div>
        <Flow flow={flowByPath.get('opcua-gateway:plc-ingestor')!} />
        <div className="system-map-row single-row"><MapNode node={nodeById.get('plc-ingestor')!} /></div>
        <Flow flow={flowByPath.get('plc-ingestor:historian')!} />
        <div className="system-map-row single-row"><MapNode node={nodeById.get('historian')!} /></div>
        <div className="system-map-split"><Flow flow={flowByPath.get('historian:heat-management')!} /><Flow flow={flowByPath.get('historian:level2-api')!} /></div>
        <div className="system-map-row service-row">{deliveryIds.slice(0, 2).map((id) => <MapNode key={id} node={nodeById.get(id)!} />)}</div>
        <Flow flow={flowByPath.get('level2-api:nginx')!} />
        <div className="system-map-row single-row"><MapNode node={nodeById.get('nginx')!} /></div>
        <Flow flow={flowByPath.get('nginx:operator-console')!} />
        <div className="system-map-row single-row"><MapNode node={nodeById.get('operator-console')!} /></div>
      </div>}

      <footer className="system-map-legend"><span><i className="system-map-dot online" /> Live / healthy</span><span><i className="system-map-dot degraded" /> Delayed or reconnecting</span><span><i className="system-map-dot offline" /> No current signal</span><span>Each node shows its current resolved IP and listening port. Flow arrows show actual freshest telemetry and service probes.</span></footer>
    </section>
  )
}
