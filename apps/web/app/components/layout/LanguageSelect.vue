<script setup lang="ts">
const { locale, setLocale } = useI18n()
const preference = useCookie<string>('tooldawn_locale', { sameSite: 'lax', maxAge: 31536000 })
async function change(value: string) {
  const next = value === 'en' ? 'en' : 'zh'
  await setLocale(next)
  preference.value = next
}
</script>

<template>
  <label class="language-select">
    <AppIcon name="globe" :size="17" />
    <span class="sr-only">{{ $t('界面语言') }}</span>
    <select :value="locale" @change="change(($event.target as HTMLSelectElement).value)">
      <option value="zh">{{ $t('中文') }}</option>
      <option value="en">English</option>
    </select>
  </label>
</template>
