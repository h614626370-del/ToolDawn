<script setup lang="ts">
const { locale } = useI18n()
const { data: site } = await useSiteSettings()
const favicon = computed(() => {
  const logo = site.value.site_logo
  return ['speed', 'heritage', 'signature', 'street'].includes(logo)
    ? { href: `/images/brand/${logo}-favicon.png?v=1`, type: 'image/png', sizes: '64x64' }
    : { href: '/favicon.svg', type: 'image/svg+xml', sizes: 'any' }
})
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'en' ? 'en' : 'zh-CN' },
  link: [{ key: 'site-favicon', rel: 'icon', ...favicon.value }],
}))
</script>

<template>
  <NuxtRouteAnnouncer />
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
