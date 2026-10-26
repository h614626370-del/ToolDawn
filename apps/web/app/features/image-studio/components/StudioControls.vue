<script setup lang="ts">
import type { ImageQuality, ReferenceImage, StudioMode } from '../types'
const mode = defineModel<StudioMode>('mode', { required: true })
const prompt = defineModel<string>('prompt', { required: true })
const size = defineModel<string>('size', { required: true })
const quality = defineModel<ImageQuality>('quality', { required: true })
const transparent = defineModel<boolean>('transparent', { required: true })
defineProps<{ reference: ReferenceImage | null; busy: boolean; uploading: boolean; ready: boolean;
  loading: boolean; loggedIn: boolean; cost: number; enabled: boolean | undefined; editEnabled: boolean; balance: number | null }>()
const emit = defineEmits<{ generate: []; upload: [file: File]; removeReference: []; editReference: [] }>()
const { t } = useI18n()
const input = ref<HTMLInputElement>()
const dragging = ref(false)
function picked(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('upload', file)
  if (input.value) input.value.value = ''
}
function dropped(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files[0]
  if (file) emit('upload', file)
}
</script>

<template>
  <form class="studio-controls" @submit.prevent="emit('generate')">
    <div class="studio-panel-heading"><h1>{{ t('创作') }}</h1></div>
    <div class="studio-mode" role="group" :aria-label="t('创作模式')">
      <button type="button" :class="{ active: mode === 'generate' }" :aria-pressed="mode === 'generate'" :disabled="busy" @click="mode = 'generate'"><AppIcon name="sparkles" :size="16" />{{ t('文生图') }}</button>
      <button type="button" :class="{ active: mode === 'edit' }" :aria-pressed="mode === 'edit'" :disabled="busy" @click="mode = 'edit'"><AppIcon name="image" :size="16" />{{ t('图生图') }}</button>
    </div>
    <div class="studio-controls-scroll">
      <section v-if="mode === 'edit'" class="studio-field">
        <div class="studio-field-label"><h2>{{ t('参考图片') }}</h2><span>{{ t('单张参考图') }}</span></div>
        <p v-if="!editEnabled" class="studio-inline-note">{{ t('图生图暂不可用，请稍后重试。') }}</p>
        <input ref="input" class="sr-only" type="file" accept="image/png,image/jpeg,image/webp" :aria-label="t('上传参考图')" :disabled="busy || uploading" @change="picked" />
        <div v-if="reference" class="studio-reference">
          <img :src="reference.preview" :alt="t('参考图片')" />
          <div><strong>{{ reference.name }}</strong><span>{{ reference.width }} × {{ reference.height }}</span></div>
          <div class="studio-reference-actions"><button type="button" class="studio-icon" :disabled="busy || uploading" :aria-label="t('编辑参考图')" :title="t('编辑参考图')" @click="emit('editReference')"><AppIcon name="pen" :size="16" /></button><button type="button" class="studio-icon" :disabled="busy || uploading" :aria-label="t('移除参考图')" :title="t('移除参考图')" @click="emit('removeReference')"><AppIcon name="close" :size="16" /></button></div>
        </div>
        <button v-else type="button" class="studio-upload" :class="{ dragging }" :disabled="busy || uploading || !loggedIn" @click="input?.click()" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="!busy && !uploading && loggedIn && dropped($event)">
          <AppIcon :name="uploading ? 'loader' : 'upload'" :size="24" :class="{ spin: uploading }" /><strong>{{ t(uploading ? '正在上传图片' : '点击或拖入参考图') }}</strong><span>PNG / JPG / WebP · {{ t('最大 8 MB') }}</span>
        </button>
        <p class="studio-hint">{{ t('也可以将右侧生成的作品继续用作参考图。') }}</p>
      </section>
      <div class="studio-field">
        <div class="studio-field-label"><label for="studio-prompt">{{ t(mode === 'edit' ? '你想如何修改这张图？' : '描述你想生成的画面') }}</label><span>{{ prompt.length }}/4000</span></div>
        <textarea id="studio-prompt" v-model="prompt" required minlength="2" maxlength="4000" :disabled="busy" :placeholder="t(mode === 'edit' ? '例如：保留主体，把背景换成柔和的日落海边，保持自然光影。' : '描述主体、环境、光线和风格。例如：一间临海的安静书房，午后阳光，电影摄影质感。')" />
        <div v-if="mode === 'generate'" class="studio-prompt-examples"><span>{{ t('灵感') }}</span><button type="button" :disabled="busy" @click="prompt = t('一瓶透明的香水放在浅灰色石台上，旁边有一枝橄榄叶，柔和侧光，简洁高级的产品摄影，无文字。')">{{ t('产品摄影') }}</button><button type="button" :disabled="busy" @click="prompt = t('一只橘猫坐在窗边，窗外是雨后的绿色花园，温暖的自然光，细腻的水彩插画，无文字。')">{{ t('自然插画') }}</button></div>
      </div>
      <fieldset class="studio-field studio-size" :disabled="busy"><legend>{{ t('画面比例') }}</legend><div>
        <label v-for="option in [{value:'1024x1024',label:'方形',ratio:'1:1',aspect:'1'}, {value:'1536x1024',label:'横向',ratio:'3:2',aspect:'1.5'}, {value:'1024x1536',label:'竖向',ratio:'2:3',aspect:'.667'}]" :key="option.value" :class="{ selected: size === option.value }"><input v-model="size" type="radio" name="studio-size" :value="option.value" /><span class="studio-ratio-shape" :style="{ aspectRatio: option.aspect }" /><strong>{{ option.ratio }}</strong><small>{{ t(option.label) }}</small></label>
      </div></fieldset>
      <div class="studio-field"><label for="studio-quality">{{ t('生成质量') }}</label><select id="studio-quality" v-model="quality" :disabled="busy"><option value="low">{{ t('标准 · 更快出图') }}</option><option value="medium">{{ t('精细 · 更多细节') }}</option><option value="high">{{ t('高质量 · 更长等待') }}</option></select></div>
      <label class="studio-transparent"><span><strong>{{ t('透明背景') }}</strong><small>{{ t('适合商品素材、贴纸与设计元素') }}</small></span><input v-model="transparent" type="checkbox" :disabled="busy" role="switch" /></label>
    </div>
    <div class="studio-submit">
      <div><span>{{ t('本次消耗') }}</span><strong>{{ t('{cost} 积分', {cost}) }}</strong></div>
      <NuxtLink v-if="!loading && !loggedIn" to="/login?next=/tools/image-generate" class="studio-button primary">{{ t('登录后创作') }}<AppIcon name="arrow" :size="16" /></NuxtLink>
      <button v-else type="submit" class="studio-button primary" :disabled="!ready"><AppIcon :name="busy ? 'loader' : 'sparkles'" :size="17" :class="{ spin: busy }" />{{ t(busy ? '正在生成' : enabled ? '生成图片' : '暂不可用') }}</button>
      <NuxtLink v-if="balance !== null && balance < cost" to="/account/credits" class="studio-insufficient">{{ t('积分不足，查看积分') }}</NuxtLink>
      <p>{{ t('失败自动退分。输入与参考图会发送给模型服务商。') }}</p>
    </div>
  </form>
</template>
