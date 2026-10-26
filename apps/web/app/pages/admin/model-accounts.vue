<script setup lang="ts">
import { capabilityLabels } from '~/types/model-groups'
import type { ModelAccount, Page } from '~/types/operations'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: ['admin', 'superadmin'] })
const { t, locale } = useI18n()
const accounts = ref<ModelAccount[]>([])
function accountModels(account: ModelAccount) { return account.capabilities.map(c => `${t(capabilityLabels[c])}: ${account.capability_models[c] || account.model}`) }
const busy = ref(false)
const testing = ref('')
const error = ref('')
const notice = ref('')
const editing = ref(false)
const selected = ref<ModelAccount | null>(null)
useSeoMeta({ title: () => t('模型账号') })
async function load() {
  busy.value = true; error.value = ''
  try { accounts.value = (await $fetch<Page<ModelAccount>>('/api/v1/admin/model-accounts')).items }
  catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
async function test(account: ModelAccount) {
  testing.value = account.id; notice.value = ''; error.value = ''
  try {
    const result = await $fetch<{ ok: boolean; message: string }>('/api/v1/admin/model-accounts/' + account.id + '/test', { method: 'POST' })
    notice.value = t(result.message)
    await load()
  } catch (cause) { error.value = authError(cause) }
  finally { testing.value = '' }
}
async function resetHealth(account: ModelAccount) {
  testing.value = account.id; error.value = ''
  try { await $fetch(`/api/v1/admin/model-accounts/${account.id}/reset-health`, { method: 'POST' }); await load() }
  catch (cause) { error.value = authError(cause) }
  finally { testing.value = '' }
}
onMounted(load)
</script>
<template><div><div class="admin-page-heading"><h1>{{ $t('模型账号') }}</h1><button class="button primary" @click="selected = null; editing = true"><AppIcon name="plus" :size="17" />{{ $t('新增模型账号') }}</button></div>
  <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p><AsyncState v-if="error" kind="error" :description="error" @retry="load" /><AsyncState v-else-if="busy" kind="loading" /><AsyncState v-else-if="!accounts.length" kind="empty" :title="$t('暂无模型账号')" />
  <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th>{{ $t('账号名称') }}</th><th>Base URL</th><th>{{ $t('模型') }}</th><th>{{ $t('状态') }}</th><th>{{ $t('连通检查') }}</th><th>{{ $t('操作') }}</th></tr></thead><tbody><tr v-for="account in accounts" :key="account.id"><td>{{ account.name }}<small>{{ account.key_set ? $t('密钥已保存') : $t('未配置密钥') }}</small></td><td class="url-cell">{{ account.base_url }}</td><td><span>{{ account.model }}</span><small v-for="line in accountModels(account)" :key="line">{{ line }}</small></td><td><span class="status-tag" :class="account.enabled ? 'succeeded' : 'closed'">{{ account.enabled ? $t('已启用') : $t('已停用') }}</span><small v-if="account.cooldown_until && Date.parse(account.cooldown_until) > Date.now()">{{ $t('冷却至') }} {{ new Date(account.cooldown_until).toLocaleTimeString(locale) }}</small><button v-if="account.last_failure_code" class="button secondary" :disabled="!!testing" @click="resetHealth(account)">{{ $t('重置冷却') }}</button></td><td>{{ account.last_test_ok === null ? $t('未检查') : account.last_test_ok ? $t('通过') : $t('失败') }}<small v-if="account.last_test_at">{{ account.last_test_ms }} ms · {{ new Date(account.last_test_at).toLocaleString(locale) }}</small></td><td><div class="admin-row-actions"><button class="icon-button" :disabled="!!testing" :title="$t('检查模型列表')" :aria-label="$t('检查模型列表')" @click="test(account)"><AppIcon :name="testing === account.id ? 'loader' : 'activity'" :size="18" :class="{ spin: testing === account.id }" /></button><button class="icon-button" :title="$t('编辑')" :aria-label="$t('编辑')" @click="selected = account; editing = true"><AppIcon name="pen" :size="18" /></button></div></td></tr></tbody></table></div>
  <ModelAccountEditor v-if="editing" :account="selected" @close="editing = false" @saved="editing = false; load()" />
</div></template>
