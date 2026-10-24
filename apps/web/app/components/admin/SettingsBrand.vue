<script setup lang="ts">
import type { RuntimeConfig } from '~/types/operations'
const model = defineModel<RuntimeConfig['site_logo']>({ required: true })
defineProps<{ siteName: string }>()
const options = [
  { id: 'speed', number: '03', name: '锐角疾速' },
  { id: 'heritage', number: '04', name: '复古典藏' },
  { id: 'signature', number: '05', name: '自由签名' },
  { id: 'street', number: '10', name: '街头涂写' },
] as const
</script>

<template>
  <section class="settings-section brand-settings">
    <h2>{{ $t('站点 Logo') }}</h2>
    <p class="brand-help">{{ $t('选择预置 Logo，保存后同步应用到前台和后台。') }}</p>
    <fieldset class="brand-presets">
      <legend class="sr-only">{{ $t('站点 Logo') }}</legend>
      <label v-for="option in options" :key="option.id" class="brand-option" :class="{ selected: model === option.id }">
        <img :src="`/images/brand/${option.id}-preview.webp`" alt="" width="640" height="640">
        <span class="brand-option-caption"><input v-model="model" type="radio" name="site-logo" :value="option.id"><span>{{ option.number }} · {{ $t(option.name) }}</span></span>
      </label>
    </fieldset>
    <label class="brand-default"><input v-model="model" type="radio" name="site-logo" value="default">{{ $t('原有太阳标识') }}</label>
    <div class="brand-preview" aria-live="polite">
      <span>{{ $t('实际尺寸预览') }}</span>
      <div class="brand-preview-sample"><SiteLogo :variant="model" :size="40" /><strong>{{ siteName || 'ToolDawn' }}</strong></div>
      <small>{{ $t('已选择，保存后生效') }}</small>
    </div>
  </section>
</template>

<style scoped>
.brand-help { color: var(--muted); font-size: 13px; line-height: 1.7; margin: -5px 0 20px; }
.brand-presets { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; border: 0; padding: 0; margin: 0; }
.brand-option { min-width: 0; border: 2px solid var(--admin-line); border-radius: 10px; overflow: hidden; cursor: pointer; background: var(--admin-panel); }
.brand-option.selected { border-color: var(--admin-accent); }
.brand-option:focus-within { outline: 2px solid var(--admin-accent); outline-offset: 3px; }
.brand-option img { display: block; width: 100%; height: auto; aspect-ratio: 1; object-fit: contain; }
.brand-option-caption { display: flex; align-items: center; gap: 9px; padding: 13px 10px; font-size: 12px; }
.brand-option input, .brand-default input { accent-color: var(--admin-accent-fill); flex-shrink: 0; }
.brand-default { display: flex; gap: 9px; align-items: center; width: fit-content; margin: 20px 0; font-size: 13px; cursor: pointer; }
.brand-preview { display: flex; align-items: center; flex-wrap: wrap; gap: 16px 24px; padding-top: 20px; border-top: 1px solid var(--admin-line); }
.brand-preview > span, .brand-preview small { color: var(--muted); font-size: 12px; }
.brand-preview-sample { display: flex; align-items: center; gap: 10px; }
.brand-preview-sample strong { font-size: 18px; }
@media (max-width: 1000px) { .brand-presets { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 420px) { .brand-presets { gap: 10px; } .brand-option-caption { gap: 6px; padding: 10px 7px; font-size: 11px; } }
</style>
