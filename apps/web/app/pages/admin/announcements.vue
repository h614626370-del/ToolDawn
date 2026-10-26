<script setup lang="ts">
import type { Announcement } from '~/types/announcements'
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t, locale } = useI18n()
useSeoMeta({ title: () => `${t('公告管理')} · ToolDawn` })
const draft = ref('')
const search = ref('')
const status = ref('')
const offset = ref(0)
const limit = 20
const query = computed(() => ({ q: search.value, status: status.value || undefined, offset: offset.value, limit }))
const { result, pending, error, refresh } = useAdminList<Announcement>('announcements', query)
watch([search, status], () => { offset.value = 0 })
const editing = ref(false)
const selected = ref<Announcement | null>(null)
const preview = ref<Announcement | null>(null)
const notice = ref('')
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 30000) })
onBeforeUnmount(() => clearInterval(timer))
function state(item: Announcement) {
  if (item.status === 'draft') return '草稿'
  if (item.status === 'archived') return '已归档'
  if (item.ends_at && Date.parse(item.ends_at) <= now.value) return '已结束'
  if (item.starts_at && Date.parse(item.starts_at) > now.value) return '待展示'
  return '展示中'
}
const date = (value: string) => new Intl.DateTimeFormat(locale.value, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
function edit(item: Announcement | null) { selected.value = item; editing.value = true; notice.value = '' }
async function saved() { editing.value = false; notice.value = t('公告已保存。'); await refresh() }
</script>

<template>
  <div>
    <div class="admin-page-heading"><div><h1>{{ $t('公告管理') }}</h1><p>{{ $t('发布产品更新与维护通知，选择合适的展示时间和提醒方式。') }}</p></div><button class="button primary" @click="edit(null)"><AppIcon name="plus" :size="18" />{{ $t('新增公告') }}</button></div>
    <form class="admin-toolbar" role="search" @submit.prevent="search = draft.trim(); offset = 0">
      <label class="admin-search"><AppIcon name="search" :size="18" /><input v-model="draft" :aria-label="$t('搜索公告标题')" :placeholder="$t('搜索公告标题')" maxlength="100"><button class="icon-button" type="submit" :aria-label="$t('搜索')"><AppIcon name="arrow" :size="18" /></button></label>
      <select v-model="status" :aria-label="$t('公告状态筛选')"><option value="">{{ $t('全部状态') }}</option><option value="draft">{{ $t('草稿') }}</option><option value="active">{{ $t('已发布') }}</option><option value="archived">{{ $t('已归档') }}</option></select>
      <button class="icon-button" type="button" :disabled="pending" :aria-label="$t('刷新')" @click="refresh"><AppIcon name="refresh" :size="18" /></button>
    </form>
    <p v-if="notice" role="status" class="admin-notice">{{ notice }}</p>
    <AsyncState v-if="error" kind="error" :description="error" @retry="refresh" />
    <AsyncState v-else-if="pending" kind="loading" />
    <AsyncState v-else-if="!result.items.length" kind="empty" :title="$t('没有找到公告')" :description="$t('新增公告，或调整筛选条件。')" />
    <div v-else class="admin-table-scroll"><table class="admin-table announcement-admin-table"><thead><tr><th scope="col">{{ $t('公告标题') }}</th><th scope="col">{{ $t('发布状态') }}</th><th scope="col">{{ $t('提醒方式') }}</th><th scope="col">{{ $t('展示时间') }}</th><th scope="col">{{ $t('已读人数') }}</th><th scope="col">{{ $t('操作') }}</th></tr></thead><tbody>
      <tr v-for="item in result.items" :key="item.id"><td><strong>{{ item.title }}</strong><small>{{ $t(item.audience === 'all' ? '所有访客' : '仅登录用户') }}</small></td><td><span class="admin-state" :class="{ enabled: state(item) === '展示中' }">{{ $t(state(item)) }}</span></td><td>{{ $t(item.notify_mode === 'popup' ? '弹窗提醒' : '仅铃铛提醒') }}</td><td><span>{{ item.starts_at ? date(item.starts_at) : $t('立即展示') }}</span><small>{{ item.ends_at ? date(item.ends_at) : $t('长期展示') }}</small></td><td>{{ item.read_count || 0 }}</td><td><div class="admin-row-actions"><button class="icon-button" :aria-label="$t('预览 {value0}', { value0: item.title })" :title="$t('预览')" @click="preview = item"><AppIcon name="eye" :size="17" /></button><button class="icon-button" :aria-label="$t('编辑 {value0}', { value0: item.title })" :title="$t('编辑公告')" @click="edit(item)"><AppIcon name="pen" :size="17" /></button></div></td></tr>
    </tbody></table></div>
    <AdminPagination :total="result.total" :offset="offset" :limit="limit" :busy="pending" @change="offset = $event" />
    <p class="announcement-field-help">{{ $t('已读人数仅统计登录用户对当前版本的确认。游客已读保存在各自浏览器中。') }}</p>
    <AdminAnnouncementEditor v-if="editing" :announcement="selected" @close="editing = false" @saved="saved" />
    <AdminDialog v-if="preview" :title="preview.title" @close="preview = null"><div class="announcement-dialog-content"><AnnouncementBody :content="preview.content" /></div></AdminDialog>
  </div>
</template>
