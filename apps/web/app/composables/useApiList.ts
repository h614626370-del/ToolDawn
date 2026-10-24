import type { Page } from '~/types/operations'
import { authError } from './useAuth'

export function useApiList<T>(url: string, query: Ref<Record<string, string | number | undefined>>) {
  const result = shallowRef<Page<T>>({ items: [], total: 0 })
  const pending = ref(true)
  const error = ref('')
  let sequence = 0
  async function refresh() {
    const current = ++sequence
    pending.value = true
    error.value = ''
    try {
      const data = await $fetch<Page<T>>(url, { query: query.value })
      if (current === sequence) result.value = data
    } catch (cause) {
      if (current === sequence) { error.value = authError(cause); result.value = { items: [], total: 0 } }
    } finally { if (current === sequence) pending.value = false }
  }
  onMounted(refresh)
  watch(query, refresh)
  onBeforeUnmount(() => { sequence++ })
  return { result, pending, error, refresh }
}
