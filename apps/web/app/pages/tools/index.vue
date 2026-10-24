<script setup lang="ts">
const { t } = useI18n()
useSeoMeta({ title: () => t('全部工具 · ToolDawn'), description: () => t('搜索、筛选和收藏 ToolDawn 收录的在线工具。') })
</script>

<template><CatalogBrowser /></template>
