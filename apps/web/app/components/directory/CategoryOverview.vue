<script setup lang="ts">
import type { Category } from '~/types/catalog'
defineProps<{ categories: Category[] }>()
</script>

<template>
  <section class="category-overview" aria-labelledby="category-heading">
    <h2 id="category-heading" class="section-title"><AppIcon name="grid" :size="22" />{{ $t('按分类浏览') }}</h2>
    <div class="category-overview-grid">
      <NuxtLink v-for="category in categories" :key="category.slug" :to="{ path: '/tools', query: { category: category.slug } }">
        <AppIcon :name="category.icon" :size="28" :class="`ink-${category.color}`" />
        <strong>{{ $t(category.name) }}</strong><span>{{ category.tool_count }} {{ $t('个工具') }}</span><AppIcon name="arrow" :size="17" />
      </NuxtLink>
    </div>
  </section>
</template>
