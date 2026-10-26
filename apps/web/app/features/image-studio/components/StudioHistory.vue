<script setup lang="ts">
import type { ImageRun } from '../types'
defineProps<{ records: ImageRun[]; active: ImageRun | null; busy: boolean; loading: boolean; loggedIn: boolean }>()
const emit = defineEmits<{ select: [run: ImageRun]; refresh: []; close: [] }>()
const { t, locale } = useI18n()
function time(value: string) { return new Date(value).toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' }) }
</script>

<template>
  <aside class="studio-history" :aria-label="t('作品记录')">
    <div class="studio-panel-heading"><h2>{{ t('作品记录') }}<span>{{ records.length }}</span></h2><div><button class="studio-icon" :disabled="loading" :aria-label="t('刷新作品')" :title="t('刷新作品')" @click="emit('refresh')"><AppIcon name="refresh" :size="16" /></button><button class="studio-icon" :aria-label="t('收起作品记录')" :title="t('收起作品记录')" @click="emit('close')"><AppIcon name="panel-close" :size="16" /></button></div></div>
    <div v-if="!records.length" class="studio-history-empty"><AppIcon name="history" :size="26" /><strong>{{ t('你的创作会留在这里') }}</strong><p>{{ t(loggedIn ? '完成第一张图片后，可随时打开、下载或继续创作。' : '登录后查看你的作品记录。') }}</p></div>
    <div v-else class="studio-history-list">
      <button v-for="run in records" :key="run.id" class="studio-history-item" :class="{ selected: active?.id === run.id }" :aria-pressed="active?.id === run.id" :aria-label="`${t(run.mode === 'edit' ? '图生图' : '文生图')} ${time(run.created_at)}`" @click="emit('select', run)">
        <div class="studio-history-preview"><img v-if="run.output" :src="run.output" :alt="t('生成作品缩略图')" loading="lazy" /><span v-else><AppIcon :name="run.status === 'running' ? 'loader' : run.status === 'failed' ? 'alert' : 'image'" :size="23" :class="{ spin: run.status === 'running' }" />{{ t(run.status === 'running' ? '正在生成' : run.status === 'failed' ? '失败已退分' : '结果已删除') }}</span><span v-if="active?.id === run.id" class="studio-selected-mark"><AppIcon name="check" :size="13" /></span></div>
        <div class="studio-history-caption"><strong>{{ t(run.mode === 'edit' ? '图生图' : '文生图') }}</strong><time :datetime="run.created_at">{{ time(run.created_at) }}</time></div><small>{{ run.size }}<span v-if="run.background === 'transparent'"> · {{ t('透明') }}</span></small>
      </button>
    </div>
    <p class="studio-history-footer">{{ t('仅你可见 · 最近 20 次创作') }}</p>
  </aside>
</template>
