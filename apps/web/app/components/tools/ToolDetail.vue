<script setup lang="ts">
import type { Category, Tool } from '~/types/catalog'
defineProps<{ tool: Tool; category?: Category }>()
</script>

<template>
  <article class="tool-preview-page">
    <ToolPageHeading :tool="tool" />
    <div class="tool-preview-layout">
      <div class="tool-preview-art"><ToolArtwork :tool="tool" eager /></div>
      <section class="tool-preview-description">
        <span class="tool-coming-soon"><AppIcon name="history" :size="16" />{{ $t('开发中') }}</span>
        <h2>{{ $t('关于这个工具') }}</h2>
        <p>{{ $t(tool.description) }}</p>
        <ul class="tool-feature-list"><li v-for="feature in tool.features" :key="feature"><AppIcon name="check" :size="17" />{{ $t(feature) }}</li></ul>
        <p class="tool-preview-note">{{ $t('工作台上线后，你可以在这里开始使用。') }}</p>
        <NuxtLink to="/tools" class="button secondary">{{ $t('浏览其他工具') }}<AppIcon name="arrow" :size="16" /></NuxtLink>
      </section>
    </div>
  </article>
</template>
