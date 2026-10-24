<script setup lang="ts">
const { t } = useI18n()
import type { Category, ToolPage } from '~/types/catalog'
const props = withDefaults(defineProps<{ home?: boolean }>(), { home: false })
const filters = useCatalogFilters()
const { slugs, ready, storageAvailable } = useFavorites()
const apiQuery = computed(() => ({
  q: filters.query.value,
  category: filters.category.value || undefined,
  sort: filters.sort.value,
  limit: 48,
}))
const { data, status, error, refresh } = await useFetch<ToolPage>('/api/v1/tools', { query: apiQuery })
const { data: categories, error: categoryError, refresh: refreshCategories } = await useFetch<Category[]>('/api/v1/categories')
const categoryMap = computed(() => Object.fromEntries((categories.value || []).map(item => [item.slug, item])))
const isHomeOverview = computed(() => props.home && !filters.active.value && filters.sort.value === 'recommended')
const visibleTools = computed(() => {
  const items = data.value?.items || []
  if (filters.favoritesOnly.value) return items.filter(item => slugs.value.includes(item.slug))
  return isHomeOverview.value ? items.filter(item => item.featured) : items
})
const available = computed(() => (data.value?.items || []).filter(tool => tool.status === 'available').slice(0, 4))
const heading = computed(() => filters.favoritesOnly.value ? t('我的收藏') : filters.query.value ? t('搜索结果') : filters.category.value ? t(categoryMap.value[filters.category.value]?.name || '分类工具') : isHomeOverview.value ? t('精选工具') : t('全部工具'))
const emptyTitle = computed(() => filters.favoritesOnly.value && !slugs.value.length ? t('还没有收藏工具') : t('没有找到合适的工具'))
const emptyDescription = computed(() => filters.favoritesOnly.value && !slugs.value.length ? t('点击工具旁的收藏图标，将它留在这里。') : t('换一个关键词，或查看全部分类。'))

async function retry() {
  await Promise.all([refresh(), refreshCategories()])
}
</script>

<template>
  <div class="container directory">
    <section class="directory-intro" aria-labelledby="directory-title">
      <div><h1 id="directory-title">{{ home ? $t('发现好工具') : filters.favoritesOnly.value ? $t('我的收藏') : $t('全部工具') }}</h1><p>{{ home ? $t('把时间留给想做的事。') : filters.favoritesOnly.value ? $t('常用的工具，随时回来。') : $t('按用途寻找，找到就开始。') }}</p></div>
      <SearchBar :model-value="filters.query.value" :busy="status === 'pending'" @search="filters.update({ q: $event || undefined })" />
    </section>
    <CategoryTabs :categories="categories || []" :selected="filters.category.value" @select="filters.update({ category: $event || undefined })" />
    <section class="tool-section" aria-labelledby="tools-heading" :aria-busy="status === 'pending'">
      <div class="section-heading">
        <h2 id="tools-heading" class="section-title"><AppIcon :name="filters.favoritesOnly.value ? 'bookmark' : 'compass'" :size="23" />{{ heading }}<span v-if="!error" class="result-count">{{ visibleTools.length }}</span></h2>
        <NuxtLink v-if="isHomeOverview" to="/tools" class="text-link">{{ $t('查看全部') }}<AppIcon name="arrow" :size="16" /></NuxtLink>
        <div v-else class="result-actions">
          <button v-if="filters.active.value" class="text-button" @click="filters.clear"><AppIcon name="close" :size="15" />{{ $t('清除筛选') }}</button>
          <label class="sort-control"><span class="sr-only">{{ $t('排序方式') }}</span><select :value="filters.sort.value" @change="filters.update({ sort: ($event.target as HTMLSelectElement).value })"><option value="recommended">{{ $t('推荐排序') }}</option><option value="recent">{{ $t('最近更新') }}</option></select></label>
        </div>
      </div>
      <p v-if="filters.query.value" class="search-context">{{ $t('“{query}” 的搜索结果', { query: filters.query.value }) }}</p>
      <p v-if="!storageAvailable" class="inline-notice" role="status">{{ $t('浏览器暂时无法保存收藏，本次操作仅在当前页面有效。') }}</p>
      <AsyncState v-if="error || categoryError" kind="error" @retry="retry" />
      <AsyncState v-else-if="status === 'pending' || (filters.favoritesOnly.value && !ready)" kind="loading" />
      <AsyncState v-else-if="!visibleTools.length" kind="empty" :title="emptyTitle" :description="emptyDescription">
        <button v-if="filters.active.value" class="button secondary" @click="filters.clear">{{ $t('清除筛选') }}</button>
      </AsyncState>
      <div v-else class="tool-grid">
        <ToolCard v-for="tool in visibleTools" :key="tool.slug" :tool="tool" :category="categoryMap[tool.category]" :compact="!isHomeOverview" />
      </div>
    </section>
    <template v-if="isHomeOverview && !error && !categoryError">
      <CategoryOverview :categories="categories || []" />
      <AvailableTools :tools="available" />
      <div class="directory-end"><span /><AppIcon name="sun" :size="16" /><p>{{ $t('好工具，让灵感更进一步。') }}</p><span /></div>
    </template>
  </div>
</template>
