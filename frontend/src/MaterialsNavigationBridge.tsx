import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { RawMaterials } from './RawMaterials'
import './materials-navigation-bridge.css'

const MATERIALS_LABEL = 'Raw Materials & Charging'
const MATERIALS_QUERY_KEY = 'panel'
const MATERIALS_QUERY_VALUE = 'materials'

function findDashboardContent(): HTMLElement | null {
  return document.querySelector<HTMLElement>('.dashboard-content')
}

function findMaterialsButton(): HTMLButtonElement | null {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.side-nav button'))
  return buttons.find((button) => button.textContent?.includes(MATERIALS_LABEL)) ?? null
}

function setMaterialsQuery(enabled: boolean): void {
  const url = new URL(window.location.href)
  if (enabled) {
    url.searchParams.set(MATERIALS_QUERY_KEY, MATERIALS_QUERY_VALUE)
  } else if (url.searchParams.get(MATERIALS_QUERY_KEY) === MATERIALS_QUERY_VALUE) {
    url.searchParams.delete(MATERIALS_QUERY_KEY)
  } else {
    return
  }
  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
}

function initialOpenState(): boolean {
  return new URL(window.location.href).searchParams.get(MATERIALS_QUERY_KEY) === MATERIALS_QUERY_VALUE
}

export function MaterialsNavigationBridge() {
  const [open, setOpen] = useState<boolean>(initialOpenState)
  const [target, setTarget] = useState<HTMLElement | null>(null)

  useEffect(() => {
    const refreshTarget = () => setTarget(findDashboardContent())
    refreshTarget()

    const observer = new MutationObserver(refreshTarget)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const handleNavigationClick = (event: MouseEvent) => {
      const element = event.target instanceof Element ? event.target : null
      const button = element?.closest<HTMLButtonElement>('.side-nav button') ?? null
      if (!button) return

      if (button.textContent?.includes(MATERIALS_LABEL)) {
        setOpen(true)
        setMaterialsQuery(true)
        return
      }

      setOpen(false)
      setMaterialsQuery(false)
    }

    document.addEventListener('click', handleNavigationClick, true)
    return () => document.removeEventListener('click', handleNavigationClick, true)
  }, [])

  useEffect(() => {
    if (!target) return
    target.classList.toggle('materials-route-active', open)

    const button = findMaterialsButton()
    button?.classList.toggle('materials-route-selected', open)

    return () => {
      target.classList.remove('materials-route-active')
      button?.classList.remove('materials-route-selected')
    }
  }, [open, target])

  if (!open || !target) return null

  return createPortal(
    <div className="materials-route-surface" role="region" aria-label="Raw Materials and Charging">
      <RawMaterials />
    </div>,
    target,
  )
}
