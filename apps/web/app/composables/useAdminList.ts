import type { AdminPage } from '~/types/admin'
import { authError } from './useAuth'

export function useAdminList<T>(resource: string, query: Ref<Record<string, string | number | boolean | undefined>>) {
  const result = shallowRef<AdminPage<T>>({ items: [], total: 0 })
  const pending = ref(true)
  const error = ref('')
  let request = 0
  async function refresh() {
    const current = ++request
    pending.value = true
    error.value = ''
    try {
      const data = await $fetch<AdminPage<T>>(`/api/v1/admin/${resource}`, { query: query.value })
      if (current === request) result.value = data
    } catch (cause) {
      if (current === request) {
        result.value = { items: [], total: 0 }
        error.value = authError(cause)
      }
    } finally { if (current === request) pending.value = false }
  }
  onMounted(refresh)
  watch(query, refresh)
  onBeforeUnmount(() => { request++ })
  return { result, pending, error, refresh }
}
