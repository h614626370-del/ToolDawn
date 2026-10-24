export default defineNuxtRouteMiddleware(() => {
  if (import.meta.server) return
  if (!useAuth().user.value?.is_superadmin) return navigateTo('/admin')
})
