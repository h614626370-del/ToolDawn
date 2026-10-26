<script setup lang="ts">
import { authError } from '~/composables/useAuth'
import type { Usage } from '~/types/operations'
import { accountToolNames as names, accountRunStates as states } from '~/utils/accountTools'
const { t, locale } = useI18n()
const status = ref(''), tool = ref(''), start = ref(''), end = ref(''), offset = ref(0)
function dateBound(value: string, next = false) { if (!value) return; const date = new Date(`${value}T00:00:00`); if (next) date.setDate(date.getDate() + 1); return date.toISOString() }
const query = computed(() => ({ offset:offset.value, limit:12, status:status.value || undefined, tool:tool.value || undefined, start:dateBound(start.value), end:dateBound(end.value,true) }))
watch([status,tool,start,end], () => { offset.value = 0 })
const { result, pending, error, refresh } = useApiList<Usage>('/api/v1/me/usage', query)
const selected = ref<Usage | null>(null)
const output = ref(''), outputError = ref(''), notice = ref('')
const loading = ref(false), deleting = ref(false), confirmDelete = ref(false)
let sequence = 0
async function inspect(row: Usage) {
  const current = ++sequence
  selected.value = row; output.value = ''; outputError.value = ''; notice.value = ''; loading.value = true; confirmDelete.value = false
  try { const data = await $fetch<{output:string | null}>(`/api/v1/me/usage/${row.id}`); if (current === sequence) output.value = data.output || '' }
  catch (cause) { if (current === sequence) outputError.value = authError(cause) }
  finally { if (current === sequence) loading.value = false }
}
function close() { sequence++; selected.value = null }
async function clear() {
  if (!selected.value) return
  deleting.value = true
  try { await $fetch(`/api/v1/ai-tools/runs/${selected.value.id}/output`,{method:'DELETE'}); output.value = ''; confirmDelete.value = false; await refresh() }
  catch (cause) { outputError.value = authError(cause) }
  finally { deleting.value = false }
}
async function copy() {
  try { await navigator.clipboard.writeText(output.value); notice.value = t('已复制。') }
  catch { outputError.value = t('复制失败，请手动选择文本复制。') }
}
onBeforeUnmount(() => { sequence++ })
</script>
<template>
  <section>
    <form class="account-filters" @submit.prevent="refresh"><label><span>{{ $t('工具') }}</span><select v-model="tool"><option value="">{{ $t('全部工具') }}</option><option v-for="(name,slug) in names" :key="slug" :value="slug">{{ $t(name) }}</option></select></label><label><span>{{ $t('执行状态') }}</span><select v-model="status"><option value="">{{ $t('全部状态') }}</option><option v-for="(label,key) in states" :key="key" :value="key">{{ $t(label) }}</option></select></label><label><span>{{ $t('开始日期') }}</span><input v-model="start" type="date" :max="end || undefined"></label><label><span>{{ $t('结束日期') }}</span><input v-model="end" type="date" :min="start || undefined"></label><button class="button secondary" :disabled="pending"><AppIcon name="refresh" :size="16" />{{ $t('刷新') }}</button></form>
    <AsyncState v-if="error" kind="error" :title="$t('暂时无法加载')" :description="error" @retry="refresh" /><AsyncState v-else-if="pending" kind="loading" :title="$t('正在加载')" /><div v-else-if="!result.items.length" class="account-empty"><AppIcon name="history" :size="32" /><h2>{{ $t('暂无使用记录') }}</h2><p>{{ $t('换个筛选条件，或去工具目录开始创作。') }}</p><NuxtLink to="/tools" class="button primary">{{ $t('浏览工具') }}</NuxtLink></div>
    <div v-else class="account-usage-list"><article v-for="row in result.items" :key="row.id" class="account-usage-row"><button class="account-result-preview" :aria-label="$t('查看结果')" @click="inspect(row)"><img v-if="row.image_url" :src="row.image_url" :alt="$t('AI 生成的图片')" loading="lazy"><AppIcon v-else :name="row.tool_slug === 'image-generate' ? 'image' : 'pen'" :size="26" /></button><div class="account-usage-main"><div class="account-row-title"><NuxtLink :to="`/tools/${row.tool_slug}`">{{ $t(names[row.tool_slug] || row.tool_slug) }}</NuxtLink><span class="account-status" :data-status="row.status">{{ $t(states[row.status] || row.status) }}</span></div><p class="account-result-excerpt">{{ row.result_preview || $t(row.image_url ? '图片已生成，可查看、下载或继续创作。' : row.status === 'running' ? '任务正在处理中，可稍后刷新查看。' : row.status === 'failed' ? '本次未完成，积分已退回。' : '暂无保存的结果。') }}</p><div class="account-row-meta"><time>{{ new Date(row.created_at).toLocaleString(locale) }}</time><span>{{ $t('消耗 {count} 积分', {count:row.charged}) }}</span></div></div><button class="button secondary" @click="inspect(row)">{{ $t('查看结果') }}<AppIcon name="arrow" :size="16" /></button></article></div>
    <AdminPagination :total="result.total" :offset="offset" :limit="12" :busy="pending" @change="offset = $event" />
    <AccountDialog v-if="selected" :title="$t(names[selected.tool_slug] || selected.tool_slug)" :busy="deleting" @close="close"><div class="account-dialog-body"><AsyncState v-if="loading" kind="loading" :title="$t('正在加载')" /><p v-else-if="outputError" role="alert" class="form-error">{{ outputError }}</p><template v-else><img v-if="output && selected.tool_slug === 'image-generate'" :src="output" :alt="$t('AI 生成的图片')" class="account-result-image"><pre v-else-if="output" class="account-text-output">{{ output }}</pre><p v-else class="muted">{{ $t('暂无保存的结果。') }}</p><dl class="account-result-meta"><div><dt>{{ $t('模型') }}</dt><dd>{{ selected.model || '—' }}</dd></div><div><dt>{{ $t('耗时') }}</dt><dd>{{ selected.duration_ms === null ? '—' : `${(selected.duration_ms / 1000).toFixed(1)}s` }}</dd></div></dl><p v-if="notice" role="status" class="account-notice">{{ notice }}</p><div class="account-inline-actions"><NuxtLink :to="`/tools/${selected.tool_slug}`" class="button primary">{{ $t('打开工具') }}</NuxtLink><a v-if="output && selected.tool_slug === 'image-generate'" :href="`${output}?download=true`" class="button secondary">{{ $t('下载') }}</a><button v-else-if="output" class="button secondary" @click="copy">{{ $t('复制结果') }}</button><button v-if="output" class="text-button" @click="confirmDelete = true">{{ $t('删除结果') }}</button></div><div v-if="confirmDelete" class="account-delete-confirm"><p>{{ $t('删除后无法恢复，使用记录仍会保留。') }}</p><button class="button secondary" :disabled="deleting" @click="confirmDelete = false">{{ $t('取消') }}</button><button class="button danger" :disabled="deleting" @click="clear">{{ $t('确认删除') }}</button></div></template></div></AccountDialog>
  </section>
</template>
