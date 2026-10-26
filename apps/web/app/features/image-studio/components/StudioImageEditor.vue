<script setup lang="ts">
import type FilerobotImageEditor from 'filerobot-image-editor'
import { editorZh } from '../editorTranslations'
const props = defineProps<{ source: string }>()
const emit = defineEmits<{ close: []; save: [blob: Blob] }>()
const { t, locale } = useI18n()
const dialog = ref<HTMLDialogElement>()
const mount = ref<HTMLElement>()
const loading = ref(true)
const saving = ref(false)
const error = ref('')
let instance: FilerobotImageEditor | undefined
let objectUrl = ''
let stopped = false
let previous: HTMLElement | null = null
let dirty = false
const discard = ref(false)
function close() { if (saving.value) return; if (dirty) discard.value = true; else emit('close') }
async function save(download = false) {
  if (!instance || saving.value) return
  saving.value = true; error.value = ''
  try {
    const result = instance.getCurrentImgData({ name: 'tooldawn-edited', extension: 'png' }, 1)
    const canvas = result.imageData?.imageCanvas
    if (!canvas || canvas.width * canvas.height > 20_000_000) throw new Error('Invalid canvas')
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('Export failed')), 'image/png'))
    if (download) {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = 'tooldawn-edited.png'; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } else { dirty = false; emit('save', blob) }
  } catch { error.value = t('编辑结果导出失败，请调整后重试。') }
  finally { saving.value = false }
}
onMounted(async () => {
  previous = document.activeElement as HTMLElement
  dialog.value?.showModal()
  try {
    const [{ default: Editor }, response] = await Promise.all([import('filerobot-image-editor'), fetch(props.source, { credentials: 'same-origin' })])
    if (!response.ok) throw new Error('Image unavailable')
    const blob = await response.blob()
    if (stopped) return
    objectUrl = URL.createObjectURL(blob)
    if (!mount.value) return
    instance = new Editor(mount.value, {
      source: objectUrl, useBackendTranslations: false, useCloudimage: false,
      savingPixelRatio: 1, previewPixelRatio: 1, defaultSavedImageType: 'png',
      defaultSavedImageName: 'tooldawn-edited', showBackButton: false,
      tabsIds: ['Adjust', 'Finetune', 'Filters', 'Annotate', 'Resize'], defaultTabId: 'Adjust', defaultToolId: 'Crop',
      translations: locale.value === 'zh' ? editorZh : { save: 'Use as reference' },
      Text: { text: locale.value === 'zh' ? '文字' : 'Text', fonts: ['Arial', 'sans-serif'], fontFamily: 'Arial' },
      annotationsCommon: { fill: '#2b6653', stroke: '#2b6653' }, Rotate: { angle: 90, componentType: 'buttons' },
      onBeforeSave: () => { void save(); return false }, onSave: () => {},
      onModify: () => { dirty = true },
    })
    instance.render()
  } catch { error.value = t('图片编辑器加载失败，请关闭后重试。') }
  finally { loading.value = false }
})
onBeforeUnmount(() => { stopped = true; instance?.terminate(); if (objectUrl) URL.revokeObjectURL(objectUrl); dialog.value?.close(); previous?.focus() })
</script>

<template>
  <dialog ref="dialog" class="studio-editor-dialog" aria-labelledby="studio-editor-title" @cancel.prevent="close">
    <header><div><h2 id="studio-editor-title">{{ t('图片编辑') }}</h2><p>{{ t('裁剪、调色、标注在本地完成，原始作品保持不变。') }}</p></div><div><button class="studio-button" :disabled="loading || saving" @click="save(true)"><AppIcon name="download" :size="16" />{{ t('下载 PNG') }}</button><button class="studio-icon" :aria-label="t('关闭编辑')" :disabled="saving" @click="close"><AppIcon name="close" :size="20" /></button></div></header>
    <div v-if="discard" class="studio-editor-discard" role="alert"><span>{{ t('关闭后将放弃尚未导出的编辑。') }}</span><button class="studio-button" @click="discard = false">{{ t('继续编辑') }}</button><button class="studio-button" @click="emit('close')">{{ t('放弃修改') }}</button></div>
    <p v-if="error" class="studio-message error" role="alert">{{ error }}</p>
    <p v-if="loading" class="studio-editor-loading" role="status">{{ t('正在加载图片编辑器') }}</p>
    <div ref="mount" class="studio-editor-mount" />
    <footer>{{ t('图片编辑组件') }} · Filerobot Image Editor · MIT</footer>
  </dialog>
</template>
