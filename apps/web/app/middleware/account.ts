export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) return
  const auth = useAuth()
  const user = await auth.refresh(5000)
  if (!user) return navigateTo(`/login?next=${encodeURIComponent(to.fullPath)}`)
  if (user.must_change_password && to.path !== '/account/security') {
    return navigateTo('/account/security')
  }
})
