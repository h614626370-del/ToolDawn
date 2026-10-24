import type { AuthUser, EmailChallenge } from '~/types/auth'

export function authError(error: unknown): string {
  const value = error as { data?: { message?: string } }
  const { t, te } = useNuxtApp().$i18n
  const message = value.data?.message || '暂时无法连接，请稍后重试。'
  return te(message) ? t(message) : t('请求未完成，请稍后重试。')
}

export function useAuth() {
  const user = useState<AuthUser | null>('auth-user', () => null)
  const loaded = useState('auth-loaded', () => false)
  const requestFetch = useRequestFetch()

  async function refresh() {
    try {
      user.value = await requestFetch<AuthUser>('/api/v1/me')
      return user.value
    } catch (error) {
      const value = error as { statusCode?: number; status?: number }
      if ((value.statusCode || value.status) !== 401) throw error
      user.value = null
      return null
    } finally {
      loaded.value = true
    }
  }

  async function sendCode(email: string) {
    return await $fetch<EmailChallenge>('/api/v1/auth/email-code', {
      method: 'POST', body: { email },
    })
  }

  async function verify(email: string, challengeId: string, code: string) {
    user.value = await $fetch<AuthUser>('/api/v1/auth/verify', {
      method: 'POST', body: { email, challenge_id: challengeId, code },
    })
    loaded.value = true
  }

  async function logout() {
    await $fetch('/api/v1/auth/logout', { method: 'POST' })
    user.value = null
    loaded.value = true
  }

  async function passwordLogin(email: string, password: string) {
    user.value = await $fetch<AuthUser>('/api/v1/auth/password', {
      method: 'POST', body: { email, password },
    })
    loaded.value = true
  }

  return { user, loaded, refresh, sendCode, verify, passwordLogin, logout }
}
