<script setup lang="ts">
import type { Category, Tool } from '~/types/catalog'
const props = defineProps<{ tool: Tool; category?: Category }>()
const { slugs, toggle, storageAvailable } = useFavorites()
const saved = computed(() => slugs.value.includes(props.tool.slug))
</script>

<template>
  <article class="tool-detail">
    <div class="detail-intro">
      <span class="tool-icon detail-icon" :class="`tone-${tool.color}`"><AppIcon :name="tool.icon" :size="38" /></span>
      <div class="detail-heading"><span class="detail-category">{{ $t(category?.name || tool.category) }}<span>/</span>{{ tool.kind === 'external' ? $t('站外工具') : $t('ToolDawn 工具') }}</span><h1>{{ $t(tool.name) }}</h1><p>{{ $t(tool.summary) }}</p></div>
      <button class="button secondary" :aria-pressed="saved" @click="toggle(tool.slug)"><AppIcon name="bookmark" :size="17" />{{ saved ? $t('已收藏') : $t('收藏工具') }}</button>
    </div>
    <p v-if="!storageAvailable" role="status" class="inline-notice">{{ $t('当前浏览器无法持久保存收藏。') }}</p>
    <div class="detail-columns">
      <section class="detail-description"><h2>{{ $t('关于这个工具') }}</h2><p>{{ $t(tool.description) }}</p><h2>{{ $t('功能概览') }}</h2><ul class="feature-list"><li v-for="feature in tool.features" :key="feature"><AppIcon name="check" :size="17" />{{ $t(feature) }}</li></ul></section>
      <aside class="detail-action" :aria-label="$t('使用工具')">
        <span class="availability" :class="{ available: tool.status === 'available' }"><span />{{ tool.status === 'available' ? $t('可前往使用') : $t('正在准备中') }}</span>
        <template v-if="tool.kind === 'external' && tool.external_url && tool.status === 'available'">
          <a :href="tool.external_url" target="_blank" rel="noopener noreferrer" class="button primary">{{ $t('前往工具') }}<AppIcon name="external" :size="18" /></a>
          <p>{{ $t('将在新标签页打开第三方网站，使用规则以对方网站为准。') }}</p>
        </template>
        <template v-else><button class="button secondary" disabled>{{ $t('开发中') }}</button><p>{{ $t('工作台上线后，你可以在这里开始使用。') }}</p></template>
        <dl><div><dt>{{ $t('所属分类') }}</dt><dd>{{ $t(category?.name || tool.category) }}</dd></div><div><dt>{{ $t('最近更新') }}</dt><dd><time :datetime="tool.updated_at">{{ tool.updated_at }}</time></dd></div></dl>
      </aside>
    </div>
  </article>
</template>
