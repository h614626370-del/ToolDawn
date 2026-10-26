<script setup lang="ts">
import type { Announcement, AnnouncementPage } from '~/types/announcements'
const { t, locale } = useI18n()
const auth = useAuth()
const route = useRoute()
const dialog = ref<HTMLDialogElement>()
const titleId = useId()
const mode = ref<'list' | 'detail' | null>(null)
const selected = ref<Announcement | null>(null)
const popup = ref(false)
const data = ref<AnnouncementPage>({ items: [], total: 0, unread_count: 0, popups: [], guest_versions: {} })
const pending = ref(false)
const busy = ref(false)
const error = ref('')
const storageWarning = ref(false)
const offset = ref(0)
const limit = 20
const now = ref(Date.now())
const guestReads = useState<Record<string, number>>('announcement-guest-reads', () => ({}))
const shown = useState<Record<string, boolean>>('announcement-shown', () => ({}))
let request = 0
let refreshTimer: ReturnType<typeof setInterval> | undefined
let previous: HTMLElement | null = null
const identity = computed(() => auth.user.value?.id || 'guest')
const key = (item: Announcement) => `${identity.value}:${item.id}:${item.revision}`
const isVisible = (item: Announcement) => (!item.ends_at || Date.parse(item.ends_at) > now.value) && (item.audience === 'all' || !!auth.user.value)
const items = computed(() => data.value.items.filter(isVisible))
const isRead = (item: Announcement) => auth.user.value ? !!item.read_at : guestReads.value[item.id] === item.revision
const hasUnread = computed(() => auth.user.value ? data.value.unread_count > 0 : Object.entries(data.value.guest_versions || {}).some(([id, revision]) => guestReads.value[id] !== revision))
const pageUnread = computed(() => items.value.filter(item => !isRead(item)))
const date = (value: string) => new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))

function rememberShown(item: Announcement) {
  shown.value[key(item)] = true
  try { sessionStorage.setItem('tooldawn-announcement-shown', JSON.stringify(shown.value)) } catch { /* In-memory dedup still works. */ }
}

function showNext() {
  if (mode.value || !auth.loaded.value || !['/', '/tools'].some(path => route.path === path || (path === '/tools' && route.path.startsWith('/tools/')))) return
  // Do not interrupt typing or another modal.
  if (document.querySelector('dialog[open]') || document.activeElement?.matches('input, textarea, select, [contenteditable="true"]')) return
  const next = data.value.popups.find(item => isVisible(item) && !isRead(item) && !shown.value[key(item)])
  if (next) {
    rememberShown(next)
    selected.value = next
    popup.value = true
    mode.value = 'detail'
  }
}

async function refresh(automatic = false) {
  const current = ++request
  const owner = identity.value
  pending.value = true
  error.value = ''
  try {
    const result = await $fetch<AnnouncementPage>('/api/v1/announcements', { query: { offset: offset.value, limit } })
    if (current !== request || owner !== identity.value) return
    data.value = result
    if (automatic) showNext()
  } catch { if (current === request) error.value = t('公告加载失败，请重试。') }
  finally { if (current === request) pending.value = false }
}

async function openList() {
  selected.value = null
  popup.value = false
  mode.value = 'list'
  await refresh()
}
function openDetail(item: Announcement) {
  selected.value = item
  popup.value = false
  rememberShown(item)
  mode.value = 'detail'
  error.value = ''
}
function close() {
  if (busy.value) return
  mode.value = null
  selected.value = null
  error.value = ''
}
async function markRead(rows: Announcement[], dismiss = false) {
  if (!rows.length || busy.value) return
  busy.value = true
  error.value = ''
  const owner = identity.value
  try {
    if (auth.user.value) {
      await $fetch('/api/v1/announcements/read', { method: 'POST', body: { items: rows.map(({ id, revision }) => ({ id, revision })) } })
    } else {
      for (const row of rows) guestReads.value[row.id] = row.revision
      try { localStorage.setItem('tooldawn-announcement-reads', JSON.stringify(guestReads.value)) }
      catch { storageWarning.value = true }
    }
    if (owner !== identity.value) return
    for (const row of rows) row.read_at = new Date().toISOString()
    await refresh()
    if (dismiss) { mode.value = popup.value ? null : 'list'; selected.value = null }
  } catch { if (owner === identity.value) error.value = t('未能保存已读状态，请重试；公告也可能已更新或下线。') }
  finally { busy.value = false }
}
async function page(value: number) { offset.value = value; await refresh() }
function tick() {
  now.value = Date.now()
  if (selected.value && !isVisible(selected.value)) close()
  if (document.visibilityState === 'visible' && !mode.value && !pending.value) void refresh(true)
}
watch(mode, async value => {
  await nextTick()
  if (value && !dialog.value?.open) {
    previous = document.activeElement as HTMLElement
    dialog.value?.showModal()
  } else if (!value) {
    dialog.value?.close()
    previous?.focus()
  }
})
watch(identity, () => {
  request++
  mode.value = null
  selected.value = null
  offset.value = 0
  data.value = { items: [], total: 0, unread_count: 0, popups: [], guest_versions: {} }
  if (import.meta.client) void refresh(true)
})
watch(() => auth.loaded.value, loaded => { if (loaded && import.meta.client) void refresh(true) })
watch(() => route.path, () => { close(); if (import.meta.client) showNext() })
onMounted(() => {
  try {
    const stored = JSON.parse(localStorage.getItem('tooldawn-announcement-reads') || '{}')
    if (stored && typeof stored === 'object' && !Array.isArray(stored)) guestReads.value = stored
    const seen = JSON.parse(sessionStorage.getItem('tooldawn-announcement-shown') || '{}')
    if (seen && typeof seen === 'object' && !Array.isArray(seen)) shown.value = seen
  } catch { /* Malformed or blocked storage does not block reading announcements. */ }
  if (auth.loaded.value) void refresh(true)
  refreshTimer = setInterval(tick, 60000)
  window.addEventListener('focus', tick)
})
onBeforeUnmount(() => {
  request++
  clearInterval(refreshTimer)
  window.removeEventListener('focus', tick)
  dialog.value?.close()
})
</script>

