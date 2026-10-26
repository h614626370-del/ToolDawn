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
const { data: workspace, error: workspaceError, refresh: refreshWorkspace } = await useAsyncData(`workspace-${slug.value}`, async () => {
  if (tool.value?.kind !== 'internal' || tool.value.status !== 'available') return null
  return await $fetch<TextToolConfig>(`/api/v1/ai-tools/${encodeURIComponent(slug.value)}`)
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
  <div class="container directory tool-page">
    <div class="directory-frame">
      <aside class="catalog-sidebar"><DirectoryNavigation collapsible /></aside>
      <div class="directory-body tool-page-body">
        <nav class="tool-breadcrumbs" :aria-label="$t('当前位置')">
          <NuxtLink to="/tools"><AppIcon name="back" :size="16" />{{ $t('全部工具') }}</NuxtLink>
          <template v-if="category"><span aria-hidden="true">/</span><NuxtLink :to="{ path: '/tools', query: { category: category.slug } }">{{ $t(category.name) }}</NuxtLink></template>
          <template v-if="tool"><span aria-hidden="true">/</span><span aria-current="page">{{ $t(tool.name) }}</span></template>
        </nav>
        <AsyncState v-if="error" kind="error" @retry="refresh()" />
        <template v-else-if="tool">
          <template v-if="workspaceError"><ToolPageHeading :tool="tool" /><AsyncState kind="error" @retry="refreshWorkspace()" /></template>
          <TextToolWorkspace v-else-if="workspace" :key="workspace.slug" :tool="tool" :config="workspace" />
          <ToolDetail v-else :key="tool.slug" :tool="tool" :category="category" />
          <section v-if="relatedTools.length" class="tool-related" aria-labelledby="related-title">
            <div class="section-heading"><h2 id="related-title" class="section-title">{{ $t('你可能也需要') }}</h2><NuxtLink :to="{ path: '/tools', query: { category: tool.category } }" class="text-link">{{ $t('同类工具') }}<AppIcon name="arrow" :size="16" /></NuxtLink></div>
            <div class="tool-related-grid"><DirectoryToolCard v-for="item in relatedTools" :key="item.slug" :tool="item" :category="category" /></div>
          </section>
        </template>
      </div>
    </div>
  </div>
</template>
