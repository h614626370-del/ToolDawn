<script setup lang="ts">
import type { Tool } from '~/types/catalog'
import { toolArtwork } from '~/utils/directoryStyles'
const props = defineProps<{ tool: Tool; eager?: boolean }>()
const failed = ref(false)
const source = computed(() => toolArtwork(props.tool))
watch(source, () => { failed.value = false })
</script>

<template>
  <div class="tool-artwork">
    <img v-if="!failed" :src="source" :alt="$t('{name}效果示意', { name: $t(tool.name) })" width="600" height="400" :loading="eager ? 'eager' : 'lazy'" decoding="async" @error="failed = true">
    <span v-else class="artwork-fallback">{{ $t('预览暂不可用') }}</span>
  </div>
</template>
