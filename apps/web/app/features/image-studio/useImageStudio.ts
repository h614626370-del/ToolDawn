import { authError } from '~/composables/useAuth'
import type { ImageQuality, ImageRun, ReferenceImage, StudioConfig, StudioMode } from './types'

export function useImageStudio(config: Ref<StudioConfig | null | undefined>) {
  const { t } = useI18n()
  const auth = useAuth()
  const prompt = ref('')
  const mode = ref<StudioMode>('generate')
  const size = ref('1024x1024')
  const quality = ref<ImageQuality>('low')
  const transparent = ref(false)
  const balance = useState<number | null>('studio-balance', () => null)
  const records = ref<ImageRun[]>([])
  const active = ref<ImageRun | null>(null)
  const reference = shallowRef<ReferenceImage | null>(null)
  const submitting = ref(false)
  const uploading = ref(false)
  const loading = ref(true)
  const error = ref('')
  const notice = ref('')
  const workbookVersion = ref(0)
  let autoSelect = true
  const pendingRun = computed(() => records.value.find(run => run.status === 'running')
    || (active.value?.status === 'running' ? active.value : null))
  const busy = computed(() => submitting.value || !!pendingRun.value)
  const cost = computed(() => config.value?.costs?.[quality.value] ?? config.value?.cost ?? 0)
  const enabled = computed(() => mode.value === 'edit' ? config.value?.edit_enabled : config.value?.enabled)
  const ready = computed(() => enabled.value && auth.user.value && !busy.value && !uploading.value && !loading.value
    && prompt.value.trim().length >= 2 && balance.value !== null && balance.value >= cost.value
    && (mode.value !== 'edit' || !!reference.value))
  const endpoint = '/api/v1/image-tools/image-generate/runs'
  let timer: ReturnType<typeof setTimeout> | undefined
  let stopped = false
  let requestKey = ''
  let signature = ''

  async function load() {
    if (!auth.user.value || stopped) return
    const [runs, wallet] = await Promise.all([$fetch<ImageRun[]>(endpoint), $fetch<{ balance: number }>('/api/v1/billing/wallet')])
    if (stopped) return
    records.value = runs
    balance.value = wallet.balance
    active.value = autoSelect ? runs.find(run => run.id === active.value?.id) || runs.find(run => run.status === 'running') || runs[0] || null : null
  }
  function poll() {
    if (timer) clearTimeout(timer)
    if (stopped) return
    timer = setTimeout(async () => {
      try { await load(); error.value = '' } catch (cause) { error.value = authError(cause) }
      if (busy.value) poll()
    }, 4000)
  }
  async function refresh() {
    try { error.value = ''; await load(); if (busy.value) poll() } catch (cause) { error.value = authError(cause) }
  }
  async function generate() {
    if (!ready.value) return
    submitting.value = true
    autoSelect = true
    error.value = ''; notice.value = ''
    const body = { prompt: prompt.value.trim(), mode: mode.value, size: size.value, quality: quality.value,
      background: transparent.value ? 'transparent' : 'auto', reference_id: mode.value === 'edit' ? reference.value?.id : null }
    const next = JSON.stringify(body)
    if (next !== signature || !requestKey) { signature = next; requestKey = crypto.randomUUID() }
    try {
      active.value = await $fetch<ImageRun>(endpoint, { method: 'POST', body: { ...body, request_key: requestKey }, retry: 0 })
      requestKey = ''
      await load()
    } catch (cause) {
      error.value = authError(cause)
      try { await load() } catch { /* Keep the original error and key for a safe retry. */ }
    } finally { submitting.value = false; if (busy.value) poll() }
  }
  async function discardReference() {
    const previous = reference.value
    if (!previous) return
    reference.value = null
    URL.revokeObjectURL(previous.preview)
    try { await $fetch(`/api/v1/image-tools/references/${previous.id}`, { method: 'DELETE' }) }
    catch { /* References also expire automatically. */ }
  }
  async function upload(file: Blob, name = 'reference.png') {
    if (uploading.value || busy.value) return
    if (!auth.user.value) { error.value = t('请先登录。'); return }
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { error.value = t('图片无法读取，请使用静态 PNG、JPG 或 WebP 图片。'); return }
    if (file.size > 8 * 1024 * 1024) { error.value = t('请选择 8 MB 以内的图片。'); return }
    uploading.value = true; error.value = ''; notice.value = ''
    try {
      const value = await $fetch<Omit<ReferenceImage, 'preview' | 'name'>>('/api/v1/image-tools/references', {
        method: 'POST', body: file, headers: { 'Content-Type': file.type }, retry: 0,
      })
      if (stopped) return
      await discardReference()
      reference.value = { ...value, preview: URL.createObjectURL(file), name }
      mode.value = 'edit'
      notice.value = t('参考图已就绪，描述你希望如何修改。')
    } catch (cause) { error.value = authError(cause) }
    finally { uploading.value = false }
  }
  async function useResult() {
    if (!active.value?.output || busy.value || uploading.value) return
    error.value = ''
    const version = workbookVersion.value
    try {
      const blob = await $fetch<Blob>(active.value.output, { responseType: 'blob' })
      if (stopped || version !== workbookVersion.value) return
      await upload(blob, 'generated-image.png')
    } catch (cause) { error.value = authError(cause) }
  }
  async function removeResult() {
    if (!active.value?.output || busy.value) return
    try {
      await $fetch(`/api/v1/image-tools/runs/${active.value.id}/image`, { method: 'DELETE' })
      await load()
    } catch (cause) { error.value = authError(cause) }
  }
  function newWorkbook() {
    if (busy.value || uploading.value || loading.value) return false
    workbookVersion.value++
    autoSelect = false
    prompt.value = ''; mode.value = 'generate'; size.value = '1024x1024'
    quality.value = 'low'; transparent.value = false; active.value = null
    requestKey = ''; signature = ''; error.value = ''
    notice.value = t('已新建空白工作簿，历史作品仍保留。')
    void discardReference()
    return true
  }
  function select(run: ImageRun) { autoSelect = true; active.value = run; notice.value = '' }
  onMounted(async () => {
    try { await auth.refresh(30000); await load(); if (busy.value) poll() }
    catch (cause) { error.value = authError(cause) }
    finally { loading.value = false }
  })
  watch(() => auth.user.value?.id, (next, previous) => {
    if (previous && next !== previous) {
      records.value = []; active.value = null; balance.value = null
      if (reference.value) URL.revokeObjectURL(reference.value.preview)
      reference.value = null
    }
  })
  onBeforeUnmount(() => {
    stopped = true
    if (timer) clearTimeout(timer)
    if (reference.value) URL.revokeObjectURL(reference.value.preview)
  })
  return { auth, prompt, mode, size, quality, transparent, balance, records, active, reference, submitting,
    uploading, loading, error, notice, pendingRun, busy, cost, enabled, ready, generate, refresh, upload,
    discardReference, useResult, removeResult, select, newWorkbook, workbookVersion }
}
