<script setup lang="ts">
import { type ModelGroup } from '~/types/model-groups'
import type { ModelAccount, Page } from '~/types/operations'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: ['admin', 'superadmin'] })
const { t } = useI18n()
useSeoMeta({ title: () => t('账号分组') })
const groups = ref<ModelGroup[]>([])
const accounts = ref<ModelAccount[]>([])
const busy = ref(false)
const error = ref('')
const editing = ref(false)
const selected = ref<ModelGroup | null>(null)
const deleting = ref<ModelGroup | null>(null)
const deleteBusy = ref(false)
const deleteError = ref('')
async function load() {
  busy.value = true; error.value = ''
  try {
    const [g, a] = await Promise.all([$fetch<Page<ModelGroup>>('/api/v1/admin/model-groups'), $fetch<Page<ModelAccount>>('/api/v1/admin/model-accounts')])
    groups.value = g.items; accounts.value = a.items
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
function accountName(id: string) { return accounts.value.find(a => a.id === id)?.name || t('账号不存在') }
function availableCount(group: ModelGroup) {
  return accounts.value.filter(a => group.account_ids.includes(a.id) && a.enabled && (!a.cooldown_until || Date.parse(a.cooldown_until) <= Date.now())).length
}
async function remove() {
  if (!deleting.value) return
  deleteBusy.value = true; deleteError.value = ''
  try {
    await $fetch(`/api/v1/admin/model-groups/${deleting.value.id}`, { method: 'DELETE', query: { revision: deleting.value.revision } })
    deleting.value = null; await load()
  } catch (cause) { deleteError.value = authError(cause) }
  finally { deleteBusy.value = false }
}
onMounted(load)
</script>

<template>
  <div>
    <div class="admin-page-heading"><h1>{{ $t('账号分组') }}</h1><button class="button primary" :disabled="busy || !!error" @click="selected = null; editing = true"><AppIcon name="plus" :size="17" />{{ $t('新增账号分组') }}</button></div>
    <p class="groups-intro">{{ $t('分组用于聚合账号，可混合添加不同能力的账号。工具调用时，由账号提供所需能力并自动切换。') }}</p>
    <div class="admin-toolbar"><NuxtLink class="button secondary" to="/admin/model-accounts">{{ $t('管理模型账号') }}</NuxtLink><NuxtLink class="button secondary" to="/admin/tools">{{ $t('为工具分配分组') }}</NuxtLink><button class="icon-button" :disabled="busy" :aria-label="$t('刷新')" :title="$t('刷新')" @click="load"><AppIcon name="refresh" :size="18" /></button></div>
    <AsyncState v-if="error" kind="error" :description="error" @retry="load" /><AsyncState v-else-if="busy" kind="loading" />
    <div v-else-if="!groups.length" class="groups-empty"><AppIcon name="layers" :size="32" /><h2>{{ $t('建立第一个账号分组') }}</h2><p>{{ $t('例如，将具备图片编辑能力的账号放在一起，供图片编辑工具调用。') }}</p><button class="button primary" @click="selected = null; editing = true">{{ $t('新增账号分组') }}</button></div>
    <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th>{{ $t('分组名称') }}</th><th>{{ $t('账号优先顺序') }}</th><th>{{ $t('已绑定工具') }}</th><th>{{ $t('状态') }}</th><th>{{ $t('操作') }}</th></tr></thead><tbody>
      <tr v-for="group in groups" :key="group.id"><td><strong>{{ group.name }}</strong><small class="group-description">{{ group.description }}</small></td><td><span v-if="!group.account_ids.length" class="muted">{{ $t('尚未添加账号') }}</span><ol v-else class="group-account-order"><li v-for="id in group.account_ids.slice(0, 3)" :key="id">{{ accountName(id) }}</li></ol><small>{{ $t('当前可调度 {count} 个账号', { count: availableCount(group) }) }}</small></td><td><span>{{ $t('{count} 个工具', { count: group.tool_slugs.length }) }}</span><small v-for="slug in group.tool_slugs" :key="slug">{{ slug }}</small></td><td><span class="status-tag" :class="group.enabled ? 'succeeded' : 'closed'">{{ group.enabled ? $t('已启用') : $t('已停用') }}</span></td><td><div class="admin-row-actions"><button class="icon-button" :aria-label="$t('编辑')" :title="$t('编辑')" @click="selected = group; editing = true"><AppIcon name="pen" :size="17" /></button><button class="icon-button" :disabled="!!group.tool_slugs.length" :aria-label="$t('删除分组')" :title="group.tool_slugs.length ? $t('请先解除工具绑定') : $t('删除分组')" @click="deleting = group; deleteError = ''"><AppIcon name="trash" :size="17" /></button></div></td></tr>
    </tbody></table></div>
    <ModelGroupEditor v-if="editing" :group="selected" :accounts="accounts" @close="editing = false" @saved="editing = false; load()" />
    <AdminDialog v-if="deleting" :title="$t('删除分组')" :busy="deleteBusy" @close="deleting = null"><div class="admin-editor"><p>{{ $t('确认删除分组「{name}」？组内模型账号会保留。', { name: deleting.name }) }}</p><p v-if="deleteError" class="form-error" role="alert">{{ deleteError }}</p><div class="admin-editor-actions"><button class="button secondary" :disabled="deleteBusy" @click="deleting = null">{{ $t('取消') }}</button><button class="button danger" :disabled="deleteBusy" @click="remove">{{ $t('删除分组') }}</button></div></div></AdminDialog>
  </div>
</template>

<style scoped>
.admin-table { min-width: 780px; }
.groups-intro { max-width: 70ch; color: var(--muted); line-height: 1.7; margin: -8px 0 22px; }
.groups-empty { padding: 64px 24px; text-align: center; border: 1px dashed var(--admin-line); border-radius: 12px; }
.groups-empty > svg { color: var(--admin-accent); margin-inline: auto; }
.groups-empty h2 { font-size: 20px; margin: 18px 0 8px; }
.groups-empty p { color: var(--muted); margin-bottom: 24px; line-height: 1.7; }
.group-tags { display: flex; flex-wrap: wrap; gap: 6px; max-width: 180px; }
.group-description { max-width: 240px; white-space: normal; }
.group-account-order { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.8; }
</style>
