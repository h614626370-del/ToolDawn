<script setup lang="ts">
import type { Tool } from '~/types/catalog'
const props = defineProps<{ tool: Tool }>()
const { slugs, toggle, storageAvailable } = useFavorites()
const saved = computed(() => slugs.value.includes(props.tool.slug))
</script>

<template>
  <header class="workspace-heading">
    <span class="workspace-tool-icon"><AppIcon :name="tool.icon" :size="25" /></span>
    <div><h1>{{ $t(tool.name) }}</h1><p>{{ $t(tool.summary) }}</p></div>
    <button class="tool-save" :class="{ saved }" :aria-pressed="saved" @click="toggle(tool.slug)"><AppIcon name="bookmark" :size="18" /><span>{{ saved ? $t('已收藏') : $t('收藏工具') }}</span></button>
  </header>
  <p v-if="!storageAvailable" class="inline-notice" role="status">{{ $t('当前浏览器无法持久保存收藏。') }}</p>
</template>
