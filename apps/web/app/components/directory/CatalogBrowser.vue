<script setup lang="ts">
const { t } = useI18n()
import type { Category, ToolPage } from '~/types/catalog'
const props = withDefaults(defineProps<{ home?: boolean }>(), { home: false })
const { selected } = useDirectoryStyle()
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
const showHighlights = computed(() => isHomeOverview.value && !error.value && !categoryError.value && !!data.value?.items.some(tool => tool.kind === 'internal'))
const visibleTools = computed(() => {
  const items = data.value?.items || []
  if (filters.favoritesOnly.value) return items.filter(item => slugs.value.includes(item.slug))
  return isHomeOverview.value ? items.filter(item => item.featured) : items
})
const available = computed(() => {
  const choices: Record<string, string[]> = { cream: ['text-summary', 'copy-rewrite'], plum: ['email-writer', 'text-translate'], library: ['text-polish', 'text-summary'] }
  const items = (data.value?.items || []).filter(tool => tool.status === 'available' && tool.kind === 'internal')
  return (choices[selected.value] || []).flatMap(slug => items.filter(tool => tool.slug === slug))
})
const grouped = computed(() => isHomeOverview.value && ['olive', 'library'].includes(selected.value))
const toolGroups = computed(() => (categories.value || []).map(category => ({ category, tools: visibleTools.value.filter(tool => tool.category === category.slug) })).filter(group => group.tools.length))
const heading = computed(() => filters.favoritesOnly.value ? t('我的收藏') : filters.query.value ? t('搜索结果') : filters.category.value ? t(categoryMap.value[filters.category.value]?.name || '分类工具') : isHomeOverview.value ? t('精选工具') : t('全部工具'))
const emptyTitle = computed(() => filters.favoritesOnly.value && !slugs.value.length ? t('还没有收藏工具') : t('没有找到合适的工具'))
const emptyDescription = computed(() => filters.favoritesOnly.value && !slugs.value.length ? t('点击工具旁的收藏图标，将它留在这里。') : t('换一个关键词，或查看全部分类。'))

async function retry() {
  await Promise.all([refresh(), refreshCategories()])
}
</script>

<template>
  <div class="container directory" :class="{ 'home-overview': isHomeOverview }">
    <div class="directory-frame">
    <aside v-if="selected === 'library'" class="directory-sidebar">
      <span class="sidebar-label">{{ $t('探索工具') }}</span>
      <CategoryTabs :categories="categories || []" :selected="filters.category.value" @select="filters.update({ category: $event || undefined })" />
      <NuxtLink to="/tools?saved=1" class="sidebar-favorites"><AppIcon name="bookmark" :size="16" />{{ $t('我的收藏') }}</NuxtLink>
      <p class="sidebar-note">{{ $t('把时间留给想做的事。') }}</p>
    </aside>
    <div class="directory-body">
    <div class="overview-stage" :class="{ 'with-carousel': showHighlights }">
      <section class="directory-intro" aria-labelledby="directory-title">
        <div><h1 id="directory-title">{{ home ? $t('发现好工具') : filters.favoritesOnly.value ? $t('我的收藏') : $t('全部工具') }}</h1><p>{{ home ? $t('把时间留给想做的事。') : filters.favoritesOnly.value ? $t('常用的工具，随时回来。') : $t('按用途寻找，找到就开始。') }}</p></div>
        <SearchBar :model-value="filters.query.value" :busy="status === 'pending'" @search="filters.update({ q: $event || undefined })" />
        <CategoryTabs v-if="selected === 'midnight' && showHighlights" :categories="categories || []" :selected="filters.category.value" @select="filters.update({ category: $event || undefined })" />
      </section>
      <template v-if="showHighlights">
        <FeatureCarousel :tools="data?.items || []" />
        <aside v-if="['cream', 'plum', 'library'].includes(selected) && available.length" class="quick-tools">
          <h2>{{ $t('随手就能用') }}<AppIcon name="arrow" :size="16" /></h2>
          <NuxtLink v-for="tool in available" :key="tool.slug" :to="`/tools/${tool.slug}`" class="quick-tool"><ToolArtwork :tool="tool" eager /><span><strong>{{ $t(tool.name) }}</strong><small>{{ $t(tool.summary) }}</small></span></NuxtLink>
        </aside>
      </template>
    </div>
    <CategoryTabs v-if="selected !== 'library' && !(selected === 'midnight' && showHighlights)" :categories="categories || []" :selected="filters.category.value" @select="filters.update({ category: $event || undefined })" />
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
      <div v-else-if="grouped" class="tool-shelves">
        <section v-for="group in toolGroups" :key="group.category.slug" class="tool-shelf" :aria-labelledby="`shelf-${group.category.slug}`">
          <div class="shelf-heading"><AppIcon :name="group.category.icon" :size="20" /><h3 :id="`shelf-${group.category.slug}`">{{ $t(group.category.name) }}</h3><button class="text-button" @click="filters.update({ category: group.category.slug })">{{ $t('查看全部') }}<AppIcon name="arrow" :size="14" /></button></div>
          <div class="shelf-tools" :data-count="group.tools.length" :style="{ '--shelf-count': Math.min(group.tools.length, 5) }"><DirectoryToolCard v-for="(tool, index) in group.tools" :key="tool.slug" :tool="tool" :category="group.category" :eager="index < 2" /></div>
        </section>
      </div>
      <div v-else class="visual-tool-grid">
        <DirectoryToolCard v-for="(tool, index) in visibleTools" :key="tool.slug" :tool="tool" :category="categoryMap[tool.category]" :eager="index < 4" />
      </div>
    </section>
    <template v-if="isHomeOverview && !error && !categoryError">
      <div class="directory-end"><span /><AppIcon name="sun" :size="16" /><p>{{ $t('好工具，让灵感更进一步。') }}</p><span /></div>
    </template>
    </div>
    </div>
  </div>
</template>
