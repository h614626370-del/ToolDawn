<script setup lang="ts">
import { capabilityLabels, type ModelCapability } from '~/types/model-groups'
import type { ModelAccount } from '~/types/operations'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ account: ModelAccount | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const form = reactive({ capabilities: [...(props.account?.capabilities || ['text'])] as ModelCapability[], name: props.account?.name || '', base_url: props.account?.base_url || '', model: props.account?.model || '', api_key: '', enabled: props.account?.enabled ?? true })
const modelOverrides = reactive<Partial<Record<ModelCapability, string>>>({ ...props.account?.capability_models })
const busy = ref(false)
const discovering = ref(false)
const error = ref('')
const modelsError = ref('')
const models = ref<string[]>([])
const modelsLoaded = ref(false)
const locked = computed(() => busy.value || discovering.value)
watch(() => [form.base_url, form.api_key], () => { models.value = []; modelsLoaded.value = false; modelsError.value = '' })
async function discover() {
  discovering.value = true; modelsError.value = ''; modelsLoaded.value = false
  try {
    const result = await $fetch<{ items: string[] }>('/api/v1/admin/model-accounts/models', {
      method: 'POST', body: { base_url: form.base_url, api_key: form.api_key || null, account_id: props.account?.id || null, revision: props.account?.revision || 0 },
    })
    models.value = result.items; modelsLoaded.value = true
  } catch (cause) { modelsError.value = authError(cause) }
  finally { discovering.value = false }
}
async function save() {
  busy.value = true; error.value = ''
  try {
    const capability_models = Object.fromEntries(form.capabilities.filter(c => modelOverrides[c]?.trim()).map(c => [c, modelOverrides[c]!.trim()]))
    await $fetch(`/api/v1/admin/model-accounts${props.account ? `/${props.account.id}` : ''}`, {
      method: props.account ? 'PUT' : 'POST',
      body: { ...form, capability_models, api_key: form.api_key || null, revision: props.account?.revision || 0 },
    })
    form.api_key = ''
    emit('saved')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <AdminDialog :title="account ? $t('编辑模型账号') : $t('新增模型账号')" :busy="locked" @close="emit('close')">
    <form class="admin-editor" @submit.prevent="save">
      <fieldset class="admin-form-fields" :disabled="locked">
        <p class="account-connection-note">{{ $t('API Key 接入 · OpenAI 兼容接口') }}</p>
        <label class="admin-field"><span>{{ $t('账号名称') }}</span><input v-model="form.name" required maxlength="80" autofocus></label>
        <label class="admin-field"><span>{{ $t('服务地址') }} · Base URL</span><input v-model="form.base_url" type="url" required maxlength="500" placeholder="https://api.example.com/v1"><small>{{ $t('填写 API 基础地址，包含 /v1 等路径，不填写具体接口。') }}</small></label>
        <label class="admin-field"><span>API Key <small v-if="account?.key_set">{{ $t('已配置，留空保留') }}</small></span><input v-model="form.api_key" type="password" :required="!account" maxlength="1000" autocomplete="off"></label>
        <div class="account-model-discovery"><button type="button" class="button secondary" :disabled="!form.base_url || (!form.api_key && !account?.key_set)" @click="discover"><AppIcon :name="discovering ? 'loader' : 'refresh'" :size="16" :class="{ spin: discovering }" />{{ discovering ? $t('正在获取模型') : $t('获取模型列表') }}</button><span v-if="modelsLoaded" role="status">{{ models.length ? $t('已获取 {count} 个模型', { count: models.length }) : $t('未返回模型，可手动填写。') }}</span></div>
        <p v-if="modelsError" class="form-error" role="alert">{{ modelsError }}</p>
        <datalist id="account-model-options"><option v-for="model in models" :key="model" :value="model" /></datalist>
        <label class="admin-field"><span>{{ $t('默认模型') }}</span><input v-model="form.model" list="account-model-options" required maxlength="120" :placeholder="$t('选择或填写模型名称')"></label>
        <fieldset class="account-capabilities"><legend>{{ $t('账号提供的能力') }}</legend><div class="admin-checks"><label v-for="(label, value) in capabilityLabels" :key="value"><input v-model="form.capabilities" type="checkbox" :value="value">{{ $t(label) }}</label></div><p class="muted">{{ $t('根据账号实际能力选择。获取模型列表不会验证生成或编辑能力。') }}</p></fieldset>
        <details class="account-model-overrides" :open="Object.keys(account?.capability_models || {}).length > 0"><summary>{{ $t('按能力指定模型（可选）') }}</summary><p class="muted">{{ $t('同一个 Key 可使用不同模型；留空使用默认模型。') }}</p><div class="admin-form-grid"><label v-for="capability in form.capabilities" :key="capability" class="admin-field"><span>{{ $t(capabilityLabels[capability]) }}</span><input v-model="modelOverrides[capability]" list="account-model-options" maxlength="120" :placeholder="form.model || $t('使用默认模型')"></label></div></details>
        <label class="toggle-label"><input v-model="form.enabled" type="checkbox">{{ $t('启用账号') }}</label>
      </fieldset>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="admin-editor-actions"><button type="button" class="button secondary" :disabled="locked" @click="emit('close')">{{ $t('取消') }}</button><button class="button primary" :disabled="locked || !form.capabilities.length"><AppIcon name="save" :size="17" />{{ $t('保存账号') }}</button></div>
    </form>
  </AdminDialog>
</template>

<style scoped>
.account-connection-note { margin: 0; color: var(--muted); font-size: 13px; }
.account-model-discovery { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.account-model-discovery span { font-size: 13px; color: var(--muted); }
.account-capabilities { border: 0; padding: 0; margin: 0; }
.account-capabilities legend { font-weight: 600; margin-bottom: 10px; }
.account-capabilities p, .account-model-overrides p, .admin-field small { font-size: 13px; line-height: 1.6; color: var(--muted); }
.account-model-overrides { border-block: 1px solid var(--admin-line); padding: 14px 0; }
.account-model-overrides summary { font-weight: 600; cursor: pointer; }
</style>
