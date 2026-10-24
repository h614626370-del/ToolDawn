<script setup lang="ts">
import type { ModelAccount } from '~/types/operations'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ account: ModelAccount | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const form = reactive({ name: props.account?.name || '', base_url: props.account?.base_url || '', model: props.account?.model || '', api_key: '', enabled: props.account?.enabled ?? true })
const busy = ref(false)
const error = ref('')
async function save() {
  busy.value = true; error.value = ''
  try {
    await $fetch(`/api/v1/admin/model-accounts${props.account ? `/${props.account.id}` : ''}`, {
      method: props.account ? 'PUT' : 'POST',
      body: { ...form, api_key: form.api_key || null, revision: props.account?.revision || 0 },
    })
    form.api_key = ''
    emit('saved')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>
<template>
  <AdminDialog :title="account ? $t('编辑模型账号') : $t('新增模型账号')" :busy="busy" @close="emit('close')"><form class="admin-editor" @submit.prevent="save"><fieldset class="admin-form-fields" :disabled="busy">
    <label class="admin-field"><span>{{ $t('账号名称') }}</span><input v-model="form.name" required maxlength="80"></label>
    <label class="admin-field"><span>Base URL</span><input v-model="form.base_url" type="url" required maxlength="500" placeholder="https://api.example.com/v1"></label>
    <label class="admin-field"><span>API Key <small v-if="account?.key_set">{{ $t('已配置，留空保留') }}</small></span><input v-model="form.api_key" type="password" :required="!account" maxlength="1000" autocomplete="off"></label>
    <label class="admin-field"><span>{{ $t('模型名称') }}</span><input v-model="form.model" required maxlength="120"></label>
    <label class="toggle-label"><input v-model="form.enabled" type="checkbox">{{ $t('启用账号') }}</label>
  </fieldset><p v-if="error" class="form-error" role="alert">{{ error }}</p><div class="admin-editor-actions"><button type="button" class="button secondary" :disabled="busy" @click="emit('close')">{{ $t('取消') }}</button><button class="button primary" :disabled="busy"><AppIcon name="save" :size="17" />{{ $t('保存账号') }}</button></div></form></AdminDialog>
</template>
