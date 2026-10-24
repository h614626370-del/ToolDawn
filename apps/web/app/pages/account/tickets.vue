<script setup lang="ts">
definePageMeta({ middleware: 'account' })
const { t } = useI18n()
useSeoMeta({ title: () => t('我的工单'), robots: 'noindex, nofollow' })
</script>
<template><div class="container account-page operations-page"><h1>{{ $t('我的工单') }}</h1><AccountNav /><TicketDesk /></div></template>
