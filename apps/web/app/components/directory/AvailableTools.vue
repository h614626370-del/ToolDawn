<script setup lang="ts">
import type { Tool } from '~/types/catalog'
defineProps<{ tools: Tool[] }>()
</script>

<template>
  <section v-if="tools.length" class="recent-section" aria-labelledby="available-heading">
    <div class="section-heading"><h2 id="available-heading" class="section-title"><AppIcon name="external" :size="20" />{{ $t('现在就能用') }}</h2><NuxtLink to="/tools" class="text-link">{{ $t('浏览工具库') }}<AppIcon name="arrow" :size="16" /></NuxtLink></div>
    <div class="recent-grid">
      <NuxtLink v-for="tool in tools" :key="tool.slug" :to="`/tools/${tool.slug}`" class="recent-item">
        <span class="tool-icon" :class="`tone-${tool.color}`"><AppIcon :name="tool.icon" :size="24" /></span>
        <div><h3>{{ $t(tool.name) }}</h3><p>{{ $t(tool.summary) }}</p></div>
        <AppIcon name="arrow" :size="17" />
      </NuxtLink>
    </div>
  </section>
</template>
