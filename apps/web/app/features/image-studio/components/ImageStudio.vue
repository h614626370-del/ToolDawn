<script setup lang="ts">
import StudioControls from './StudioControls.vue'
import StudioCanvas from './StudioCanvas.vue'
import StudioHistory from './StudioHistory.vue'
import StudioImageEditor from './StudioImageEditor.vue'
import { useImageStudio } from '../useImageStudio'
import type { StudioConfig } from '../types'
const { t } = useI18n()
const { data: config, error: configError, refresh: refreshConfig } = await useFetch<StudioConfig>('/api/v1/image-tools/image-generate')
const { auth, prompt, mode, size, quality, transparent, balance, records, active, reference, uploading,
  loading, error, notice, pendingRun, busy, cost, enabled, ready, generate, refresh, upload,
  discardReference, useResult, removeResult, select, newWorkbook, workbookVersion } = useImageStudio(config)
const historyOpen = ref(true)
const mobilePanel = ref<'create' | 'canvas' | 'history'>('create')
const editorSource = ref('')
const confirmDelete = ref(false)
async function submit() { await generate(); if (pendingRun.value) mobilePanel.value = 'canvas' }
async function continueResult() { await useResult(); mobilePanel.value = 'create' }
async function edited(blob: Blob) { editorSource.value = ''; await upload(blob, 'edited-image.png'); mobilePanel.value = 'create' }
function openControls() { mobilePanel.value = 'create'; nextTick(() => document.getElementById('studio-prompt')?.focus()) }
function createWorkbook() {
  if (!newWorkbook()) return
  editorSource.value = ''; confirmDelete.value = false
  openControls()
}
</script>

<template>
  <div class="image-studio" :class="{ 'history-collapsed': !historyOpen }" :data-mobile-panel="mobilePanel">
    <AsyncState v-if="configError" kind="error" @retry="refreshConfig()" />
    <template v-else-if="config">
      <nav class="studio-mobile-tabs" :aria-label="t('工作台面板')"><button v-for="item in [{id:'create',label:'创作'},{id:'canvas',label:'画布'},{id:'history',label:'作品记录'}] as const" :key="item.id" :aria-current="mobilePanel === item.id ? 'page' : undefined" @click="mobilePanel = item.id">{{ t(item.label) }}</button></nav>
      <div v-if="error || notice" class="studio-mobile-feedback"><p v-if="error" role="alert" class="studio-message error">{{ error }}<button @click="refresh">{{ t('重试') }}</button></p><p v-else role="status" class="studio-message">{{ notice }}</p></div>
      <div class="studio-controls-region"><StudioControls v-model:prompt="prompt" v-model:mode="mode" v-model:size="size" v-model:quality="quality" v-model:transparent="transparent" :reference="reference" :busy="busy" :uploading="uploading" :ready="!!ready" :loading="loading" :logged-in="!!auth.user.value" :cost="cost" :enabled="enabled" :edit-enabled="config.edit_enabled" :balance="balance" @generate="submit" @upload="upload" @remove-reference="discardReference" @edit-reference="editorSource = reference?.preview || ''" /></div>
      <div class="studio-center">
        <div class="studio-project-bar"><span><AppIcon name="layers" :size="16" />{{ t('我的画布') }}<button type="button" class="studio-button subtle" :disabled="busy || uploading || loading" :title="t('清空当前工作簿，保留历史作品')" @click="createWorkbook"><AppIcon name="plus" :size="16" />{{ t('新建') }}</button><span v-if="pendingRun" class="studio-job-dot">{{ t('任务进行中') }}</span></span><div><button v-if="active?.output" class="studio-icon" :disabled="busy" :aria-label="t('删除此结果')" :title="t('删除此结果')" @click="confirmDelete = true"><AppIcon name="trash" :size="16" /></button><button v-if="!historyOpen" class="studio-button subtle" @click="historyOpen = true"><AppIcon name="history" :size="16" />{{ t('作品记录') }}</button></div></div>
        <p v-if="error" role="alert" class="studio-message studio-desktop-feedback error">{{ error }}<button @click="refresh">{{ t('重试') }}</button></p>
        <p v-if="notice" role="status" class="studio-message studio-desktop-feedback">{{ notice }}</p>
        <StudioCanvas :key="workbookVersion" :active="active" :reference="reference" :busy="busy" :uploading="uploading" :loading="loading" @use-result="continueResult" @edit="editorSource = $event" @open-controls="openControls" />
      </div>
      <StudioHistory :records="records" :active="active" :busy="busy" :loading="loading" :logged-in="!!auth.user.value" @select="select($event); mobilePanel = 'canvas'" @refresh="refresh" @close="historyOpen = false; mobilePanel = 'canvas'" />
      <Teleport to="body"><StudioImageEditor v-if="editorSource" :source="editorSource" @close="editorSource = ''" @save="edited" /></Teleport>
      <AdminDialog v-if="confirmDelete" :title="t('删除生成图片')" @close="confirmDelete = false"><div class="studio-delete-body"><p>{{ t('图片删除后无法恢复，积分使用记录会保留。') }}</p><div><button class="studio-button" @click="confirmDelete = false">{{ t('取消') }}</button><button class="studio-button" @click="removeResult(); confirmDelete = false">{{ t('确认删除') }}</button></div></div></AdminDialog>
    </template>
  </div>
</template>
