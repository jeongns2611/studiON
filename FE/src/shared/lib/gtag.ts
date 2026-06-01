const GA_ID = 'G-YBVM4JJ6DV'

declare global {
  interface Window {
    gtag?: (...args: any[]) => void
  }
}

function isGtagReady() {
  return typeof window !== 'undefined' && typeof window.gtag === 'function'
}

export function pageView(path: string, title?: string) {
  if (!isGtagReady()) return

  window.gtag!('event', 'page_view', {
    page_path: path,
    page_title: title,
    page_location: window.location.origin + path,
    send_to: GA_ID,
  })
}

export function trackEvent(
  eventName: string,
  params: Record<string, unknown> = {},
) {
  if (!isGtagReady()) return

  window.gtag!('event', eventName, {
    ...params,
    send_to: GA_ID,
  })
}