<script setup lang="ts">
const { t } = useI18n()
const auth = useAuth()
const { data: site } = await useSiteSettings()
const route = useRoute()
const busy = ref(false)
const error = ref('')
const { selected: adminStyle, select: selectStyle } = useAdminStyle()
const collapsed = useCookie<boolean>('tooldawn-admin-collapsed', { default: () => false, path: '/', sameSite: 'lax', maxAge: 31536000 })
const mobileOpen = ref(false)
const isMobile = ref(false)
let mobileMedia: MediaQueryList | undefined
const syncViewport = () => { isMobile.value = mobileMedia?.matches || false }
onMounted(() => {
  mobileMedia = window.matchMedia('(max-width: 760px)')
  syncViewport()
  mobileMedia.addEventListener('change', syncViewport)
})
onBeforeUnmount(() => mobileMedia?.removeEventListener('change', syncViewport))
const items = computed(() => [
  { path: '', icon: 'chart', name: '仪表盘' }, { path: '/monitoring', icon: 'activity', name: '系统监控' },
  { path: '/tools', icon: 'wrench', name: '工具管理' }, { path: '/categories', icon: 'grid', name: '分类管理' },
  ...(auth.user.value?.is_superadmin ? [{ path: '/model-accounts', icon: 'key', name: '模型账号' }] : []),
  { path: '/users', icon: 'user', name: '用户管理' }, { path: '/usage', icon: 'history', name: '使用记录' },
  { path: '/orders', icon: 'receipt', name: '支付管理' }, { path: '/tickets', icon: 'support', name: '工单管理' },
  { path: '/audit', icon: 'shield', name: '操作日志' },
  ...(auth.user.value?.is_superadmin ? [{ path: '/settings', icon: 'settings', name: '系统设置' }] : []),
])
const groups = computed(() => [
  { title: '工作空间', items: items.value.filter(item => ['', '/monitoring', '/tools', '/categories'].includes(item.path)) },
  { title: '运营管理', items: items.value.filter(item => ['/users', '/usage', '/orders', '/tickets'].includes(item.path)) },
  { title: '系统管理', items: items.value.filter(item => ['/model-accounts', '/audit', '/settings'].includes(item.path)) },
])
const pageName = computed(() => items.value.find(item => route.path === `/admin${item.path}`)?.name || '管理后台')
function toggleNavigation() {
  if (isMobile.value) mobileOpen.value = !mobileOpen.value
  else collapsed.value = !collapsed.value
}
watch(() => route.path, () => { mobileOpen.value = false })
async function logout() {
  busy.value = true
  try { await auth.logout(); await navigateTo('/login') } catch { error.value = t('退出失败，请重试。') }
  finally { busy.value = false }
}
useSeoMeta({ robots: 'noindex, nofollow' })
</script>

<template>
  <div class="admin-shell" :data-admin-style="adminStyle" :class="{ 'admin-collapsed': collapsed, 'admin-mobile-open': mobileOpen }" @keydown.esc="mobileOpen = false">
    <a href="#main-content" class="skip-link">{{ $t('跳到主要内容') }}</a>
    <header class="admin-header">
      <div class="admin-breadcrumb"><button class="icon-button admin-nav-toggle" :aria-label="$t('切换导航')" :aria-expanded="isMobile ? mobileOpen : !collapsed" aria-controls="admin-navigation" @click="toggleNavigation"><AppIcon name="grid" :size="18" /></button><span>{{ $t('管理后台') }}</span><span aria-hidden="true">/</span><strong>{{ $t(pageName) }}</strong></div>
      <div class="admin-header-actions"><div class="admin-style-switch" role="group" :aria-label="$t('后台风格')"><button v-for="value in (['sub2api', 'vm2api'] as const)" :key="value" :aria-label="$t(value === 'sub2api' ? '浅色模式' : '深色模式')" :title="$t(value === 'sub2api' ? '浅色模式' : '深色模式')" :aria-pressed="adminStyle === value" @click="selectStyle(value)"><AppIcon :name="value === 'sub2api' ? 'sun' : 'moon'" :size="17" /></button></div><LanguageSelect /><NuxtLink to="/" class="admin-return" :aria-label="$t('返回网站')" :title="$t('返回网站')"><AppIcon name="external" :size="16" /><span>{{ $t('返回网站') }}</span></NuxtLink></div>
    </header>
    <aside class="admin-sidebar">
      <NuxtLink to="/admin" class="admin-brand" :aria-label="`ToolDawn ${$t('管理后台')}`"><span class="admin-brand-mark" :class="{ 'custom-brand-mark': site.site_logo && site.site_logo !== 'default' }"><SiteLogo :variant="site.site_logo" :size="37" /></span><span class="admin-brand-copy"><strong>{{ site.site_name }}</strong><small>{{ $t('管理后台') }}</small></span></NuxtLink>
      <nav id="admin-navigation" :aria-label="$t('后台导航')">
        <div v-for="group in groups" :key="group.title" class="admin-nav-group"><p class="admin-nav-label">{{ $t(group.title) }}</p><NuxtLink v-for="item in group.items" :key="item.path" :to="`/admin${item.path}`" :title="$t(item.name)" :aria-current="route.path === `/admin${item.path}` ? 'page' : undefined" :class="{ active: route.path === `/admin${item.path}` }"><AppIcon :name="item.icon" :size="18" /><span>{{ $t(item.name) }}</span></NuxtLink></div>
      </nav>
      <div class="admin-identity"><NuxtLink to="/account/security" :title="$t('账户安全')"><AppIcon name="shield" :size="20" /></NuxtLink><span>{{ auth.user.value?.email }}</span><button class="icon-button" :disabled="busy" :title="$t('退出登录')" :aria-label="$t('退出登录')" @click="logout"><AppIcon name="logout" :size="18" /></button><p v-if="error" role="alert">{{ error }}</p></div>
    </aside>
    <main id="main-content" class="admin-main"><slot /></main>
  </div>
</template>
