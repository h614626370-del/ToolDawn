<script setup lang="ts">
const { t } = useI18n()
import type { EmailChallenge } from '~/types/auth'
import { authError } from '~/composables/useAuth'

const emit = defineEmits<{ success: [] }>()
const auth = useAuth()
const mode = ref<'password' | 'code'>('password')
const password = ref('')
const email = ref('')
const code = ref('')
const challenge = ref<EmailChallenge | null>(null)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const seconds = ref(0)
let deadline = 0
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  timer = setInterval(() => { seconds.value = Math.max(0, Math.ceil((deadline - Date.now()) / 1000)) }, 500)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })

async function send() {
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    challenge.value = await auth.sendCode(email.value.trim().toLowerCase())
    code.value = ''
    deadline = Date.now() + challenge.value.resend_after * 1000
    seconds.value = challenge.value.resend_after
    notice.value = t('验证码已发送，10 分钟内有效。')
    await nextTick()
    document.getElementById('login-code')?.focus()
  } catch (cause) {
    error.value = authError(cause)
  } finally {
    busy.value = false
  }
}

async function submit() {
  if (mode.value === 'password') {
    busy.value = true
    error.value = ''
    try {
      await auth.passwordLogin(email.value.trim().toLowerCase(), password.value)
      password.value = ''
      emit('success')
    } catch (cause) { error.value = authError(cause) }
    finally { busy.value = false }
    return
  }
  if (!challenge.value) return send()
  busy.value = true
  error.value = ''
  try {
    await auth.verify(email.value.trim().toLowerCase(), challenge.value.challenge_id, code.value)
    emit('success')
  } catch (cause) {
    error.value = authError(cause)
  } finally {
    busy.value = false
  }
}

function changeEmail() {
  challenge.value = null
  code.value = ''
  error.value = ''
  notice.value = ''
}
</script>

<template>
  <form class="login-form" @submit.prevent="submit">
    <div class="mode-tabs" role="group" :aria-label="$t('登录方式')">
      <button v-for="item in (['password', 'code'] as const)" :key="item" type="button" :aria-pressed="mode === item" :class="{ active: mode === item }" :disabled="busy" @click="mode = item; changeEmail()">{{ item === 'password' ? $t('密码登录') : $t('验证码登录') }}</button>
    </div>
    <div class="form-field">
      <label for="login-email">{{ $t('邮箱地址') }}</label>
      <input id="login-email" v-model="email" type="email" autocomplete="email" maxlength="254" placeholder="you@example.com" required :readonly="!!challenge" :disabled="busy">
    </div>
    <label v-if="mode === 'password'" class="form-field"><span>{{ $t('密码') }}</span><input v-model="password" type="password" autocomplete="current-password" maxlength="128" required :disabled="busy"></label>
    <NuxtLink v-if="mode === 'password'" to="/forgot-password" class="text-button">{{ $t('忘记密码？') }}</NuxtLink>
    <template v-if="mode === 'code' && challenge">
      <div class="code-email-actions">
        <button type="button" class="text-button" :disabled="busy" @click="changeEmail"><AppIcon name="pen" :size="14" />{{ $t('更换邮箱') }}</button>
        <button type="button" class="text-button" :disabled="busy || seconds > 0" @click="send"><AppIcon name="refresh" :size="14" />{{ seconds ? $t('{value0} 秒后重发', { value0: seconds }) : $t('重新发送') }}</button>
      </div>
      <div class="form-field">
        <label for="login-code">{{ $t('验证码') }}</label>
        <input id="login-code" v-model="code" type="text" inputmode="numeric" pattern="[0-9]{6}" minlength="6" maxlength="6" autocomplete="one-time-code" :placeholder="$t('6 位数字')" required :disabled="busy" aria-describedby="login-notice">
      </div>
    </template>
    <p v-if="notice" id="login-notice" class="form-notice" role="status">{{ notice }}</p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <button class="button primary login-submit" type="submit" :disabled="busy" :aria-busy="busy">
      <AppIcon :name="busy ? 'loader' : challenge ? 'login' : 'mail'" :size="18" :class="{ spin: busy }" />
      {{ busy ? $t('请稍候') : mode === 'password' || challenge ? $t('登录') : $t('获取验证码') }}
    </button>
    <i18n-t v-if="mode === 'code'" keypath="首次验证后自动创建账户。继续即表示你已阅读{privacy}。" tag="p" class="login-terms"><template #privacy><NuxtLink to="/privacy">{{ $t('隐私说明') }}</NuxtLink></template></i18n-t>
  </form>
</template>
