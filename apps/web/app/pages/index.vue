<script setup lang="ts">
const { t } = useI18n()
useSeoMeta({
  title: () => t('ToolDawn · 发现好工具'),
  description: () => t('浏览图片处理、文字写作、日常生活与实用工具，发现适合你的在线工具。'),
})
</script>

<template><CatalogBrowser home /></template>
