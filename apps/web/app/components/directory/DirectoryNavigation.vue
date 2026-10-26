<script setup lang="ts">
import type { Category } from '~/types/catalog'

defineProps<{ collapsible?: boolean }>()
const { collapsed, toggle } = useDirectoryNavigation()
const linksId = useId()
const emit = defineEmits<{ navigate: [] }>()
const route = useRoute()
const { slugs, ready } = useFavorites()
const { data: categories, error, refresh } = await useFetch<Category[]>('/api/v1/categories')
const saved = computed(() => route.query.saved === '1')
const category = computed(() => typeof route.query.category === 'string' ? route.query.category : '')
const entries = computed(() => [
  { label: '发现', icon: 'compass', to: '/', active: route.path === '/' && !saved.value && !category.value },
  { label: '全部工具', icon: 'grid', to: '/tools', active: (route.path === '/tools' || route.path.startsWith('/tools/')) && !saved.value && !category.value },
  { label: '我的收藏', icon: 'bookmark', to: '/tools?saved=1', active: saved.value },
])
</script>

<template>
  <nav class="directory-navigation" :aria-label="$t('工具导航')">
    <button v-if="collapsible" class="directory-collapse-toggle" :aria-expanded="!collapsed" :aria-controls="linksId" :aria-label="$t(collapsed ? '展开左侧导航' : '收起左侧导航')" :title="$t(collapsed ? '展开左侧导航' : '收起左侧导航')" @click="toggle">
      <span>{{ $t('收起导航') }}</span><AppIcon :name="collapsed ? 'panel-open' : 'panel-close'" :size="19" />
    </button>
    <div :id="linksId">
    <div class="directory-nav-links">
      <NuxtLink v-for="entry in entries" :key="entry.to" :to="entry.to" :class="{ 'is-current': entry.active }" :aria-current="entry.active ? 'page' : undefined" :aria-label="$t(entry.label)" :title="$t(entry.label)" @click="emit('navigate')">
        <AppIcon :name="entry.icon" :size="18" /><span>{{ $t(entry.label) }}</span>
        <span v-if="entry.icon === 'bookmark' && ready && slugs.length" class="directory-nav-count">{{ slugs.length }}</span>
      </NuxtLink>
    </div>
    <p class="directory-nav-label">{{ $t('工具分类') }}</p>
    <div class="directory-nav-links">
      <NuxtLink v-for="item in categories || []" :key="item.slug" :to="{ path: '/tools', query: { category: item.slug } }" :class="{ 'is-current': !saved && category === item.slug }" :aria-current="!saved && category === item.slug ? 'page' : undefined" :aria-label="$t(item.name)" :title="$t(item.name)" @click="emit('navigate')">
        <AppIcon :name="item.icon" :size="18" /><span>{{ $t(item.name) }}</span><span class="directory-nav-count">{{ item.tool_count }}</span>
      </NuxtLink>
      <button v-if="error" class="directory-nav-retry" :aria-label="$t('重新加载分类')" :title="$t('重新加载分类')" @click="refresh()"><AppIcon name="refresh" :size="18" /><span>{{ $t('重新加载分类') }}</span></button>
    </div>
    </div>
  </nav>
</template>
