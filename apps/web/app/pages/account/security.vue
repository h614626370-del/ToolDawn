<script setup lang="ts">
import type { AuthUser } from '~/types/auth'
import { authError } from '~/composables/useAuth'
definePageMeta({ middleware: 'account' })
const { t, locale } = useI18n()
const auth = useAuth()
const current = ref('')
const password = ref('')
const confirm = ref('')
const email = ref('')
const busy = ref(false)
const error = ref('')
const notice = ref('')
const sessions = ref<{ created_at: string; expires_at: string; current: boolean }[]>([])
useSeoMeta({ title: () => t('账户安全'), robots: 'noindex, nofollow' })
async function load() {
  try {
    const user = await auth.refresh(5000)
    email.value = user?.email || ''
    sessions.value = await $fetch<{ created_at: string; expires_at: string; current: boolean }[]>('/api/v1/me/sessions')
  } catch (cause) { error.value = authError(cause) }
}
onMounted(load)
async function save() {
  error.value = ''; notice.value = ''
  if (password.value !== confirm.value) { error.value = t('两次输入的密码不一致。'); return }
  busy.value = true
  try {
    const superadmin = auth.user.value?.is_superadmin
    auth.user.value = await $fetch<AuthUser>(superadmin ? '/api/v1/me/admin-credentials' : '/api/v1/me/password', {
      method: 'PUT', body: { current_password: current.value, new_password: password.value, ...(superadmin ? { email: email.value } : {}) },
    })
    current.value = password.value = confirm.value = ''
    notice.value = t('凭据已更新，其他登录已退出。')
    await load()
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
async function revoke() {
  busy.value = true; error.value = ''; notice.value = ''
  try {
    await $fetch('/api/v1/me/sessions/others', { method: 'DELETE' })
    notice.value = t('其他登录已退出。')
    await load()
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <div class="container account-page operations-page">
    <h1>{{ $t('账户安全') }}</h1><AccountNav />
    <p v-if="auth.user.value?.must_change_password" class="setup-notice" role="status">{{ $t('首次登录，请先修改初始密码。') }}</p>
    <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <form class="settings-section narrow-form" @submit.prevent="save">
      <h2>{{ auth.user.value?.is_superadmin ? $t('管理员凭据') : $t('修改密码') }}</h2>
      <label v-if="auth.user.value?.is_superadmin" class="admin-field"><span>{{ $t('登录邮箱') }}</span><input v-model="email" type="email" required maxlength="254" autocomplete="username"></label>
      <label v-if="auth.user.value?.has_password" class="admin-field"><span>{{ $t('当前密码') }}</span><input v-model="current" type="password" required maxlength="128" autocomplete="current-password"></label>
      <label class="admin-field"><span>{{ $t('新密码') }}</span><input v-model="password" type="password" required minlength="6" maxlength="128" :title="$t('密码长度为 6–128 个字符。')" aria-describedby="password-policy" autocomplete="new-password"><small id="password-policy">{{ $t('密码长度为 6–128 个字符。') }}</small></label>
      <label class="admin-field"><span>{{ $t('确认新密码') }}</span><input v-model="confirm" type="password" required minlength="6" maxlength="128" autocomplete="new-password"></label>
      <button class="button primary" :disabled="busy"><AppIcon name="save" :size="17" />{{ $t('保存更改') }}</button>
    </form>
    <section class="settings-section"><div class="section-heading"><h2>{{ $t('登录会话') }}</h2><button class="button secondary" :disabled="busy" @click="revoke"><AppIcon name="logout" :size="16" />{{ $t('退出其他登录') }}</button></div>
      <div class="admin-table-scroll"><table class="admin-table"><thead><tr><th>{{ $t('登录时间') }}</th><th>{{ $t('到期时间') }}</th><th>{{ $t('状态') }}</th></tr></thead><tbody><tr v-for="(session, index) in sessions" :key="index"><td>{{ new Date(session.created_at).toLocaleString(locale) }}</td><td>{{ new Date(session.expires_at).toLocaleString(locale) }}</td><td>{{ session.current ? $t('当前会话') : $t('其他会话') }}</td></tr></tbody></table></div>
    </section>
  </div>
</template>
