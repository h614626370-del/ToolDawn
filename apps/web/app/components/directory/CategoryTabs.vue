<script setup lang="ts">
import type { Category } from '~/types/catalog'
defineProps<{ categories: Category[]; selected: string }>()
defineEmits<{ select: [slug: string] }>()
</script>

<template>
  <div class="category-tabs" role="group" :aria-label="$t('按分类筛选')">
    <button :class="{ selected: !selected }" :aria-pressed="!selected" @click="$emit('select', '')">
      <AppIcon name="grid" /><span>{{ $t('全部工具') }}</span>
    </button>
    <button v-for="category in categories" :key="category.slug" :class="{ selected: selected === category.slug }" :aria-pressed="selected === category.slug" @click="$emit('select', category.slug)">
      <AppIcon :name="category.icon" /><span>{{ $t(category.name) }}</span>
    </button>
  </div>
</template>
