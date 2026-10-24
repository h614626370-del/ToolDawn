<script setup lang="ts">
const { t } = useI18n()
definePageMeta({ key: route => route.path })
import type { Category, Tool, ToolPage } from '~/types/catalog'
import type { TextToolConfig } from '~/types/ai-tools'
const route = useRoute()
const slug = computed(() => String(route.params.slug))
const { data: tool, error, refresh } = await useFetch<Tool>(() => `/api/v1/tools/${encodeURIComponent(slug.value)}`)
if (error.value?.statusCode === 404) {
  throw createError({ statusCode: 404, statusMessage: t('没有找到这个工具') })
}
const { data: categories } = await useFetch<Category[]>('/api/v1/categories')
const { data: workspace } = await useAsyncData(`workspace-${slug.value}`, async () => {
  if (tool.value?.kind !== 'internal' || tool.value.status !== 'available') return null
  try { return await $fetch<TextToolConfig>(`/api/v1/ai-tools/${encodeURIComponent(slug.value)}`) }
  catch { return null }
}, { watch: [slug] })
const { data: related } = await useFetch<ToolPage>('/api/v1/tools', {
  query: computed(() => ({ category: tool.value?.category, limit: 8 })),
})
const category = computed(() => categories.value?.find(item => item.slug === tool.value?.category))
const relatedTools = computed(() => related.value?.items.filter(item => item.slug !== slug.value).slice(0, 3) || [])
useSeoMeta({
  title: () => tool.value ? `${t(tool.value.name)} · ToolDawn` : t('工具详情 · ToolDawn'),
  description: () => t(tool.value?.summary || '查看工具介绍和使用入口。'),
})
</script>

<template>
  <div class="container detail-page">
    <NuxtLink to="/tools" class="back-link"><AppIcon name="back" :size="16" />{{ $t('返回工具目录') }}</NuxtLink>
    <AsyncState v-if="error" kind="error" @retry="refresh()" />
    <template v-else-if="tool">
      <TextToolWorkspace v-if="workspace" :key="workspace.slug" :tool="tool" :config="workspace" />
      <ToolDetail v-else :key="tool.slug" :tool="tool" :category="category" />
      <section v-if="relatedTools.length" class="related-section"><div class="section-heading"><h2 class="section-title">{{ $t('你可能也需要') }}</h2><NuxtLink :to="{ path: '/tools', query: { category: tool.category } }" class="text-link">{{ $t('同类工具') }}<AppIcon name="arrow" :size="16" /></NuxtLink></div><div class="related-grid"><ToolCard v-for="item in relatedTools" :key="item.slug" :tool="item" :category="category" compact /></div></section>
    </template>
  </div>
</template>
