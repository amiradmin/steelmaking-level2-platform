import { PropsWithChildren, useEffect, useState } from 'react'
import './license.css'

type LicenseSnapshot = {
  status: 'DEVELOPMENT' | 'ACTIVE' | 'GRACE' | 'READ_ONLY' | 'INVALID'
  read_only: boolean
  message: string
  customer?: string | null
  license_id?: string | null
  expires_at?: string | null
  grace_ends_at?: string | null
  days_remaining?: number | null
}

function dateLabel(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return parsed.toLocaleDateString()
}

export function LicenseNotice({ children }: PropsWithChildren) {
  const [license, setLicense] = useState<LicenseSnapshot | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null

    const refresh = async () => {
      try {
        const response = await fetch('/api/v1/license', { cache: 'no-store' })
        if (!response.ok) return
        const snapshot = await response.json() as LicenseSnapshot
        if (!cancelled) setLicense(snapshot)
      } catch {
        // The application must remain usable if the status endpoint is temporarily unreachable.
      } finally {
        if (!cancelled) timer = window.setTimeout(() => { void refresh() }, 60_000)
      }
    }

    void refresh()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [])

  const visible = license && license.status !== 'DEVELOPMENT'
  const tone = license?.status.toLowerCase().replace('_', '-') ?? 'active'
  const remaining = typeof license?.days_remaining === 'number'
    ? `${license.days_remaining} day${license.days_remaining === 1 ? '' : 's'}`
    : null

  return (
    <>
      {children}
      {visible && (
        <aside className={`license-notice ${tone}`} role={license.read_only ? 'alert' : 'status'}>
          <div className="license-notice-dot" aria-hidden="true" />
          <div className="license-notice-copy">
            <strong>
              {license.status === 'ACTIVE' ? 'LICENSE ACTIVE' : license.status === 'GRACE' ? 'LICENSE GRACE PERIOD' : 'READ-ONLY LICENSE MODE'}
            </strong>
            <span>{license.message}</span>
            <small>
              {license.customer ?? 'Steelmaking Level 2'}
              {remaining ? ` · ${remaining}` : ''}
              {license.expires_at ? ` · expires ${dateLabel(license.expires_at)}` : ''}
            </small>
          </div>
        </aside>
      )}
    </>
  )
}