<template>
  <div class="announcement-center">
    <button class="announcement-bell" :aria-label="hasUnread ? $t('站内公告，有未读') : $t('站内公告')" :title="$t('站内公告')" @click="openList"><AppIcon name="bell" :size="20" /><span v-if="hasUnread" class="announcement-dot" /></button>
    <dialog ref="dialog" class="announcement-dialog" :aria-labelledby="titleId" @cancel.prevent="close" @click="($event.target === dialog) && close()">
      <template v-if="mode">
        <header class="announcement-dialog-heading">
          <div><span class="announcement-eyebrow"><AppIcon name="bell" :size="16" />{{ $t(popup ? '重要公告' : '站内公告') }}</span><h2 :id="titleId">{{ selected?.title || $t('最近消息') }}</h2><p v-if="selected"><time :datetime="selected.updated_at">{{ date(selected.updated_at) }}</time><span v-if="!isRead(selected)"> · {{ $t('未读') }}</span></p><p v-else>{{ $t('产品更新、维护通知，都在这里。') }}</p></div>
          <button class="icon-button" :disabled="busy" :aria-label="$t('关闭公告')" @click="close"><AppIcon name="close" /></button>
        </header>
        <div class="announcement-dialog-content">
          <p v-if="storageWarning" class="announcement-feedback" role="status">{{ $t('浏览器未允许保存，下次访问可能再次提醒。') }}</p>
          <p v-if="error" class="announcement-feedback" role="alert">{{ error }} <button v-if="!selected" class="text-button" :disabled="pending" @click="refresh()">{{ $t('重试') }}</button></p>
          <AnnouncementBody v-if="selected" :content="selected.content" />
          <template v-else>
            <div class="announcement-list-toolbar"><span>{{ $t('共 {count} 条公告', { count: data.total }) }}</span><button class="text-button" :disabled="busy || pending || !pageUnread.length" @click="markRead(pageUnread)">{{ $t('本页标为已读') }}</button></div>
            <p v-if="pending" class="announcement-empty" role="status">{{ $t('正在加载公告…') }}</p>
            <div v-else-if="!items.length && !error" class="announcement-empty"><AppIcon name="bell" :size="28" /><h3>{{ $t('暂时没有公告') }}</h3><p>{{ $t('有新消息时，会在这里提醒你。') }}</p></div>
            <ul v-else class="announcement-list"><li v-for="item in items" :key="item.id"><button @click="openDetail(item)"><span class="announcement-read-indicator" :class="{ unread: !isRead(item) }" /><span class="announcement-list-copy"><strong>{{ item.title }}</strong><span><time :datetime="item.updated_at">{{ date(item.updated_at) }}</time> · {{ $t(isRead(item) ? '已读' : '未读') }}</span></span><AppIcon name="arrow" :size="18" /></button></li></ul>
            <AdminPagination v-if="data.total > limit" :total="data.total" :offset="offset" :limit="limit" :busy="pending || busy" @change="page" />
          </template>
        </div>
        <footer v-if="selected" class="announcement-dialog-actions"><button class="button secondary" :disabled="busy" @click="popup ? close() : openList()">{{ $t(popup ? '稍后再看' : '返回公告列表') }}</button><button class="button primary" :disabled="busy || pending" @click="markRead([selected], true)"><AppIcon :name="busy ? 'loader' : 'check'" :size="17" />{{ $t(busy ? '正在保存…' : '我已阅读') }}</button></footer>
      </template>
    </dialog>
  </div>
</template>
