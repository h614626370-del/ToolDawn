<script setup lang="ts">
import type { EmailChallenge } from '~/types/auth'
import { authError } from '~/composables/useAuth'

const { t } = useI18n()
const auth = useAuth()
useSeoMeta({ title: () => t('找回密码 · ToolDawn'), robots: 'noindex, nofollow' })
const email = ref('')
const code = ref('')
const password = ref('')
const confirmation = ref('')
const challenge = ref<EmailChallenge | null>(null)
const busy = ref(false)
const error = ref('')
const sent = ref(false)
const complete = ref(false)
const seconds = ref(0)
let deadline = 0
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => { seconds.value = Math.max(0, Math.ceil((deadline - Date.now()) / 1000)) }, 500)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })

async function send() {
  if (busy.value || seconds.value > 0) return
  busy.value = true
  error.value = ''
  sent.value = false
  try {
    challenge.value = await $fetch<EmailChallenge>('/api/v1/auth/password-reset/code', {
      method: 'POST', body: { email: email.value.trim().toLowerCase() },
    })
    code.value = ''
    deadline = Date.now() + challenge.value.resend_after * 1000
    seconds.value = challenge.value.resend_after
    sent.value = true
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
  if (sent.value) {
    await nextTick()
    document.getElementById('reset-code')?.focus()
  }
}

function changeEmail() {
  challenge.value = null
  code.value = ''
  password.value = ''
  confirmation.value = ''
  error.value = ''
  sent.value = false
}

async function submit() {
  if (busy.value) return
  if (!challenge.value) return send()
  error.value = ''
  if (password.value !== confirmation.value) {
    error.value = t('两次输入的密码不一致。')
    return
  }
  busy.value = true
  try {
    await $fetch('/api/v1/auth/password-reset', {
      method: 'POST', body: {
        email: email.value.trim().toLowerCase(), challenge_id: challenge.value.challenge_id,
        code: code.value, new_password: password.value,
      },
    })
    password.value = ''
    confirmation.value = ''
    code.value = ''
    // The reset may target a different account from the current browser session.
    try { await auth.refresh() } catch { auth.user.value = null; auth.loaded.value = false }
    complete.value = true
    await nextTick()
    document.getElementById('reset-success')?.focus()
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <div class="container auth-page">
    <NuxtLink to="/login" class="back-link"><AppIcon name="back" :size="16" />{{ $t('返回登录') }}</NuxtLink>
    <section class="auth-content" aria-labelledby="reset-title">
      <AppIcon name="key" :size="34" class="auth-mark" />
      <h1 id="reset-title">{{ $t('找回密码') }}</h1>
      <template v-if="complete">
        <p id="reset-success" class="form-notice" role="status" tabindex="-1">{{ $t('密码已重置，所有旧会话已退出。请使用新密码登录。') }}</p>
        <NuxtLink to="/login" class="button primary login-submit">{{ $t('返回登录') }}</NuxtLink>
      </template>
      <template v-else>
        <p class="auth-description">{{ $t('验证账户邮箱后，设置一个新密码。') }}</p>
        <form class="login-form" @submit.prevent="submit">
          <div class="form-field">
            <label for="reset-email">{{ $t('邮箱地址') }}</label>
            <input id="reset-email" v-model="email" type="email" autocomplete="email" maxlength="254" placeholder="you@example.com" required :readonly="!!challenge" :disabled="busy">
          </div>
          <template v-if="challenge">
            <div class="code-email-actions">
              <button type="button" class="text-button" :disabled="busy" @click="changeEmail">{{ $t('更换邮箱') }}</button>
              <button type="button" class="text-button" :disabled="busy || seconds > 0" @click="send">{{ seconds ? $t('{value0} 秒后重发', { value0: seconds }) : $t('重新发送') }}</button>
            </div>
            <div class="form-field">
              <label for="reset-code">{{ $t('验证码') }}</label>
              <input id="reset-code" v-model="code" type="text" inputmode="numeric" pattern="[0-9]{6}" minlength="6" maxlength="6" autocomplete="one-time-code" :placeholder="$t('6 位数字')" required :disabled="busy" :aria-describedby="sent ? 'reset-notice' : undefined">
            </div>
            <div class="form-field">
              <label for="reset-password">{{ $t('新密码') }}</label>
              <input id="reset-password" v-model="password" type="password" autocomplete="new-password" minlength="6" maxlength="128" :title="$t('密码长度为 6–128 个字符。')" required :disabled="busy" aria-describedby="reset-password-hint">
              <small id="reset-password-hint">{{ $t('密码长度为 6–128 个字符。') }}</small>
            </div>
            <div class="form-field">
              <label for="reset-confirmation">{{ $t('确认新密码') }}</label>
              <input id="reset-confirmation" v-model="confirmation" type="password" autocomplete="new-password" minlength="6" maxlength="128" required :disabled="busy">
            </div>
          </template>
          <p v-if="sent" id="reset-notice" class="form-notice" role="status">{{ $t('如果该邮箱对应可找回的账户，我们已发送验证码，10 分钟内有效。') }}</p>
          <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          <button class="button primary login-submit" type="submit" :disabled="busy || (!challenge && seconds > 0)" :aria-busy="busy">
            {{ busy ? $t('请稍候') : challenge ? $t('重置密码') : seconds ? $t('{value0} 秒后重发', { value0: seconds }) : $t('获取验证码') }}
          </button>
        </form>
      </template>
    </section>
  </div>
</template>
