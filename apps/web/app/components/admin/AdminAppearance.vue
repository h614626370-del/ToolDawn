<script setup lang="ts">
const { t } = useI18n()
const icon = defineModel<string>('icon', { required: true })
const color = defineModel<string>('color', { required: true })
const icons = computed(() => [
  ['wrench', t('工具')], ['image', t('图片')], ['text', t('文字')], ['coffee', t('生活')],
  ['grid', t('分类')], ['code', t('代码')], ['compress', t('压缩')], ['pen', t('编辑')],
  ['scissors', t('裁剪')], ['layers', t('图层')], ['gift', t('礼物')], ['sparkles', t('灵感')],
  ['sun', t('太阳')], ['compass', t('导航')], ['heart', t('喜爱')], ['bookmark', t('收藏')],
])
const colors = computed(() => [['green', t('绿色')], ['blue', t('蓝色')], ['coral', t('珊瑚色')], ['violet', t('紫色')], ['amber', t('金色')]])
</script>

<template>
  <div class="admin-form-grid">
    <label class="admin-field"><span>{{ $t('图标') }}</span><span class="admin-icon-select"><AppIcon :name="icon" :size="21" /><select v-model="icon"><option v-for="[value, name] in icons" :key="value" :value="value">{{ name }}</option></select></span></label>
    <fieldset class="admin-color-field"><legend>{{ $t('颜色') }}</legend><div class="admin-swatches"><label v-for="[value, name] in colors" :key="value" :title="name"><input v-model="color" type="radio" :value="value" name="appearance-color" :aria-label="name"><span :class="`tone-${value}`"><AppIcon v-if="color === value" name="check" :size="17" /></span></label></div></fieldset>
  </div>
</template>
