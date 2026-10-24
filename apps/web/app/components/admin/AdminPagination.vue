<script setup lang="ts">
const props = defineProps<{ total: number; offset: number; limit: number; busy: boolean }>()
const emit = defineEmits<{ change: [offset: number] }>()
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.limit)))
</script>

<template>
  <div class="admin-pagination"><span>{{ $t('共 {total} 条 · 第 {page} / {pages} 页', { total, page: Math.floor(offset / limit) + 1, pages }) }}</span><div><button class="icon-button" :disabled="busy || offset === 0" :title="$t('上一页')" :aria-label="$t('上一页')" @click="emit('change', Math.max(0, offset - limit))"><AppIcon name="back" :size="18" /></button><button class="icon-button" :disabled="busy || offset + limit >= total" :title="$t('下一页')" :aria-label="$t('下一页')" @click="emit('change', offset + limit)"><AppIcon name="arrow" :size="18" /></button></div></div>
</template>
