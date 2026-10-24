import type { TextRun, TextToolConfig } from '~/types/ai-tools'
import { authError } from '~/composables/useAuth'

export function useTextTool(config: TextToolConfig) {
  const { locale, t } = useI18n()
  const auth = useAuth()
  const text = ref('')
  const context = ref('')
  const style = ref(config.styles[0] || '自然')
  const language = ref(config.slug === 'text-translate' ? 'en' : locale.value)
  const balance = ref<number | null>(null)
  const busy = ref(false)
  const loading = ref(true)
  const error = ref('')
  const feedback = ref('')
  const active = shallowRef<TextRun | null>(null)
  const history = shallowRef<TextRun[]>([])
  let requestKey = ''
  let signature = ''
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let polls = 0
  const endpoint = `/api/v1/ai-tools/${config.slug}/runs`

  async function load() {
    if (!auth.user.value) return
    const [wallet, records] = await Promise.all([
      $fetch<{ balance: number }>('/api/v1/billing/wallet'),
      $fetch<TextRun[]>(endpoint),
    ])
    if (stopped) return
    balance.value = wallet.balance
    history.value = records
    return records
  }

  function schedule() {
    if (timer) clearTimeout(timer)
    if (stopped || ++polls > 30) {
      busy.value = false
      error.value = t('请刷新记录查看任务状态，重复提交同一内容不会重复扣分。')
      return
    }
    timer = setTimeout(async () => {
      try {
        const records = await load()
        const run = records?.find(item => item.id === active.value?.id)
        if (run) active.value = run
        if (active.value?.status === 'running') schedule()
        else busy.value = false
      } catch (cause) {
        error.value = authError(cause)
        busy.value = false
      }
    }, 5000)
  }

  async function refresh() {
    error.value = ''
    try {
      const records = await load()
      const running = records?.find(item => item.status === 'running')
      if (running) {
        active.value = running
        busy.value = true
        polls = 0
        schedule()
      } else if (active.value?.status === 'running') {
        active.value = records?.find(item => item.id === active.value?.id) || null
        busy.value = false
      }
    } catch (cause) { error.value = authError(cause) }
  }

  async function generate() {
    if (busy.value || text.value.trim().length < 2 || !auth.user.value || !config.enabled) return
    busy.value = true
    error.value = ''
    feedback.value = ''
    const body = { text: text.value.trim(), context: context.value, style: style.value, language: language.value }
    const nextSignature = JSON.stringify(body)
    if (nextSignature !== signature || active.value?.status === 'failed' || active.value?.status === 'succeeded') {
      requestKey = crypto.randomUUID()
      signature = nextSignature
    }
    active.value = null
    try {
      active.value = await $fetch<TextRun>(endpoint, {
        method: 'POST', body: { ...body, request_key: requestKey }, timeout: 80000, retry: 0,
      })
      await load()
      if (active.value.status === 'running') { polls = 0; schedule() }
      else busy.value = false
    } catch (cause) {
      error.value = authError(cause)
      busy.value = false
      // An interrupted response may still have completed on the server.
      try {
        const records = await load()
        const recovered = records?.find(item => item.request_key === requestKey)
        if (recovered) {
          active.value = recovered
          error.value = ''
          if (recovered.status === 'running') { busy.value = true; polls = 0; schedule() }
        }
      } catch { /* Keep the original actionable error. */ }
    }
  }

  function sample() {
    text.value = locale.value === 'zh' ? config.sample_zh : config.sample_en
    if (config.slug === 'text-translate') language.value = locale.value === 'zh' ? 'en' : 'zh'
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(active.value?.output || '')
      feedback.value = t('已复制')
    } catch { feedback.value = t('复制失败，请手动选择结果复制。') }
  }

  function download() {
    if (!active.value?.output) return
    const url = URL.createObjectURL(new Blob([active.value.output], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `tooldawn-${config.slug}.txt`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function clearOutput() {
    if (!active.value || busy.value) return
    try {
      await $fetch(`/api/v1/ai-tools/runs/${active.value.id}/output`, { method: 'DELETE' })
      active.value = null
      await load()
    } catch (cause) { error.value = authError(cause) }
  }

  onMounted(async () => {
    try {
      await auth.refresh()
      await refresh()
    } catch (cause) { error.value = authError(cause) }
    finally { loading.value = false }
  })
  watch(() => auth.user.value?.id, () => {
    history.value = []
    active.value = null
    balance.value = null
    if (timer) clearTimeout(timer)
    busy.value = false
  })
  onBeforeUnmount(() => { stopped = true; if (timer) clearTimeout(timer) })
  return {
    auth, text, context, style, language, balance, busy, loading, error, feedback,
    active, history, generate, sample, copy, download, clearOutput, refresh,
  }
}
