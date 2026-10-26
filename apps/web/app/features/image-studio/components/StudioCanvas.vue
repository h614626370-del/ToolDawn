<script setup lang="ts">
import type { ImageRun, ReferenceImage } from '../types'
const props = defineProps<{ active: ImageRun | null; reference: ReferenceImage | null; busy: boolean; uploading: boolean; loading: boolean }>()
const emit = defineEmits<{ useResult: []; edit: [source: string]; openControls: [] }>()
const { t } = useI18n()
const zoom = ref(100)
const showReference = ref(false)
const failed = ref(false)
const stage = ref<HTMLElement>()
const canvas = ref<HTMLElement>()
const dimensions = ref('')
const source = computed(() => showReference.value && props.reference ? props.reference.preview : props.active?.output || props.reference?.preview || '')
watch(source, () => { zoom.value = 100; failed.value = false; dimensions.value = '' })
const canUseResult = computed(() => !!props.active?.output && !showReference.value)
let drag: { x: number; y: number; left: number; top: number } | null = null
function startDrag(event: PointerEvent) {
  if (!stage.value || zoom.value <= 100 || event.button !== 0) return
  stage.value.setPointerCapture(event.pointerId)
  drag = { x:event.clientX, y:event.clientY, left:stage.value.scrollLeft, top:stage.value.scrollTop }
}
function moveDrag(event: PointerEvent) {
  if (!drag || !stage.value) return
  stage.value.scrollLeft = drag.left - event.clientX + drag.x
  stage.value.scrollTop = drag.top - event.clientY + drag.y
}
async function fullscreen() {
  try { if (document.fullscreenElement) await document.exitFullscreen(); else await canvas.value?.requestFullscreen() }
  catch { /* The zoom and fit controls remain available if fullscreen is unsupported. */ }
}
</script>

<template>
  <section ref="canvas" class="studio-canvas" :aria-label="t('图像画布')">
    <div class="studio-canvas-toolbar">
      <div class="studio-canvas-label"><AppIcon name="image" :size="16" /><span>{{ t('画布') }}</span><span v-if="dimensions" class="studio-dimensions">{{ dimensions }}</span></div>
      <div class="studio-canvas-actions">
        <button v-if="reference && active?.output" class="studio-button subtle" :aria-pressed="showReference" @click="showReference = !showReference">{{ t(showReference ? '查看生成结果' : '查看参考图') }}</button>
        <button class="studio-icon" :disabled="!source" :aria-label="t('全屏预览')" :title="t('全屏预览')" @click="fullscreen"><AppIcon name="maximize" :size="17" /></button>
      </div>
    </div>
    <div v-if="loading" class="studio-canvas-empty" role="status"><AppIcon name="loader" :size="26" class="spin" /><p>{{ t('正在加载作品') }}</p></div>
    <div v-else-if="active?.status === 'running' || (busy && !source)" class="studio-canvas-empty" role="status"><span class="studio-empty-symbol"><AppIcon name="sparkles" :size="34" /></span><h2>{{ t('正在把想法变成图片') }}</h2><p>{{ t('通常需要 1–3 分钟。你可以离开页面，稍后从生成记录查看结果。') }}</p><div class="studio-progress"><span /></div></div>
    <div v-else-if="active?.status === 'failed' && !showReference" class="studio-canvas-empty" role="alert"><AppIcon name="alert" :size="30" /><h2>{{ t('这次生成没有完成') }}</h2><p>{{ t('生成未完成，已退回本次积分，请重新尝试。') }}</p></div>
    <div v-else-if="source && !failed" ref="stage" class="studio-stage" :class="{ zoomed: zoom > 100 }" tabindex="0" :aria-label="t('图片预览，可使用下方按钮缩放')" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="drag = null" @pointercancel="drag = null">
      <div class="studio-image-frame" :style="{ width: `${zoom}%`, height: `${zoom}%` }"><img :src="source" :alt="t(showReference ? '参考图片' : 'AI 生成的图片')" draggable="false" @load="dimensions = `${($event.target as HTMLImageElement).naturalWidth} × ${($event.target as HTMLImageElement).naturalHeight}`" @error="failed = true" /></div>
    </div>
    <div v-else-if="failed" class="studio-canvas-empty" role="alert"><p>{{ t('图片暂时无法加载，请刷新后重试。') }}</p><button class="studio-button" @click="failed = false">{{ t('重新加载') }}</button></div>
    <div v-else class="studio-canvas-empty"><span class="studio-empty-symbol"><AppIcon name="image" :size="34" /></span><h2>{{ t('给想法一整张画布') }}</h2><p>{{ t('写下描述开始创作，或上传一张图片继续探索。') }}</p><button class="studio-button" @click="emit('openControls')"><AppIcon name="sparkles" :size="16" />{{ t('开始创作') }}</button></div>
    <div class="studio-canvas-bottom">
      <div class="studio-zoom"><button class="studio-icon" :disabled="!source || zoom <= 50" :aria-label="t('缩小')" :title="t('缩小')" @click="zoom = Math.max(50, zoom - 25)"><AppIcon name="minus" :size="16" /></button><button class="studio-fit" :disabled="!source" :title="t('适应画布')" @click="zoom = 100">{{ zoom }}%</button><button class="studio-icon" :disabled="!source || zoom >= 250" :aria-label="t('放大')" :title="t('放大')" @click="zoom = Math.min(250, zoom + 25)"><AppIcon name="plus" :size="16" /></button></div>
      <div class="studio-output-actions">
        <button class="studio-button" :disabled="!source || busy || uploading" @click="emit('edit', source)"><AppIcon name="sliders" :size="16" />{{ t('编辑图片') }}</button>
        <button class="studio-button" :disabled="!canUseResult || busy || uploading" @click="emit('useResult')"><AppIcon name="layers" :size="16" />{{ t('继续创作') }}</button>
        <a v-if="canUseResult && active?.output" :href="`${active.output}?download=true`" class="studio-button primary"><AppIcon name="download" :size="16" />{{ t('下载') }}</a>
      </div>
    </div>
  </section>
</template>
