<script setup lang="ts">
import { authError } from '~/composables/useAuth'
import type { AuthUser } from '~/types/auth'
const auth = useAuth()
const { t } = useI18n()
const input = ref<HTMLInputElement>()
const canvas = ref<HTMLCanvasElement>()
const editing = ref(false)
const busy = ref(false)
const decoding = ref(false)
const error = ref('')
const notice = ref('')
const zoom = ref(1)
const x = ref(50)
const y = ref(50)
let source: HTMLImageElement | null = null
let objectUrl = ''
let stopped = false
function release() { if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = ''; source = null }
function close() { editing.value = false; release() }
function draw() {
  const context = canvas.value?.getContext('2d')
  if (!context || !source) return
  const side = Math.min(source.naturalWidth, source.naturalHeight) / zoom.value
  const sx = (source.naturalWidth - side) * x.value / 100
  const sy = (source.naturalHeight - side) * y.value / 100
  context.clearRect(0, 0, 512, 512)
  context.drawImage(source, sx, sy, side, side, 0, 0, 512, 512)
}
watch([zoom, x, y, canvas], draw, { flush: 'post' })
async function pick(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (input.value) input.value.value = ''
  if (!file || decoding.value || busy.value) return
  error.value = ''; notice.value = ''
  if (!['image/png','image/jpeg','image/webp'].includes(file.type)) { error.value = t('头像无法读取，请选择静态 PNG、JPG 或 WebP 图片。'); return }
  if (file.size > 4 * 1024 * 1024) { error.value = t('请选择 4 MB 以内的头像。'); return }
  decoding.value = true
  try {
    release(); objectUrl = URL.createObjectURL(file)
    const image = new Image(); image.src = objectUrl
    await image.decode()
    if (stopped) return
    if (image.naturalWidth * image.naturalHeight > 16_000_000) throw new Error()
    source = image; zoom.value = 1; x.value = y.value = 50; editing.value = true
    await nextTick(); draw()
  } catch { release(); error.value = t('头像无法读取，请选择静态 PNG、JPG 或 WebP 图片。') }
  finally { decoding.value = false }
}
async function save() {
  if (!canvas.value || busy.value) return
  busy.value = true; error.value = ''
  try {
    const blob = await new Promise<Blob>((resolve,reject) => canvas.value!.toBlob(value => value ? resolve(value) : reject(new Error()), 'image/png'))
    auth.user.value = await $fetch<AuthUser>('/api/v1/me/avatar', { method:'PUT', body:blob, headers:{'Content-Type':'image/png'}, retry:0 })
    close(); notice.value = t('头像已更新。')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
async function remove() {
  busy.value = true; error.value = ''; notice.value = ''
  try { auth.user.value = await $fetch<AuthUser>('/api/v1/me/avatar', { method:'DELETE' }); notice.value = t('已恢复默认头像。') }
  catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
onBeforeUnmount(() => { stopped = true; release() })
</script>
<template>
  <div class="account-avatar-editor">
    <UserAvatar :src="auth.user.value?.avatar_url" :name="auth.user.value?.display_name || auth.user.value?.email" :size="88" />
    <div><h2>{{ $t('个人头像') }}</h2><p>{{ $t('让每一次创作，都有你的印记。') }}</p><div class="account-inline-actions"><button class="button secondary" :disabled="busy || decoding" @click="input?.click()"><AppIcon name="upload" :size="16" />{{ $t('更换头像') }}</button><button v-if="auth.user.value?.avatar_url" class="text-button" :disabled="busy || decoding" @click="remove">{{ $t('移除头像') }}</button></div><small>PNG / JPG / WebP · {{ $t('最大 4 MB') }}</small></div>
    <input ref="input" type="file" class="sr-only" accept="image/png,image/jpeg,image/webp" :aria-label="$t('上传头像')" :disabled="busy || decoding" @change="pick">
  </div>
  <p v-if="notice" role="status" class="account-notice">{{ notice }}</p><p v-if="error && !editing" role="alert" class="form-error">{{ error }}</p>
  <AccountDialog v-if="editing" :title="$t('调整头像')" :busy="busy" @close="close"><div class="account-dialog-body avatar-crop"><canvas ref="canvas" width="512" height="512" :aria-label="$t('头像裁剪预览')" /><label>{{ $t('缩放') }}<input v-model.number="zoom" type="range" min="1" max="3" step="0.05" :disabled="busy"></label><label>{{ $t('水平位置') }}<input v-model.number="x" type="range" min="0" max="100" :disabled="busy"></label><label>{{ $t('垂直位置') }}<input v-model.number="y" type="range" min="0" max="100" :disabled="busy"></label><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="account-inline-actions"><button class="button secondary" :disabled="busy" @click="close">{{ $t('取消') }}</button><button class="button primary" :disabled="busy" @click="save">{{ $t(busy ? '正在保存' : '保存头像') }}</button></div></div></AccountDialog>
</template>
