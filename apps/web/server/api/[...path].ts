import { getRequestIP, getRequestURL, proxyRequest } from 'h3'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const url = getRequestURL(event)
  const destination = new URL(url.pathname + url.search, config.apiBase)
  return proxyRequest(event, destination.toString(), {
    headers: { 'x-forwarded-for': getRequestIP(event, { xForwardedFor: false }) || '' },
  })
})
