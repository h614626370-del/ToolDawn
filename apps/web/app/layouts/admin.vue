<script setup lang="ts">
const { t } = useI18n()
const auth = useAuth()
const route = useRoute()
const busy = ref(false)
const error = ref('')
const items = computed(() => [
  { path: '', icon: 'chart', name: '仪表盘' }, { path: '/monitoring', icon: 'activity', name: '系统监控' },
  { path: '/tools', icon: 'wrench', name: '工具管理' }, { path: '/categories', icon: 'grid', name: '分类管理' },
  ...(auth.user.value?.is_superadmin ? [{ path: '/model-accounts', icon: 'key', name: '模型账号' }] : []),
  { path: '/users', icon: 'user', name: '用户管理' }, { path: '/usage', icon: 'history', name: '使用记录' },
  { path: '/orders', icon: 'receipt', name: '支付订单' }, { path: '/tickets', icon: 'support', name: '工单管理' },
  { path: '/audit', icon: 'shield', name: '操作日志' },
  ...(auth.user.value?.is_superadmin ? [{ path: '/settings', icon: 'settings', name: '系统设置' }] : []),
])
async function logout() {
  busy.value = true
  try { await auth.logout(); await navigateTo('/login') } catch { error.value = t('退出失败，请重试。') }
  finally { busy.value = false }
}
useSeoMeta({ robots: 'noindex, nofollow' })
</script>

<template>
  <div class="admin-shell">
    <a href="#main-content" class="skip-link">{{ $t('跳到主要内容') }}</a>
    <header class="admin-header">
      <NuxtLink to="/admin" class="brand"><AppIcon name="sun" :size="26" />ToolDawn<span class="admin-wordmark">{{ $t('管理后台') }}</span></NuxtLink>
      <div class="admin-header-actions"><LanguageSelect /><NuxtLink to="/" class="admin-return" :aria-label="$t('返回网站')" :title="$t('返回网站')"><AppIcon name="external" :size="16" /><span>{{ $t('返回网站') }}</span></NuxtLink></div>
    </header>
    <aside class="admin-sidebar">
      <nav :aria-label="$t('后台导航')">
        <NuxtLink v-for="item in items" :key="item.path" :to="`/admin${item.path}`" :class="{ active: route.path === `/admin${item.path}` }"><AppIcon :name="item.icon" :size="19" />{{ $t(item.name) }}</NuxtLink>
      </nav>
      <div class="admin-identity"><NuxtLink to="/account/security" :title="$t('账户安全')"><AppIcon name="shield" :size="20" /></NuxtLink><span>{{ auth.user.value?.email }}</span><button class="icon-button" :disabled="busy" :title="$t('退出登录')" :aria-label="$t('退出登录')" @click="logout"><AppIcon name="logout" :size="18" /></button><p v-if="error" role="alert">{{ error }}</p></div>
    </aside>
    <main id="main-content" class="admin-main"><slot /></main>
  </div>
</template>
