<script setup lang="ts">
definePageMeta({ middleware: 'account' })
const { t } = useI18n()
useSeoMeta({ title: () => t('使用记录'), robots: 'noindex, nofollow' })
</script>
<template><div class="container account-page operations-page"><h1>{{ $t('使用记录') }}</h1><AccountNav /><UsageList /></div></template>
