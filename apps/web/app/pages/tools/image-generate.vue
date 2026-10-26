<script setup lang="ts">
import ImageStudio from '~/features/image-studio/components/ImageStudio.vue'
import type { Tool } from '~/types/catalog'
definePageMeta({ layout: 'workspace' })
const { t } = useI18n()
const { data: tool, error, refresh } = await useFetch<Tool>('/api/v1/tools/image-generate')
if (error.value?.statusCode === 404) throw createError({ statusCode: 404, statusMessage: t('工具未开放或已下架。') })
useSeoMeta({ title: () => `${t('图像工作台')} · ToolDawn`, description: () => t('文生图、图生图与图片编辑，在同一个工作台完成。') })
</script>

<template>
  <AsyncState v-if="error" kind="error" @retry="refresh()" />
  <ImageStudio v-else-if="tool?.status === 'available'" />
  <div v-else class="studio-unavailable"><AppIcon name="image" :size="32" /><p>{{ $t('工具未开放或已下架。') }}</p><NuxtLink to="/tools">{{ $t('返回工具目录') }}</NuxtLink></div>
</template>
