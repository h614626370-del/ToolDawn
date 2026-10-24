<script setup lang="ts">
import type { Ticket } from '~/types/operations'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ admin?: boolean }>()
const { t, locale } = useI18n()
const base = props.admin ? '/api/v1/admin/tickets' : '/api/v1/tickets'
const status = ref('')
const search = ref('')
const offset = ref(0)
const query = computed(() => ({ status: status.value || undefined, q: search.value, offset: offset.value, limit: 20 }))
watch([status, search], () => { offset.value = 0 })
const { result, pending, error, refresh } = useApiList<Ticket>(base, query)
const states: Record<string, string> = { open: '待处理', processing: '处理中', replied: '已回复', closed: '已关闭' }
const categories: Record<string, string> = { general: '其他问题', billing: '充值与积分', tool: '工具使用', account: '账号问题' }
const creating = ref(false)
const subject = ref('')
const category = ref('general')
const body = ref('')
const createKey = ref('')
const replyKey = ref('')
const selected = ref<Ticket | null>(null)
const replyBody = ref('')
const busy = ref(false)
const actionError = ref('')
const selectionStatus = ref('replied')
function create() {
  subject.value = body.value = ''; category.value = 'general'; actionError.value = ''
  createKey.value = crypto.randomUUID(); creating.value = true
}
async function submit() {
  busy.value = true; actionError.value = ''
  try {
    const ticket = await $fetch<Ticket>(base, { method: 'POST', body: { subject: subject.value, category: category.value, body: body.value, request_key: createKey.value } })
    creating.value = false
    await refresh()
    selected.value = ticket; replyKey.value = crypto.randomUUID()
    replyBody.value = ''; selectionStatus.value = 'replied'
  } catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = false }
}
async function open(row: Ticket) {
  busy.value = true; actionError.value = ''; replyBody.value = ''
  try {
    selected.value = await $fetch<Ticket>(`${base}/${row.id}`)
    replyKey.value = crypto.randomUUID()
  } catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = false }
}
async function reply() {
  if (!selected.value) return
  busy.value = true; actionError.value = ''
  try {
    selected.value = await $fetch<Ticket>(`${base}/${selected.value.id}/replies`, {
      method: 'POST', body: { body: replyBody.value, revision: selected.value.revision,
        request_key: replyKey.value, ...(props.admin ? { status: selectionStatus.value } : {}) },
    })
    replyBody.value = ''; replyKey.value = crypto.randomUUID()
    await refresh()
  } catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = false }
}
async function state(next: string) {
  if (!selected.value) return
  busy.value = true; actionError.value = ''
  try {
    selected.value = await $fetch<Ticket>(`${base}/${selected.value.id}`, { method: 'PATCH', body: { status: next, revision: selected.value.revision } })
    await refresh()
  } catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <section>
    <form class="admin-toolbar" @submit.prevent="refresh">
      <input v-model.lazy="search" class="filter-input" maxlength="100" :aria-label="$t('搜索工单')" :placeholder="$t('搜索工单')">
      <select v-model="status" :aria-label="$t('工单状态')"><option value="">{{ $t('全部状态') }}</option><option v-for="(name, key) in states" :key="key" :value="key">{{ $t(name) }}</option></select>
      <button class="icon-button" :title="$t('刷新')" :aria-label="$t('刷新')" :disabled="pending"><AppIcon name="refresh" :size="18" /></button>
      <button v-if="!admin" type="button" class="button primary toolbar-end" @click="create"><AppIcon name="plus" :size="17" />{{ $t('新建工单') }}</button>
    </form>
    <p v-if="actionError && !selected && !creating" class="form-error" role="alert">{{ actionError }}</p>
    <AsyncState v-if="error" kind="error" :description="error" @retry="refresh" />
    <AsyncState v-else-if="pending" kind="loading" />
    <AsyncState v-else-if="!result.items.length" kind="empty" :title="$t('暂无工单')" />
    <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th>{{ $t('主题') }}</th><th v-if="admin">{{ $t('用户') }}</th><th>{{ $t('问题类型') }}</th><th>{{ $t('状态') }}</th><th>{{ $t('更新时间') }}</th><th>{{ $t('操作') }}</th></tr></thead><tbody><tr v-for="row in result.items" :key="row.id"><td><button class="text-button ticket-subject" :disabled="busy" @click="open(row)">{{ row.subject }}</button></td><td v-if="admin">{{ row.email }}</td><td>{{ $t(categories[row.category] || row.category) }}</td><td><span class="status-tag" :class="row.status">{{ $t(states[row.status] || row.status) }}</span></td><td>{{ new Date(row.updated_at).toLocaleString(locale) }}</td><td><button class="icon-button" :disabled="busy" :title="$t('打开工单')" :aria-label="$t('打开工单')" @click="open(row)"><AppIcon name="arrow" :size="17" /></button></td></tr></tbody></table></div>
    <AdminPagination :total="result.total" :offset="offset" :limit="20" :busy="pending" @change="offset = $event" />
    <AdminDialog v-if="creating" :title="$t('新建工单')" :busy="busy" @close="creating = false"><form class="admin-editor" @submit.prevent="submit">
      <label class="admin-field"><span>{{ $t('主题') }}</span><input v-model="subject" required minlength="2" maxlength="120"></label>
      <label class="admin-field"><span>{{ $t('问题类型') }}</span><select v-model="category"><option v-for="(name, key) in categories" :key="key" :value="key">{{ $t(name) }}</option></select></label>
      <label class="admin-field"><span>{{ $t('问题描述') }}</span><textarea v-model="body" rows="7" required minlength="2" maxlength="5000" /></label>
      <p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p><div class="admin-editor-actions"><button class="button primary" :disabled="busy"><AppIcon name="send" :size="17" />{{ $t('提交工单') }}</button></div>
    </form></AdminDialog>
    <AdminDialog v-if="selected" :title="selected.subject" :busy="busy" @close="selected = null">
      <div class="admin-editor">
        <div class="ticket-meta"><span class="status-tag" :class="selected.status">{{ $t(states[selected.status] || selected.status) }}</span><span>{{ $t(categories[selected.category] || selected.category) }}</span><button class="icon-button" :disabled="busy" :title="$t('刷新')" :aria-label="$t('刷新')" @click="open(selected)"><AppIcon name="refresh" :size="17" /></button><button class="text-button" :disabled="busy" @click="state(selected.status === 'closed' ? 'open' : 'closed')">{{ selected.status === 'closed' ? $t('重新打开') : $t('关闭工单') }}</button></div>
        <div class="ticket-thread"><article v-for="message in selected.messages" :key="message.id" :class="{ staff: message.staff }"><header><strong>{{ message.staff ? $t('客服') : message.author }}</strong><time>{{ new Date(message.created_at).toLocaleString(locale) }}</time></header><p>{{ message.body }}</p></article></div>
        <p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p>
        <form v-if="selected.status !== 'closed'" @submit.prevent="reply"><label class="admin-field"><span>{{ $t('回复内容') }}</span><textarea v-model="replyBody" required rows="4" maxlength="5000" /></label><div class="ticket-reply-actions"><select v-if="admin" v-model="selectionStatus" :aria-label="$t('回复后状态')"><option v-for="(name, key) in states" :key="key" :value="key">{{ $t(name) }}</option></select><button class="button primary" :disabled="busy"><AppIcon name="send" :size="17" />{{ $t('发送回复') }}</button></div></form>
      </div>
    </AdminDialog>
  </section>
</template>
