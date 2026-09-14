import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { authorizedFetch } from './auth'
import { ReportsAnalytics } from './ReportsAnalytics'
import './reports-navigation-bridge.css'

const REPORTS_LABEL = 'Reports & Analytics'
const PANEL_QUERY_KEY = 'panel'
const REPORTS_QUERY_VALUE = 'reports'

function findDashboardContent(): HTMLElement | null {
  return document.querySelector<HTMLElement>('.dashboard-content')
}

function findReportsButton(): HTMLButtonElement | null {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.side-nav button'))
  return buttons.find((button) => button.textContent?.includes(REPORTS_LABEL)) ?? null
}

function setReportsQuery(enabled: boolean): void {
  const url = new URL(window.location.href)
  if (enabled) {
    url.searchParams.set(PANEL_QUERY_KEY, REPORTS_QUERY_VALUE)
  } else if (url.searchParams.get(PANEL_QUERY_KEY) === REPORTS_QUERY_VALUE) {
    url.searchParams.delete(PANEL_QUERY_KEY)
  } else {
    return
  }
  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
}

function initialOpenState(): boolean {
  return new URL(window.location.href).searchParams.get(PANEL_QUERY_KEY) === REPORTS_QUERY_VALUE
}

export function ReportsNavigationBridge() {
  const [open, setOpen] = useState<boolean>(initialOpenState)
  const [target, setTarget] = useState<HTMLElement | null>(null)
  const [allowed, setAllowed] = useState(false)

  useEffect(() => {
    const refreshTarget = () => setTarget(findDashboardContent())
    refreshTarget()
    const observer = new MutationObserver(refreshTarget)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!target) return
    let cancelled = false

    authorizedFetch('/api/v1/auth/me')
      .then(async (response) => {
        if (!response.ok) return null
        return response.json() as Promise<{ permissions?: string[] }>
      })
      .then((profile) => {
        if (cancelled || !profile) return
        setAllowed(profile.permissions?.includes('reports.view') ?? false)
      })
      .catch(() => {
        if (!cancelled) setAllowed(false)
      })

    return () => { cancelled = true }
  }, [target])

  useEffect(() => {
    if (!allowed) return

    const syncButton = () => {
      const button = findReportsButton()
      if (!button) return
      if (button.disabled) button.disabled = false
      if (button.getAttribute('aria-disabled') !== 'false') button.setAttribute('aria-disabled', 'false')
      if (button.title) button.removeAttribute('title')
    }

    syncButton()
    const observer = new MutationObserver(syncButton)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled', 'aria-disabled'],
    })
    return () => observer.disconnect()
  }, [allowed])

  useEffect(() => {
    const handleNavigationClick = (event: MouseEvent) => {
      const element = event.target instanceof Element ? event.target : null
      const button = element?.closest<HTMLButtonElement>('.side-nav button') ?? null
      if (!button) return

      if (button.textContent?.includes(REPORTS_LABEL)) {
        if (!allowed) return
        setOpen(true)
        setReportsQuery(true)
        return
      }

      setOpen(false)
      setReportsQuery(false)
    }

    document.addEventListener('click', handleNavigationClick, true)
    return () => document.removeEventListener('click', handleNavigationClick, true)
  }, [allowed])

  useEffect(() => {
    if (!target) return
    target.classList.toggle('reports-route-active', open && allowed)

    const button = findReportsButton()
    button?.classList.toggle('reports-route-selected', open && allowed)

    return () => {
      target.classList.remove('reports-route-active')
      button?.classList.remove('reports-route-selected')
    }
  }, [open, allowed, target])

  if (!open || !target || !allowed) return null

  return createPortal(
    <div className="reports-route-surface" role="region" aria-label="Reports and Analytics">
      <ReportsAnalytics />
    </div>,
    target,
  )
}
