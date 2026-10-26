<script setup lang="ts">
import type { Ticket } from '~/types/operations'
import { authError } from '~/composables/useAuth'
const props = { admin: false }
const auth = useAuth()
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
    <form class="account-filters" @submit.prevent="refresh"><label class="account-search"><span>{{ $t('搜索工单') }}</span><input v-model.lazy="search" maxlength="100" :placeholder="$t('输入问题主题')"></label><label><span>{{ $t('工单状态') }}</span><select v-model="status"><option value="">{{ $t('全部状态') }}</option><option v-for="(name,key) in states" :key="key" :value="key">{{ $t(name) }}</option></select></label><button class="button secondary" :disabled="pending || busy"><AppIcon name="refresh" :size="16" />{{ $t('刷新') }}</button><button type="button" class="button primary" :disabled="busy" @click="create"><AppIcon name="plus" :size="16" />{{ $t('新建工单') }}</button></form>
    <p v-if="actionError && !selected && !creating" role="alert" class="form-error">{{ actionError }}</p>
    <AsyncState v-if="error" kind="error" :title="$t('暂时无法加载')" :description="error" @retry="refresh" />
    <div v-else class="account-ticket-desk" :class="{ 'has-selection': !!selected }">
      <div class="account-ticket-list"><AsyncState v-if="pending" kind="loading" :title="$t('正在加载')" /><div v-else-if="!result.items.length" class="account-empty"><AppIcon name="support" :size="30" /><h2>{{ $t('暂无工单') }}</h2><p>{{ $t('遇到问题时，可以在这里联系我们。') }}</p></div><button v-for="row in result.items" v-else :key="row.id" class="account-ticket-item" :class="{ selected: selected?.id === row.id }" :disabled="busy" @click="open(row)"><span class="account-status" :data-status="row.status">{{ $t(states[row.status] || row.status) }}</span><strong>{{ row.subject }}</strong><span>{{ $t(categories[row.category] || row.category) }} · {{ new Date(row.updated_at).toLocaleDateString(locale) }}</span></button><AdminPagination :total="result.total" :offset="offset" :limit="20" :busy="pending || busy" @change="offset = $event" /></div>
      <section class="account-ticket-detail" :aria-label="$t('工单详情')">
        <div v-if="!selected" class="account-empty"><AppIcon name="support" :size="32" /><h2>{{ $t('每个问题，都有后续') }}</h2><p>{{ $t('选择一条工单查看回复，或新建工单说明你遇到的问题。') }}</p></div>
        <template v-else><header class="account-thread-header"><button class="text-button account-ticket-back" :disabled="busy" @click="selected = null"><AppIcon name="back" :size="16" />{{ $t('返回工单列表') }}</button><h2>{{ selected.subject }}</h2><div class="account-row-meta"><span class="account-status" :data-status="selected.status">{{ $t(states[selected.status] || selected.status) }}</span><span>{{ $t(categories[selected.category] || selected.category) }}</span><button class="text-button" :disabled="busy" @click="open(selected)">{{ $t('刷新') }}</button><button class="text-button" :disabled="busy" @click="state(selected.status === 'closed' ? 'open' : 'closed')">{{ $t(selected.status === 'closed' ? '重新打开' : '关闭工单') }}</button></div></header>
        <div class="account-ticket-messages"><article v-for="message in selected.messages" :key="message.id" class="account-ticket-message" :class="{ staff: message.staff }"><span v-if="message.staff" class="account-staff-avatar"><AppIcon name="support" :size="18" /></span><UserAvatar v-else :src="auth.user.value?.avatar_url" :name="message.author" :size="34" /><div><header><strong>{{ message.staff ? $t('客服') : message.author }}</strong><time>{{ new Date(message.created_at).toLocaleString(locale) }}</time></header><p>{{ message.body }}</p></div></article></div>
        <p v-if="actionError && !creating" role="alert" class="form-error">{{ actionError }}</p>
        <form v-if="selected.status !== 'closed'" class="account-ticket-reply" @submit.prevent="reply"><label class="admin-field"><span>{{ $t('回复内容') }}</span><textarea v-model="replyBody" required minlength="1" rows="4" maxlength="5000" :disabled="busy" :placeholder="$t('补充问题细节，方便我们继续处理。')" /></label><button class="button primary" :disabled="busy || !replyBody.trim()"><AppIcon name="send" :size="16" />{{ $t('发送回复') }}</button></form><p v-else class="account-closed-note">{{ $t('这条工单已关闭。如需继续沟通，可重新打开。') }}</p></template>
      </section>
    </div>
    <AccountDialog v-if="creating" :title="$t('新建工单')" :busy="busy" @close="creating = false"><form class="account-dialog-body" @submit.prevent="submit"><label class="admin-field"><span>{{ $t('主题') }}</span><input v-model="subject" required minlength="2" maxlength="120" :disabled="busy"></label><label class="admin-field"><span>{{ $t('问题类型') }}</span><select v-model="category" :disabled="busy"><option v-for="(name,key) in categories" :key="key" :value="key">{{ $t(name) }}</option></select></label><label class="admin-field"><span>{{ $t('问题描述') }}</span><textarea v-model="body" rows="6" required minlength="2" maxlength="5000" :disabled="busy" /></label><p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p><button class="button primary" :disabled="busy"><AppIcon name="send" :size="16" />{{ $t('提交工单') }}</button></form></AccountDialog>
  </section>
</template>
