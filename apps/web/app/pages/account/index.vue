<script setup lang="ts">
const { t, locale } = useI18n()
import { authError } from '~/composables/useAuth'
import type { AuthUser } from '~/types/auth'
definePageMeta({ middleware: 'account' })
const auth = useAuth()
const displayName = ref('')
const notice = ref('')
const pending = ref(true)
const busy = ref(false)
const error = ref('')
useSeoMeta({ title: () => t('我的账户 · ToolDawn'), robots: 'noindex, nofollow' })

async function load() {
  pending.value = true
  error.value = ''
  try {
    if (!(await auth.refresh(5000))) await navigateTo('/login?next=/account', { replace: true })
    displayName.value = auth.user.value?.display_name || ''
  } catch (cause) { error.value = authError(cause) } finally { pending.value = false }
}
async function logout() {
  busy.value = true
  error.value = ''
  try { await auth.logout(); await navigateTo('/') } catch (cause) {
    error.value = authError(cause)
  } finally { busy.value = false }
}
onMounted(load)
async function save() {
  busy.value = true; error.value = ''; notice.value = ''
  try {
    auth.user.value = await $fetch<AuthUser>('/api/v1/me/profile', { method: 'PATCH', body: { display_name: displayName.value } })
    notice.value = t('个人信息已保存。')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <div class="container account-page">
    <NuxtLink to="/" class="back-link"><AppIcon name="back" :size="16" />{{ $t('返回工具导航') }}</NuxtLink>
    <h1>{{ $t('我的账户') }}</h1>
    <AccountNav />
    <AsyncState v-if="pending" kind="loading" :title="$t('正在读取账户')" />
    <AsyncState v-else-if="error && !auth.user.value" kind="error" :description="error" @retry="load" />
    <template v-else-if="auth.user.value">
      <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
      <form class="settings-section narrow-form" @submit.prevent="save"><label class="admin-field"><span>{{ $t('昵称') }}</span><input v-model="displayName" maxlength="60" autocomplete="nickname"></label><button class="button primary" :disabled="busy"><AppIcon name="save" :size="17" />{{ $t('保存更改') }}</button></form>
      <dl class="account-details">
        <div><dt>{{ $t('邮箱地址') }}</dt><dd>{{ auth.user.value.email }}</dd></div>
        <div><dt>{{ $t('账户身份') }}</dt><dd>{{ auth.user.value.role === 'admin' ? $t('管理员') : $t('普通用户') }}</dd></div>
        <div><dt>{{ $t('加入日期') }}</dt><dd>{{ new Date(auth.user.value.created_at).toLocaleDateString(locale === 'en' ? 'en-US' : 'zh-CN') }}</dd></div>
      </dl>
      <div class="account-actions">
        <NuxtLink to="/account/credits" class="button primary"><AppIcon name="wallet" :size="17" />{{ $t('积分与充值') }}</NuxtLink>
        <NuxtLink v-if="auth.user.value.role === 'admin'" to="/admin" class="button primary"><AppIcon name="shield" :size="17" />{{ $t('管理后台') }}</NuxtLink>
        <NuxtLink to="/tools?saved=1" class="button secondary"><AppIcon name="bookmark" :size="17" />{{ $t('我的收藏') }}</NuxtLink>
        <button class="button secondary" :disabled="busy" @click="logout"><AppIcon :name="busy ? 'loader' : 'logout'" :size="17" :class="{ spin: busy }" />{{ $t('退出登录') }}</button>
      </div>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    </template>
  </div>
</template>
