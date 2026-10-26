<script setup lang="ts">
const { t } = useI18n()
import type { Category, ToolPage } from '~/types/catalog'
const props = withDefaults(defineProps<{ home?: boolean }>(), { home: false })
const filters = useCatalogFilters()
const auth = useAuth()
const route = useRoute()
const favoritesChecking = computed(() => filters.favoritesOnly.value && !auth.loaded.value)
const favoritesGuest = computed(() => filters.favoritesOnly.value && auth.loaded.value && !auth.user.value)
const favoritesBlocked = computed(() => favoritesChecking.value || favoritesGuest.value)
const loginDestination = computed(() => ({ path: '/login', query: { next: route.fullPath } }))
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
  const items = (data.value?.items || []).filter(tool => tool.status === 'available' && tool.kind === 'internal')
  return ['text-summary', 'copy-rewrite'].flatMap(slug => items.filter(tool => tool.slug === slug))
})
const grouped = computed(() => isHomeOverview.value)
const toolGroups = computed(() => (categories.value || []).map(category => ({ category, tools: visibleTools.value.filter(tool => tool.category === category.slug) })).filter(group => group.tools.length))
const heading = computed(() => filters.favoritesOnly.value ? t('我的收藏') : filters.query.value ? t('搜索结果') : filters.category.value ? t(categoryMap.value[filters.category.value]?.name || '分类工具') : isHomeOverview.value ? t('精选工具') : t('全部工具'))
const emptyTitle = computed(() => filters.favoritesOnly.value && !slugs.value.length ? t('还没有收藏工具') : t('没有找到合适的工具'))
const emptyDescription = computed(() => filters.favoritesOnly.value && !slugs.value.length ? t('点击工具旁的收藏图标，将它留在这里。') : t('换一个关键词，或查看全部分类。'))
const hasSearchFilters = computed(() => !!filters.query.value || !!filters.category.value)
function clearSearchFilters() { return filters.update({ q: undefined, category: undefined }) }

async function retry() {
  await Promise.all([refresh(), refreshCategories()])
}
</script>

<template>
  <div class="container directory" :class="{ 'home-overview': isHomeOverview, 'catalog-listing': !isHomeOverview }">
    <div class="directory-frame">
    <aside class="catalog-sidebar"><DirectoryNavigation collapsible /></aside>
    <div class="directory-body">
      <section class="directory-intro" aria-labelledby="directory-title">
        <div><h1 id="directory-title">{{ isHomeOverview ? $t('发现好工具') : heading }}</h1><p>{{ isHomeOverview ? $t('把时间留给想做的事。') : filters.favoritesOnly.value ? $t('常用的工具，随时回来。') : $t('按用途寻找，找到就开始。') }}</p></div>
        <SearchBar v-if="!favoritesBlocked" :model-value="filters.query.value" :busy="status === 'pending'" @search="filters.update({ q: $event || undefined })" />
      </section>
    <div v-if="showHighlights" class="overview-stage with-carousel">
      <template v-if="showHighlights">
        <FeatureCarousel :tools="data?.items || []" />
        <aside v-if="available.length" class="quick-tools">
          <h2>{{ $t('随手就能用') }}<AppIcon name="arrow" :size="16" /></h2>
          <NuxtLink v-for="tool in available" :key="tool.slug" :to="`/tools/${tool.slug}`" class="quick-tool"><ToolArtwork :tool="tool" eager /><span><strong>{{ $t(tool.name) }}</strong><small>{{ $t(tool.summary) }}</small></span></NuxtLink>
        </aside>
      </template>
    </div>
    <AsyncState v-if="favoritesChecking" kind="loading" :title="$t('正在加载')" />
    <section v-else-if="favoritesGuest" class="favorites-login" aria-labelledby="favorites-login-title">
      <span class="favorites-login-icon"><AppIcon name="bookmark" :size="30" /></span>
      <p class="favorites-login-eyebrow">{{ $t('你的常用工具，留在这里') }}</p>
      <h2 id="favorites-login-title">{{ $t('请先登录') }}</h2>
      <p>{{ $t('登录后收藏常用工具，下次回来就能快速找到。') }}</p>
      <div class="favorites-login-actions"><NuxtLink :to="loginDestination" class="button primary">{{ $t('登录并查看收藏') }}<AppIcon name="arrow" :size="16" /></NuxtLink><NuxtLink to="/tools" class="button secondary">{{ $t('先逛逛工具') }}</NuxtLink></div>
      <small>{{ $t('收藏保存在当前浏览器，并按登录账号区分。') }}</small>
    </section>
    <section v-else class="tool-section" aria-labelledby="tools-heading" :aria-busy="status === 'pending'">
      <div class="section-heading">
        <h2 id="tools-heading" class="section-title" :class="{ 'sr-only': !isHomeOverview }"><AppIcon :name="filters.favoritesOnly.value ? 'bookmark' : 'compass'" :size="23" />{{ heading }}<span v-if="!error && isHomeOverview" class="result-count">{{ visibleTools.length }}</span></h2>
        <p v-if="!isHomeOverview" class="catalog-results" role="status">{{ status === 'pending' ? $t('正在加载数据') : error || categoryError ? $t('工具列表') : $t('共 {count} 个工具', { count: visibleTools.length }) }}</p>
        <NuxtLink v-if="isHomeOverview" to="/tools" class="text-link">{{ $t('查看全部') }}<AppIcon name="arrow" :size="16" /></NuxtLink>
        <div v-else class="result-actions">
          <button v-if="hasSearchFilters" class="text-button" @click="clearSearchFilters"><AppIcon name="close" :size="15" />{{ $t('清除筛选') }}</button>
          <label class="sort-control"><span class="sr-only">{{ $t('排序方式') }}</span><select :value="filters.sort.value" @change="filters.update({ sort: ($event.target as HTMLSelectElement).value })"><option value="recommended">{{ $t('推荐排序') }}</option><option value="recent">{{ $t('最近更新') }}</option></select></label>
        </div>
      </div>
      <p v-if="filters.query.value" class="search-context">{{ $t('“{query}” 的搜索结果', { query: filters.query.value }) }}</p>
      <p v-if="!storageAvailable" class="inline-notice" role="status">{{ $t('浏览器暂时无法保存收藏，本次操作仅在当前页面有效。') }}</p>
      <AsyncState v-if="error || categoryError" kind="error" @retry="retry" />
      <AsyncState v-else-if="status === 'pending' || (filters.favoritesOnly.value && !ready)" kind="loading" />
      <AsyncState v-else-if="!visibleTools.length" kind="empty" :title="emptyTitle" :description="emptyDescription">
        <NuxtLink v-if="filters.favoritesOnly.value && !slugs.length" to="/tools" class="button primary">{{ $t('去发现工具') }}<AppIcon name="arrow" :size="16" /></NuxtLink>
        <button v-else-if="hasSearchFilters" class="button secondary" @click="clearSearchFilters">{{ $t('清除筛选') }}</button>
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
