<script setup lang="ts">
const { locale } = useI18n()
useHead(() => ({ htmlAttrs: { lang: locale.value === 'en' ? 'en' : 'zh-CN' } }))
</script>

<template>
  <NuxtRouteAnnouncer />
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
