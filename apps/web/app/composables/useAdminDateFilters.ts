/** Local calendar days, with an exclusive end timestamp for the API. */
export function useAdminDateFilters() {
  const { t } = useI18n()
  const draft = reactive({ q: '', start: '', end: '' })
  const filters = ref<{ q: string; start?: string; end?: string }>({ q: '' })
  const filterError = ref('')
  function apply() {
    filterError.value = ''
    if (draft.start && draft.end && draft.start > draft.end) {
      filterError.value = t('开始日期不能晚于结束日期。'); return false
    }
    const end = draft.end ? new Date(`${draft.end}T00:00:00`) : null
    if (end) end.setDate(end.getDate() + 1)
    filters.value = { q: draft.q.trim(), start: draft.start ? new Date(`${draft.start}T00:00:00`).toISOString() : undefined, end: end?.toISOString() }
    return true
  }
  function reset() { Object.assign(draft, { q: '', start: '', end: '' }); apply() }
  return { draft, filters, filterError, apply, reset }
}
