<script setup lang="ts">
definePageMeta({ middleware:'account', layout:'account' })
const { t } = useI18n()
useSeoMeta({ title:() => `${t('我的工单')} · ToolDawn`, robots:'noindex, nofollow' })
</script>
<template><div><AccountHeading title="我的工单" description="反馈问题、查看回复，在这里跟进处理进展。" /><AccountTickets /></div></template>
