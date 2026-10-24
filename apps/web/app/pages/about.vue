<script setup lang="ts">
const { t } = useI18n()
useSeoMeta({ title: () => t('关于 · ToolDawn') })
</script>

<template>
  <div class="container prose-page"><NuxtLink to="/" class="back-link"><AppIcon name="back" :size="16" />{{ $t('返回首页') }}</NuxtLink><h1>{{ $t('关于 ToolDawn') }}</h1><p>{{ $t('ToolDawn 是一个在线工具目录，收录图片处理、文字写作、日常生活与实用工具，让你按用途找到需要的工具。') }}</p><h2>{{ $t('工具与收录') }}</h2><p>{{ $t('标注“站外工具”的项目会带你前往第三方网站。标注“开发中”的本站工具尚未开放使用，完成后将提供独立工作台。') }}</p><h2>{{ $t('留住常用工具') }}</h2><p>{{ $t('收藏保存在当前浏览器，不需要登录，也不会跨设备同步。清除浏览器数据后，收藏会被移除。') }}</p></div>
</template>
