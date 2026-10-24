<script setup lang="ts">
const { slugs, ready } = useFavorites()
const route = useRoute()
const auth = useAuth()
const { data: site } = await useSiteSettings()
onMounted(async () => {
  if (!auth.loaded.value) {
    try { await auth.refresh() } catch { /* Navigation remains usable during an API outage. */ }
  }
})
</script>

<template>
  <a href="#main-content" class="skip-link">{{ $t('跳到主要内容') }}</a>
  <header class="site-header">
    <div class="container header-inner">
      <NuxtLink to="/" class="brand" :aria-label="$t('ToolDawn 首页')">
        <AppIcon name="sun" :size="29" /><span>{{ site.site_name }}</span>
      </NuxtLink>
      <nav class="primary-nav" :aria-label="$t('主导航')">
        <NuxtLink to="/" :class="{ active: route.path === '/' }">{{ $t('工具导航') }}</NuxtLink>
        <NuxtLink to="/tools" :class="{ active: route.path === '/tools' && route.query.saved !== '1' }">{{ $t('全部工具') }}</NuxtLink>
        <NuxtLink to="/tools?sort=recent" class="nav-recent">{{ $t('最近更新') }}</NuxtLink>
      </nav>
      <div class="header-actions">
      <LanguageSelect />
      <NuxtLink to="/tools?saved=1" class="saved-link" :class="{ active: route.query.saved === '1' }">
        <AppIcon name="bookmark" :size="17" /><span>{{ $t('我的收藏') }}</span>
        <span v-if="ready && slugs.length" class="saved-count">{{ slugs.length }}</span>
      </NuxtLink>
      <NuxtLink :to="auth.user.value ? '/account' : '/login'" class="account-link" :aria-label="auth.user.value ? $t('我的账户') : $t('登录')">
        <AppIcon name="user" :size="18" /><span>{{ auth.user.value ? $t('我的账户') : $t('登录') }}</span>
      </NuxtLink>
      </div>
    </div>
  </header>
  <div v-if="site.announcement" class="site-announcement" role="status">{{ site.announcement }}</div>
</template>
