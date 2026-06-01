type DataLayerEventParams = Record<string, string | number | boolean | undefined>

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>
  }
}

export function trackEvent(
  eventName: string,
  params: DataLayerEventParams = {},
) {
  window.dataLayer = window.dataLayer || []

  window.dataLayer.push({
    event: eventName,
    ...params,
  })
}