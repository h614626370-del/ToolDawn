<script setup lang="ts">
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t } = useI18n()
useSeoMeta({ title: () => t('使用记录') })
</script>
<template><div><div class="admin-page-heading"><h1>{{ $t('使用记录') }}</h1></div><UsageList admin /></div></template>
