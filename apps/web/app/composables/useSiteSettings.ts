export function useSiteSettings() {
  return useAsyncData('site-settings', () => useRequestFetch()<{
    site_logo: string; site_name: string; announcement: string; contact_email: string
    registration_enabled: boolean; ai_enabled: boolean; tickets_enabled: boolean
  }>('/api/v1/site'), {
    default: () => ({ site_logo: 'default', site_name: 'ToolDawn', announcement: '', contact_email: '',
      registration_enabled: true, ai_enabled: true, tickets_enabled: true }),
  })
}
