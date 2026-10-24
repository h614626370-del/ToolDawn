<script setup lang="ts">
import type { Category, Tool } from '~/types/catalog'
const props = defineProps<{ tool: Tool; category?: Category; compact?: boolean }>()
const { slugs, toggle } = useFavorites()
const saved = computed(() => slugs.value.includes(props.tool.slug))
const imageFailed = ref(false)
</script>

<template>
  <article class="tool-card" :class="{ 'has-preview': !compact && (tool.image || tool.slug === 'text-polish'), compact }">
    <NuxtLink :to="`/tools/${tool.slug}`" class="tool-card-link">
      <div v-if="!compact && tool.image && !imageFailed" class="tool-preview" :class="`preview-${tool.slug}`">
        <img :src="tool.image" :alt="tool.name === '食物分析' ? $t('蔬菜与谷物餐食') : tool.name === '智能抠图' ? $t('浅色背景上的运动鞋') : $t('湖泊与群山风景')" width="600" height="360" loading="lazy" @error="imageFailed = true">
        <span v-if="tool.slug === 'photo-restyle'" class="preview-caption">{{ $t('每一种风景，都有新可能') }}</span>
        <span v-if="tool.slug === 'background-removal'" class="preview-chip"><AppIcon name="scissors" :size="13" />{{ $t('去除背景') }}</span>
      </div>
      <div v-else-if="!compact && tool.slug === 'text-polish'" class="tool-preview writing-preview">
        <div class="writing-sheet before"><span>{{ $t('原文') }}</span><p>{{ $t('这个想法很好，') }}<br>{{ $t('我们可以一起') }}<br>{{ $t('把它做好。') }}</p></div>
        <AppIcon name="arrow" :size="17" />
        <div class="writing-sheet after"><span>{{ $t('润色后') }}</span><p>{{ $t('让灵感落地，') }}<br>{{ $t('让每一次表达') }}<br>{{ $t('更有力量。') }}</p></div>
      </div>
      <div class="tool-card-body">
        <span class="tool-icon" :class="`tone-${tool.color}`"><AppIcon :name="tool.icon" :size="25" /></span>
        <div class="tool-card-copy">
          <div class="tool-card-title"><h3>{{ $t(tool.name) }}</h3><AppIcon name="arrow" class="card-arrow" :size="15" /></div>
          <p>{{ $t(tool.summary) }}</p>
          <div class="tool-meta">
            <span class="category-badge" :class="`tone-${category?.color || tool.color}`">{{ $t(category?.name || tool.category) }}</span>
            <span class="status-label" :class="{ available: tool.status === 'available' }">{{ tool.kind === 'external' ? $t('站外工具') : tool.status === 'available' ? $t('在线使用') : $t('开发中') }}</span>
          </div>
        </div>
      </div>
    </NuxtLink>
    <button class="icon-button bookmark-button" :class="{ saved }" :aria-label="`${saved ? $t('取消收藏') : $t('收藏工具')}：${tool.name}`" :aria-pressed="saved" :title="saved ? $t('取消收藏') : $t('收藏工具')" @click="toggle(tool.slug)">
      <AppIcon name="bookmark" :size="17" />
    </button>
  </article>
</template>
