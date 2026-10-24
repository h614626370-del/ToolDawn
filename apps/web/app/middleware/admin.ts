export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) return
  const auth = useAuth()
  let user
  try { user = await auth.refresh(5000) } catch {
    throw createError({ statusCode: 503, statusMessage: '账户服务暂时不可用，请稍后重试。' })
  }
  if (!user) return navigateTo(`/login?next=${encodeURIComponent(to.fullPath)}`)
  if (user.must_change_password) return navigateTo('/account/security')
  if (user.role !== 'admin') {
    throw createError({ statusCode: 403, statusMessage: '需要管理员权限才能进入后台。' })
  }
})
