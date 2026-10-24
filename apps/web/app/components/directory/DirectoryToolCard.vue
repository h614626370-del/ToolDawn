<script setup lang="ts">
import type { Tool, Category } from '~/types/catalog'
const props = defineProps<{ tool: Tool; category?: Category; eager?: boolean }>()
const { slugs, toggle } = useFavorites()
const saved = computed(() => slugs.value.includes(props.tool.slug))
</script>

<template>
  <article class="visual-tool" :data-tool="tool.slug" :data-category="tool.category">
    <NuxtLink :to="`/tools/${tool.slug}`" class="visual-tool-link">
      <ToolArtwork :tool="tool" :eager="eager" />
      <div class="visual-tool-copy">
        <h3>{{ $t(tool.name) }}<AppIcon name="arrow" :size="15" /></h3>
        <p>{{ $t(tool.summary) }}</p>
        <div class="visual-tool-meta">
          <span class="visual-status" :class="{ available: tool.status === 'available' }"><i aria-hidden="true" />{{ tool.kind === 'external' ? $t('站外工具') : tool.status === 'available' ? $t('在线使用') : $t('开发中') }}</span>
          <span class="visual-category">{{ $t(category?.name || tool.category) }}</span>
        </div>
      </div>
    </NuxtLink>
    <button class="visual-bookmark" :class="{ saved }" :aria-label="`${saved ? $t('取消收藏') : $t('收藏工具')}：${$t(tool.name)}`" :aria-pressed="saved" @click="toggle(tool.slug)"><AppIcon name="bookmark" :size="16" /></button>
  </article>
</template>
