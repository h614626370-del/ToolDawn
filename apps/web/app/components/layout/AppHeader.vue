<script setup lang="ts">
const route = useRoute()
const directoryPage = computed(() => route.path === '/' || route.path === '/tools' || route.path.startsWith('/tools/'))
const accountPage = computed(() => route.path.startsWith('/account'))
const menuId = useId()
const menu = ref<HTMLElement>()
const menuOpen = ref(false)
function closeMenu() { menu.value?.hidePopover() }
watch(() => route.fullPath, closeMenu)
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
      <button v-if="directoryPage" class="directory-menu-trigger" :popovertarget="menuId" :aria-label="$t('打开工具导航')" :aria-expanded="menuOpen" :aria-controls="menuId"><AppIcon name="menu" :size="22" /></button>
      <NuxtLink to="/" class="brand" :aria-label="$t('ToolDawn 首页')">
        <SiteLogo :variant="site.site_logo" :size="38" /><span>{{ site.site_name }}</span>
      </NuxtLink>
      <nav v-if="!directoryPage && !accountPage" class="primary-nav" :aria-label="$t('主导航')">
        <NuxtLink to="/tools">{{ $t('全部工具') }}</NuxtLink>
      </nav>
      <div class="header-actions">
      <StyleSwitcher v-if="directoryPage || accountPage" />
      <LanguageSelect />
      <AnnouncementCenter />
      <ClientOnly><NuxtLink :to="auth.user.value ? '/account' : '/login'" class="account-link" :aria-label="auth.user.value ? $t('我的账户') : $t('登录')">
        <UserAvatar v-if="auth.user.value" :src="auth.user.value.avatar_url" :name="auth.user.value.display_name || auth.user.value.email" :size="28" /><AppIcon v-else name="user" :size="18" /><span>{{ auth.user.value ? $t('我的账户') : $t('登录') }}</span>
      </NuxtLink><template #fallback><NuxtLink to="/login" class="account-link" :aria-label="$t('登录')"><AppIcon name="user" :size="18" /><span>{{ $t('登录') }}</span></NuxtLink></template></ClientOnly>
      </div>
    </div>
  </header>
  <div v-if="directoryPage" :id="menuId" ref="menu" popover="auto" class="directory-mobile-menu" @toggle="menuOpen = ($event as ToggleEvent).newState === 'open'">
    <div class="directory-menu-heading"><strong>{{ $t('工具导航') }}</strong><button :aria-label="$t('关闭工具导航')" @click="closeMenu"><AppIcon name="close" /></button></div>
    <DirectoryNavigation @navigate="closeMenu" />
  </div>
  <div v-if="site.announcement" class="site-announcement" role="status">{{ site.announcement }}</div>
</template>
