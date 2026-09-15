import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { AboutSystem } from './AboutSystem'

const PANEL_QUERY_KEY = 'panel'
const ABOUT_QUERY_VALUE = 'about'

function findDashboardContent(): HTMLElement | null {
  return document.querySelector<HTMLElement>('.dashboard-content')
}

function findSidebarFooter(): HTMLElement | null {
  return document.querySelector<HTMLElement>('.sidebar-footer')
}

function initialOpenState(): boolean {
  return new URL(window.location.href).searchParams.get(PANEL_QUERY_KEY) === ABOUT_QUERY_VALUE
}

function setAboutQuery(enabled: boolean): void {
  const url = new URL(window.location.href)
  if (enabled) {
    url.searchParams.set(PANEL_QUERY_KEY, ABOUT_QUERY_VALUE)
  } else if (url.searchParams.get(PANEL_QUERY_KEY) === ABOUT_QUERY_VALUE) {
    url.searchParams.delete(PANEL_QUERY_KEY)
  } else {
    return
  }

  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
}

function closeOtherDashboardPanels(): void {
  const overviewButton = Array.from(document.querySelectorAll<HTMLButtonElement>('.side-nav button'))
    .find((button) => button.textContent?.includes('Overview'))
  overviewButton?.click()
}

function InfoIcon() {
  return (
    <svg className="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6" />
      <path d="M12 7h.01" />
    </svg>
  )
}

export function AboutNavigationBridge() {
  const [open, setOpen] = useState<boolean>(initialOpenState)
  const [contentTarget, setContentTarget] = useState<HTMLElement | null>(null)
  const [navTarget, setNavTarget] = useState<HTMLElement | null>(null)

  useEffect(() => {
    let navHost: HTMLSpanElement | null = null

    const refreshTargets = () => {
      setContentTarget(findDashboardContent())

      const footer = findSidebarFooter()
      if (!footer) {
        setNavTarget(null)
        return
      }

      const existingHost = footer.querySelector<HTMLSpanElement>('.about-nav-host')
      if (existingHost) {
        navHost = existingHost
        setNavTarget(existingHost)
        return
      }

      navHost = document.createElement('span')
      navHost.className = 'about-nav-host'
      const signOutButton = footer.lastElementChild
      footer.insertBefore(navHost, signOutButton)
      setNavTarget(navHost)
    }

    refreshTargets()
    const observer = new MutationObserver(refreshTargets)
    observer.observe(document.body, { childList: true, subtree: true })

    return () => {
      observer.disconnect()
      navHost?.remove()
    }
  }, [])

  useEffect(() => {
    if (!contentTarget) return
    contentTarget.classList.toggle('about-route-active', open)

    return () => {
      contentTarget.classList.remove('about-route-active')
    }
  }, [contentTarget, open])

  useEffect(() => {
    const handleNavigationClick = (event: MouseEvent) => {
      const element = event.target instanceof Element ? event.target : null
      const sideNavButton = element?.closest<HTMLButtonElement>('.side-nav button')
      if (!sideNavButton) return

      setOpen(false)
      setAboutQuery(false)
    }

    document.addEventListener('click', handleNavigationClick, true)
    return () => document.removeEventListener('click', handleNavigationClick, true)
  }, [])

  const openAbout = () => {
    closeOtherDashboardPanels()
    setAboutQuery(true)
    setOpen(true)
  }

  return (
    <>
      {navTarget && createPortal(
        <button className={`about-system-nav ${open ? 'active' : ''}`} type="button" onClick={openAbout} aria-current={open ? 'page' : undefined}>
          <InfoIcon />
          <span>About System</span>
        </button>,
        navTarget,
      )}

      {open && contentTarget && createPortal(
        <div className="about-route-surface" role="region" aria-label="About System">
          <AboutSystem />
        </div>,
        contentTarget,
      )}
    </>
  )
}
