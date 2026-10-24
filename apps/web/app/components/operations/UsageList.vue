<script setup lang="ts">
import type { Usage } from '~/types/operations'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ admin?: boolean }>()
const { t, locale } = useI18n()
const offset = ref(0)
const status = ref('')
const tool = ref('')
const email = ref('')
const start = ref('')
const end = ref('')
const tools = ['text-polish', 'copy-rewrite', 'text-summary', 'email-writer', 'text-translate', 'birthday-message']
const names: Record<string, string> = { 'text-polish': '文字润色', 'copy-rewrite': '文案改写', 'text-summary': '长文摘要', 'email-writer': '邮件助手', 'text-translate': '自然翻译', 'birthday-message': '生日祝福' }
const states: Record<string, string> = { running: '生成中', succeeded: '已完成', failed: '失败已退分' }
const query = computed(() => ({
  offset: offset.value, limit: 20, q: props.admin ? email.value : undefined,
  status: status.value || undefined, tool: tool.value || undefined,
  start: start.value ? new Date(`${start.value}T00:00:00`).toISOString() : undefined,
  end: end.value ? new Date(`${end.value}T23:59:59.999`).toISOString() : undefined,
}))
watch([status, tool, email, start, end], () => { offset.value = 0 })
const { result, pending, error, refresh } = useApiList<Usage>(props.admin ? '/api/v1/admin/usage' : '/api/v1/me/usage', query)
const selected = ref<Usage | null>(null)
const output = ref('')
const outputError = ref('')
const loading = ref(false)
async function inspect(row: Usage) {
  selected.value = row; output.value = ''; outputError.value = ''; loading.value = true
  try {
    const data = await $fetch<{ output: string | null }>(`/api/v1/me/usage/${row.id}`)
    output.value = data.output || ''
  } catch (cause) { outputError.value = authError(cause) }
  finally { loading.value = false }
}
async function clear() {
  if (!selected.value) return
  loading.value = true
  try {
    await $fetch(`/api/v1/ai-tools/runs/${selected.value.id}/output`, { method: 'DELETE' })
    output.value = ''
  } catch (cause) { outputError.value = authError(cause) }
  finally { loading.value = false }
}
</script>

<template>
  <section>
    <form class="admin-toolbar" @submit.prevent="refresh">
      <input v-if="admin" v-model.lazy="email" class="filter-input" :placeholder="$t('搜索用户邮箱')" :aria-label="$t('搜索用户邮箱')" maxlength="100">
      <select v-model="status" :aria-label="$t('执行状态')"><option value="">{{ $t('全部状态') }}</option><option v-for="(name, key) in states" :key="key" :value="key">{{ $t(name) }}</option></select>
      <select v-model="tool" :aria-label="$t('工具')"><option value="">{{ $t('全部工具') }}</option><option v-for="slug in tools" :key="slug" :value="slug">{{ $t(names[slug] || slug) }}</option></select>
      <label class="date-filter">{{ $t('开始日期') }}<input v-model="start" type="date" :max="end || undefined"></label>
      <label class="date-filter">{{ $t('结束日期') }}<input v-model="end" type="date" :min="start || undefined"></label>
      <button class="icon-button" :disabled="pending" :title="$t('刷新')" :aria-label="$t('刷新')"><AppIcon name="refresh" :size="18" /></button>
    </form>
    <AsyncState v-if="error" kind="error" :description="error" @retry="refresh" />
    <AsyncState v-else-if="pending" kind="loading" />
    <AsyncState v-else-if="!result.items.length" kind="empty" :title="$t('暂无使用记录')" />
    <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th>{{ $t('工具') }}</th><th v-if="admin">{{ $t('用户') }}</th><th>{{ $t('状态') }}</th><th>{{ $t('模型') }}</th><th>{{ $t('扣除积分') }}</th><th>{{ $t('耗时') }}</th><th>{{ $t('时间') }}</th><th v-if="!admin">{{ $t('操作') }}</th></tr></thead><tbody><tr v-for="row in result.items" :key="row.id"><td><NuxtLink :to="`/tools/${row.tool_slug}`">{{ $t(names[row.tool_slug] || row.tool_slug) }}</NuxtLink></td><td v-if="admin">{{ row.email }}<small>{{ row.account_name || $t('默认账号') }}</small></td><td><span class="status-tag" :class="row.status">{{ $t(states[row.status] || row.status) }}</span></td><td>{{ row.model || '—' }}</td><td>{{ row.charged }}</td><td>{{ row.duration_ms === null ? '—' : `${(row.duration_ms / 1000).toFixed(1)}s` }}</td><td>{{ new Date(row.created_at).toLocaleString(locale) }}</td><td v-if="!admin"><button class="icon-button" :title="$t('查看结果')" :aria-label="$t('查看结果')" @click="inspect(row)"><AppIcon name="eye" :size="17" /></button></td></tr></tbody></table></div>
    <AdminPagination :total="result.total" :offset="offset" :limit="20" :busy="pending" @change="offset = $event" />
    <AdminDialog v-if="selected" :title="$t('生成结果')" :busy="loading" @close="selected = null"><div class="admin-editor"><AsyncState v-if="loading" kind="loading" /><p v-else-if="outputError" class="form-error" role="alert">{{ outputError }}</p><template v-else><pre v-if="output" class="generated-output">{{ output }}</pre><p v-else class="muted">{{ $t('暂无保存的结果。') }}</p><div v-if="output" class="admin-editor-actions"><button class="button danger" @click="clear"><AppIcon name="trash" :size="16" />{{ $t('清除结果') }}</button></div></template></div></AdminDialog>
  </section>
</template>
