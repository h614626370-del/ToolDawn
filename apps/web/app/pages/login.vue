<script setup lang="ts">
const { t } = useI18n()
const route = useRoute()
const auth = useAuth()
useSeoMeta({ title: () => t('登录 · ToolDawn'), robots: 'noindex, nofollow' })
function destination() {
  const next = typeof route.query.next === 'string' ? route.query.next : ''
  return /^\/(?:account|tools|admin)(?:\/|\?|$)/.test(next) && !next.includes('\\') ? next : '/account'
}
async function complete() {
  await navigateTo(auth.user.value?.must_change_password ? '/account/security' : destination())
}
onMounted(async () => {
  try { if (await auth.refresh()) await complete() } catch { /* The form reports connection errors. */ }
})
</script>

<template>
  <div class="container auth-page">
    <NuxtLink to="/" class="back-link"><AppIcon name="back" :size="16" />{{ $t('返回工具导航') }}</NuxtLink>
    <section class="auth-content" aria-labelledby="login-title">
      <AppIcon name="sun" :size="34" class="auth-mark" />
      <h1 id="login-title">{{ $t('登录 ToolDawn') }}</h1>
      <LoginForm @success="complete" />
    </section>
  </div>
</template>
