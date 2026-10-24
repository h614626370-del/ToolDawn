<script setup lang="ts">
defineProps<{ kind: 'error' | 'empty' | 'loading'; title?: string; description?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="async-state" role="status" :aria-busy="kind === 'loading'">
    <AppIcon :name="kind === 'error' ? 'alert' : kind === 'empty' ? 'search' : 'loader'" :size="30" :class="{ spin: kind === 'loading' }" />
    <h2>{{ title || (kind === 'error' ? $t('工具目录暂时不可用') : kind === 'empty' ? $t('没有找到合适的工具') : $t('正在加载工具')) }}</h2>
    <p v-if="kind !== 'loading'">{{ description || (kind === 'error' ? $t('请稍后重试。') : $t('换一个关键词，或查看全部分类。')) }}</p>
    <button v-if="kind === 'error'" class="button secondary" @click="$emit('retry')">
      <AppIcon name="refresh" :size="16" />{{ $t('重新加载') }}
    </button>
    <slot />
  </div>
</template>
