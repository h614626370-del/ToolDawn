<script setup lang="ts">
import type { PaymentProvider, ProviderType, ProviderKind } from '~/types/payment-provider'
import { authError } from '~/composables/useAuth'
const { t } = useI18n()
const providers = ref<PaymentProvider[]>([])
const types = ref<ProviderType[]>([])
const pending = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const actionError = ref('')
const editing = ref(false)
const selected = ref<PaymentProvider | null>(null)
const deleting = ref<PaymentProvider | null>(null)
const values = reactive<Record<string, string>>({})
const clear = reactive<Record<string, boolean>>({})
const draft = reactive({ name: '', kind: 'easypay' as ProviderKind, enabled: false, sort_order: 0, methods: [] as string[] })
const spec = computed(() => types.value.find(item => item.kind === draft.kind))
const methodName = (value: string) => t(({ alipay: '支付宝', wxpay: '微信支付', card: '银行卡', airwallex: 'Airwallex' } as Record<string, string>)[value] || value)
async function load() {
  pending.value = true; error.value = ''
  try {
    const [list, catalog] = await Promise.all([$fetch<{ items: PaymentProvider[] }>('/api/v1/admin/billing/providers'), $fetch<ProviderType[]>('/api/v1/admin/billing/provider-types')])
    providers.value = list.items; types.value = catalog
  } catch (cause) { error.value = authError(cause) }
  finally { pending.value = false }
}
function edit(kind: ProviderKind, row: PaymentProvider | null = null) {
  selected.value = row; actionError.value = ''; notice.value = ''
  Object.keys(values).forEach(key => delete values[key]); Object.keys(clear).forEach(key => delete clear[key])
  const definition = types.value.find(item => item.kind === kind)!
  Object.assign(draft, { kind, name: row?.name || definition.name, enabled: row?.enabled || false, sort_order: row?.sort_order || 0, methods: [...(row?.methods || definition.methods)] })
  for (const field of definition.fields) values[field.key] = row?.config[field.key] ?? field.default
  editing.value = true
}
function body(row: PaymentProvider) { return { kind: row.kind, name: row.name, enabled: row.enabled, sort_order: row.sort_order, methods: row.methods, config: {}, revision: row.revision } }
async function save() {
  if (!spec.value) return
  busy.value = true; actionError.value = ''
  try {
    const config = selected.value?.config_locked ? {} : Object.fromEntries(spec.value.fields.map(field => [field.key, field.secret ? (clear[field.key] ? '' : values[field.key] || null) : values[field.key]]))
    await $fetch(selected.value ? `/api/v1/admin/billing/providers/${selected.value.id}` : '/api/v1/admin/billing/providers', { method: selected.value ? 'PUT' : 'POST', body: { ...draft, config, revision: selected.value?.revision || 0 } })
    editing.value = false; notice.value = t('支付供应商已保存。'); await load()
  } catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = false }
}
async function toggle(row: PaymentProvider) {
  busy.value = true; error.value = ''; notice.value = ''
  try { await $fetch(`/api/v1/admin/billing/providers/${row.id}`, { method: 'PUT', body: { ...body(row), enabled: !row.enabled } }); await load() }
  catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
async function remove() {
  if (!deleting.value) return
  busy.value = true; actionError.value = ''
  try { await $fetch(`/api/v1/admin/billing/providers/${deleting.value.id}`, { method: 'DELETE', query: { revision: deleting.value.revision } }); deleting.value = null; await load() }
  catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <section class="settings-section provider-manager">
    <div class="section-heading"><div><h2>{{ $t('支付供应商') }}</h2><p class="muted">{{ $t('添加商户实例，配置支付方式和回调。') }}</p></div><button class="icon-button" :disabled="pending || busy" :aria-label="$t('刷新')" @click="load"><AppIcon name="refresh" :size="18" /></button></div>
    <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
    <AsyncState v-if="error" kind="error" :title="$t('支付数据加载失败')" :description="error" @retry="load" />
    <AsyncState v-else-if="pending" kind="loading" :title="$t('正在加载数据')" />
    <template v-else>
      <div class="provider-add-options" :aria-label="$t('添加支付供应商')"><button v-for="item in types" :key="item.kind" class="button secondary" :disabled="busy || providers.length >= 50" @click="edit(item.kind)"><AppIcon name="plus" :size="15" />{{ $t(item.name) }}</button></div>
      <p v-if="!providers.length" class="billing-empty">{{ $t('还没有支付供应商，选择上方类型开始配置。') }}</p>
      <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th>{{ $t('供应商名称') }}</th><th>{{ $t('支付方式') }}</th><th>{{ $t('状态') }}</th><th>{{ $t('排序') }}</th><th>{{ $t('操作') }}</th></tr></thead><tbody><tr v-for="row in providers" :key="row.id"><td><strong>{{ row.name }}</strong><small class="provider-kind">{{ $t(types.find(item => item.kind === row.kind)?.name || row.kind) }}</small></td><td>{{ row.methods.map(methodName).join(' / ') }}</td><td><span class="admin-state" :class="{ enabled: row.enabled }">{{ row.enabled ? $t('已启用') : $t('已停用') }}</span></td><td>{{ row.sort_order }}</td><td><div class="admin-row-actions"><button class="text-button" :disabled="busy" @click="edit(row.kind, row)">{{ $t('配置') }}</button><button class="text-button" :disabled="busy" @click="toggle(row)">{{ row.enabled ? $t('停用') : $t('启用') }}</button><button v-if="!row.config_locked" class="icon-button" :disabled="busy" :aria-label="$t('删除供应商')" @click="deleting = row; actionError = ''"><AppIcon name="trash" :size="16" /></button></div></td></tr></tbody></table></div>
      <p class="payment-help provider-footnote">{{ $t('支付宝、微信和易支付使用 CNY 套餐；Stripe 与 Airwallex 支持 CNY、USD、EUR。已停用的实例不接受新订单，历史回调继续处理。') }}</p>
    </template>
    <AdminDialog v-if="editing && spec" :title="`${selected ? $t('编辑供应商') : $t('添加支付供应商')} · ${$t(spec.name)}`" :busy="busy" @close="editing = false">
      <form class="admin-editor" @submit.prevent="save"><fieldset class="admin-form-fields" :disabled="busy">
        <div class="admin-form-grid"><label class="admin-field"><span>{{ $t('供应商名称') }}</span><input v-model="draft.name" required maxlength="80"></label><label class="admin-field"><span>{{ $t('排序') }}</span><input v-model.number="draft.sort_order" type="number" min="0" max="10000" required></label></div>
        <div class="admin-checks"><label><input v-model="draft.enabled" type="checkbox">{{ $t('启用在线支付') }}</label><label v-for="method in spec.methods" :key="method"><input v-model="draft.methods" type="checkbox" :value="method">{{ methodName(method) }}</label></div>
        <p v-if="selected?.config_locked" class="payment-help">{{ $t('已有订单的商户配置已锁定。更换商户或密钥请新建实例，历史回调仍由原实例处理。') }}</p>
        <div class="provider-fields admin-form-grid">
          <label v-for="field in spec.fields" :key="field.key" class="admin-field" :class="{ 'provider-wide': field.multiline || field.key === 'public_origin' }">
            <span>{{ $t(field.label) }} <small v-if="field.secret">{{ selected?.secrets_set[field.key] ? $t('已配置，留空保留') : $t('尚未配置') }}</small></span>
            <select v-if="field.options" v-model="values[field.key]" :disabled="selected?.config_locked"><option v-for="option in field.options" :key="option" :value="option">{{ option === 'live' ? $t('正式环境') : $t('沙箱环境') }}</option></select>
            <textarea v-else-if="field.multiline" v-model="values[field.key]" rows="4" maxlength="10000" autocomplete="off" spellcheck="false" :disabled="selected?.config_locked || clear[field.key]" />
            <input v-else v-model="values[field.key]" :type="field.secret ? 'password' : 'text'" maxlength="10000" autocomplete="off" :placeholder="field.key === 'public_origin' ? 'https://your-site.example' : ''" :disabled="selected?.config_locked || clear[field.key]">
            <span v-if="field.secret && selected && !selected.config_locked" class="toggle-label"><input v-model="clear[field.key]" type="checkbox">{{ $t('清除保存的密钥') }}</span>
          </label>
        </div>
        <p class="payment-help">{{ $t('回调域名需能从公网通过 HTTPS 访问。未完成配置可保持停用并保存草稿。') }}</p>
        <div v-if="selected" class="provider-webhook"><strong>{{ $t('回调地址') }}</strong><code>{{ selected.webhook_url }}</code><p v-if="spec.events.length">{{ $t('订阅事件') }}: {{ spec.events.join(', ') }}</p></div>
        <p v-else class="payment-help">{{ $t('保存后显示该实例专属的回调地址。') }}</p>
      </fieldset><p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p><div class="admin-editor-actions"><button type="button" class="button secondary" :disabled="busy" @click="editing = false">{{ $t('取消') }}</button><button class="button primary" :disabled="busy || !draft.methods.length"><AppIcon :name="busy ? 'loader' : 'save'" :size="17" :class="{ spin: busy }" />{{ $t('保存供应商') }}</button></div></form>
    </AdminDialog>
    <AdminDialog v-if="deleting" :title="$t('删除供应商')" :busy="busy" @close="deleting = null"><div class="admin-editor"><p>{{ deleting.name }}</p><p class="payment-help">{{ $t('仅无订单记录的实例可以删除。删除后需要重新填写商户配置。') }}</p><p v-if="actionError" role="alert" class="form-error">{{ actionError }}</p><div class="admin-editor-actions"><button class="button secondary" :disabled="busy" @click="deleting = null">{{ $t('取消') }}</button><button class="button danger" :disabled="busy" @click="remove">{{ $t('确认删除') }}</button></div></div></AdminDialog>
  </section>
</template>
