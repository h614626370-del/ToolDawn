<script setup lang="ts">
definePageMeta({ middleware:'account', layout:'account' })
const { t } = useI18n()
useSeoMeta({ title:() => `${t('使用记录')} · ToolDawn`, robots:'noindex, nofollow' })
</script>
<template><div><AccountHeading title="使用记录" description="找回每一次创作，继续完成你的想法。" /><AccountUsage /></div></template>
