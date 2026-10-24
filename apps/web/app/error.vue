<script setup lang="ts">
import type { NuxtError } from '#app'
defineProps<{ error: NuxtError }>()
</script>

<template>
  <NuxtLayout><div class="container error-page"><AppIcon name="compass" :size="44" /><p class="muted">{{ error.statusCode }}</p><h1>{{ error.statusCode === 404 ? $t('这个页面还没有日出') : error.statusCode === 403 ? $t('需要管理员权限') : $t('页面暂时无法打开') }}</h1><p>{{ error.statusCode === 404 ? $t('检查一下地址，或回到目录继续找工具。') : error.statusCode === 403 ? $t('当前账户没有此页面的访问权限。') : $t('稍后再试，或回到首页。') }}</p><button class="button primary" @click="clearError({ redirect: '/' })"><AppIcon name="back" :size="17" />{{ $t('返回首页') }}</button></div></NuxtLayout>
</template>
