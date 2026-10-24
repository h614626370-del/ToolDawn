<script setup lang="ts">
const props = withDefaults(defineProps<{ variant?: string; size?: number }>(), { variant: 'default', size: 37 })
const preset = computed(() => ['speed', 'heritage', 'signature', 'street'].includes(props.variant) ? props.variant : null)
</script>

<template>
  <span class="site-logo" :style="{ width: `${size}px`, height: `${size}px` }" aria-hidden="true">
    <img v-if="preset" :src="`/images/brand/${preset}.webp`" alt="" :width="size" :height="size">
    <AppIcon v-else name="sun" :size="Math.round(size * 0.7)" />
  </span>
</template>

<style scoped>
.site-logo { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; vertical-align: middle; }
.site-logo img { width: 100%; height: 100%; object-fit: contain; border-radius: 8px; }
</style>
