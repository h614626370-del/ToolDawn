<script setup lang="ts">
import '~/assets/css/account-center.css'
const { selected } = useDirectoryStyle()
const auth = useAuth()
const route = useRoute()
const expanded = ref(false)
watch(() => route.path, () => { expanded.value = false })
const { t } = useI18n()
const logoutError = ref('')
const busy = ref(false)
async function logout() {
  busy.value = true; logoutError.value = ''
  try { await auth.logout(); await navigateTo('/') } catch { logoutError.value = t('操作失败，请稍后重试。') } finally { busy.value = false }
}
</script>
<template>
  <div class="account-shell directory-palette" :data-directory-style="selected">
    <AppHeader />
    <div class="account-frame">
      <aside class="account-sidebar">
        <NuxtLink to="/tools" class="account-back"><AppIcon name="back" :size="16" />{{ $t('返回工具目录') }}</NuxtLink>
        <div class="account-sidebar-person"><UserAvatar :src="auth.user.value?.avatar_url" :name="auth.user.value?.display_name || auth.user.value?.email" :size="44" /><div><strong>{{ auth.user.value?.display_name || $t('我的账户') }}</strong><small>{{ $t('账户中心') }}</small></div><button class="icon-button account-menu-toggle" :aria-expanded="expanded" aria-controls="account-navigation" :aria-label="$t('账户导航')" @click="expanded = !expanded"><AppIcon name="menu" :size="20" /></button></div>
        <div id="account-navigation" class="account-sidebar-links" :class="{ expanded }"><AccountNav /><div class="account-sidebar-extra"><NuxtLink v-if="auth.user.value?.role === 'admin'" to="/admin"><AppIcon name="shield" :size="17" />{{ $t('管理后台') }}</NuxtLink><button :disabled="busy" @click="logout"><AppIcon name="logout" :size="17" />{{ $t('退出登录') }}</button></div></div>
        <p v-if="logoutError" role="alert" class="form-error">{{ logoutError }}</p>
      </aside>
      <main id="main-content" class="account-content"><slot /></main>
    </div>
  </div>
</template>
