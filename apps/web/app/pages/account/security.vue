<script setup lang="ts">
import type { AuthUser } from '~/types/auth'
import { authError } from '~/composables/useAuth'
definePageMeta({ middleware: 'account', layout: 'account' })
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
const loading = ref(true)
useSeoMeta({ title: () => t('账户安全'), robots: 'noindex, nofollow' })
async function load() {
  loading.value = true
  try {
    const user = await auth.refresh(5000)
    email.value = user?.email || ''
    sessions.value = await $fetch<{ created_at: string; expires_at: string; current: boolean }[]>('/api/v1/me/sessions')
  } catch (cause) { error.value = authError(cause) }
  finally { loading.value = false }
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
  <div>
    <AccountHeading title="账户安全" description="管理登录凭据，确认账户只在信任的地方使用。" />
    <p v-if="auth.user.value?.must_change_password" class="account-notice" role="status">{{ $t('首次登录，请先修改初始密码。') }}</p>
    <p v-if="notice" class="account-notice" role="status">{{ notice }}</p><p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <div class="account-security-grid">
      <section class="account-panel"><div class="account-section-title"><h2>{{ $t('登录与密码') }}</h2><p>{{ $t('修改密码后，其他登录会话将自动退出。') }}</p></div>
        <div class="account-login-identity"><AppIcon name="mail" :size="20" /><div><small>{{ $t('登录邮箱') }}</small><strong>{{ auth.user.value?.email || '—' }}</strong></div></div>
        <form @submit.prevent="save"><label v-if="auth.user.value?.is_superadmin" class="admin-field"><span>{{ $t('登录邮箱') }}</span><input v-model="email" type="email" required maxlength="254" autocomplete="username" :disabled="busy"></label><label v-if="auth.user.value?.has_password" class="admin-field"><span>{{ $t('当前密码') }}</span><input v-model="current" type="password" required maxlength="128" autocomplete="current-password" :disabled="busy"></label><label class="admin-field"><span>{{ $t('新密码') }}</span><input v-model="password" type="password" required minlength="6" maxlength="128" :title="$t('密码长度为 6–128 个字符。')" aria-describedby="password-policy" autocomplete="new-password" :disabled="busy"><small id="password-policy">{{ $t('密码长度为 6–128 个字符。') }}</small></label><label class="admin-field"><span>{{ $t('确认新密码') }}</span><input v-model="confirm" type="password" required minlength="6" maxlength="128" autocomplete="new-password" :disabled="busy"></label><button class="button primary" :disabled="busy"><AppIcon name="shield" :size="16" />{{ $t('保存更改') }}</button></form>
      </section>
      <section class="account-panel"><div class="account-section-title"><h2>{{ $t('登录会话') }}</h2><p>{{ $t('检查登录时间，及时退出不再使用的会话。') }}</p></div><p v-if="loading" role="status">{{ $t('正在加载') }}</p><div v-else-if="!sessions.length" class="account-empty"><p>{{ $t('暂无登录会话') }}</p></div><article v-for="(session,index) in sessions" :key="index" class="account-session"><span class="account-session-icon"><AppIcon name="shield" :size="20" /></span><div><strong>{{ $t(session.current ? '当前会话' : '其他会话') }}</strong><p>{{ $t('登录时间') }} · {{ new Date(session.created_at).toLocaleString(locale) }}</p><p>{{ $t('到期时间') }} · {{ new Date(session.expires_at).toLocaleString(locale) }}</p></div><AppIcon v-if="session.current" name="check" :size="18" /></article><button class="button secondary" :disabled="busy || !sessions.some(item => !item.current)" @click="revoke"><AppIcon name="logout" :size="16" />{{ $t('退出其他登录') }}</button></section>
    </div>
  </div>
</template>
