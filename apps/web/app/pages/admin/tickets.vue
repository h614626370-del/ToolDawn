<script setup lang="ts">
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t } = useI18n()
useSeoMeta({ title: () => t('工单管理') })
</script>
<template><div><div class="admin-page-heading"><h1>{{ $t('工单管理') }}</h1></div><TicketDesk admin /></div></template>
