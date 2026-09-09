import { AuthenticationExpiredError, authorizedFetch, loadTokens } from './auth'

export type TelemetryConnectionStatus = 'connecting' | 'live' | 'disconnected'

export type TelemetryHeat = {
  id: string
  heat_no: string
  status: string
  grade_code?: string | null
  planned_weight_t?: number | null
  actual_weight_t?: number | null
  started_at?: string | null
  updated_at?: string | null
}

export type TelemetryValue = {
  tag_name: string
  equipment_code?: string | null
  area?: string | null
  engineering_unit?: string | null
  value_double?: number | null
  value_text?: string | null
  quality?: string | null
  ts?: string | null
}

export type TelemetryAlarm = {
  alarm_code: string
  severity: string
  state: string
  message: string
  equipment_code?: string | null
  active_at?: string | null
  acknowledged_at?: string | null
}

export type TelemetrySnapshot = {
  server_time: string
  active_heat: TelemetryHeat | null
  live_values: TelemetryValue[]
  active_alarms: TelemetryAlarm[]
  recent_events: Array<Record<string, unknown>>
  l1_link: {
    online: boolean
    age_seconds: number | null
    last_sample_at: string | null
  }
}

type TelemetryEnvelope =
  | { type: 'telemetry.snapshot'; data: TelemetrySnapshot }
  | { type: 'telemetry.error'; detail?: string }

export type TelemetrySubscriptionOptions = {
  onSnapshot: (snapshot: TelemetrySnapshot) => void
  onStatus?: (status: TelemetryConnectionStatus) => void
  onAuthenticationExpired?: () => void
}

function websocketUrl(): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/ws/v1/telemetry`
}

export function subscribeRealtimeTelemetry(options: TelemetrySubscriptionOptions): () => void {
  let stopped = false
  let socket: WebSocket | null = null
  let reconnectTimer: number | null = null
  let attempt = 0

  const setStatus = (status: TelemetryConnectionStatus) => options.onStatus?.(status)

  const scheduleReconnect = () => {
    if (stopped) return
    const delay = Math.min(10_000, 750 * 2 ** Math.min(attempt, 4))
    attempt += 1
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      void connect()
    }, delay)
  }

  const connect = async () => {
    if (stopped) return
    setStatus('connecting')

    try {
      // This also refreshes an expired access token before a reconnect.
      const authResponse = await authorizedFetch('/api/v1/auth/me')
      if (!authResponse.ok) throw new Error('Authentication check failed')
    } catch (error) {
      if (error instanceof AuthenticationExpiredError) {
        options.onAuthenticationExpired?.()
        return
      }
      setStatus('disconnected')
      scheduleReconnect()
      return
    }

    const accessToken = loadTokens()?.access
    if (!accessToken) {
      options.onAuthenticationExpired?.()
      return
    }

    socket = new WebSocket(websocketUrl(), ['level2.jwt', accessToken])

    socket.onopen = () => {
      attempt = 0
      setStatus('live')
    }

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as TelemetryEnvelope
        if (message.type === 'telemetry.snapshot') {
          options.onSnapshot(message.data)
        }
      } catch {
        // Ignore malformed telemetry frames and keep the stream connected.
      }
    }

    socket.onerror = () => {
      setStatus('disconnected')
    }

    socket.onclose = () => {
      socket = null
      if (stopped) return
      setStatus('disconnected')
      scheduleReconnect()
    }
  }

  void connect()

  return () => {
    stopped = true
    if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
    socket?.close(1000, 'dashboard unmounted')
    socket = null
  }
}
