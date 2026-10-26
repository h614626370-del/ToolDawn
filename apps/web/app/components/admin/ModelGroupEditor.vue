<script setup lang="ts">
import { capabilityLabels, type ModelGroup } from '~/types/model-groups'
import type { ModelAccount } from '~/types/operations'
import { authError } from '~/composables/useAuth'
const { t } = useI18n()
const props = defineProps<{ group: ModelGroup | null; accounts: ModelAccount[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const form = reactive({ name: props.group?.name || '', description: props.group?.description || '', enabled: props.group?.enabled ?? true, account_ids: [...(props.group?.account_ids || [])] })
function capabilityText(values: ModelAccount['capabilities']) { return values.map(c => t(capabilityLabels[c])).join(' / ') }
const busy = ref(false)
const error = ref('')
const search = ref('')
const selected = computed(() => form.account_ids.map(id => props.accounts.find(a => a.id === id)).filter((a): a is ModelAccount => !!a))
const available = computed(() => props.accounts.filter(a => !form.account_ids.includes(a.id) && `${a.name} ${a.model} ${Object.values(a.capability_models).join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
function move(index: number, direction: number) {
  const next = [...form.account_ids]
  const [id] = next.splice(index, 1)
  if (id) next.splice(index + direction, 0, id)
  form.account_ids = next
}
async function save() {
  busy.value = true; error.value = ''
  try {
    await $fetch(`/api/v1/admin/model-groups${props.group ? `/${props.group.id}` : ''}`, { method: props.group ? 'PUT' : 'POST', body: { ...form, revision: props.group?.revision || 0 } })
    emit('saved')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <AdminDialog :title="group ? $t('编辑账号分组') : $t('新增账号分组')" :busy="busy" @close="emit('close')">
    <form class="admin-editor" @submit.prevent="save">
      <fieldset class="admin-form-fields" :disabled="busy">
        <label class="admin-field"><span>{{ $t('分组名称') }}</span><input v-model="form.name" required maxlength="80" autofocus :placeholder="$t('例如：图片编辑账号组')"></label>
        <label class="admin-field"><span>{{ $t('分组说明') }}</span><textarea v-model="form.description" maxlength="500" rows="2" /></label>
        <section class="group-members" :aria-label="$t('账号优先顺序')">
          <h3>{{ $t('账号优先顺序') }} <span class="muted">{{ selected.length }}</span></h3>
          <p class="muted">{{ $t('从上到下优先调用，失败后自动切换；每次最多尝试 3 个账号。') }}</p>
          <p v-if="!selected.length" class="muted">{{ $t('从下方添加账号，可在多个分组中复用同一账号。') }}</p>
          <ol class="group-member-list"><li v-for="(account, index) in selected" :key="account.id">
            <span class="group-rank">{{ index + 1 }}</span><div class="group-member-name"><strong>{{ account.name }}</strong><small>{{ account.model }} · {{ capabilityText(account.capabilities) }}<template v-if="!account.enabled"> · {{ $t('已停用') }}</template></small></div>
            <div class="admin-row-actions"><button type="button" class="icon-button" :disabled="index === 0" :aria-label="$t('上移账号')" :title="$t('上移账号')" @click="move(index, -1)">↑</button><button type="button" class="icon-button" :disabled="index === selected.length - 1" :aria-label="$t('下移账号')" :title="$t('下移账号')" @click="move(index, 1)">↓</button><button type="button" class="icon-button" :aria-label="$t('移出分组')" :title="$t('移出分组')" @click="form.account_ids = form.account_ids.filter(id => id !== account.id)"><AppIcon name="close" :size="16" /></button></div>
          </li></ol>
          <label class="admin-field"><span>{{ $t('添加账号') }}</span><input v-model="search" type="search" :placeholder="$t('搜索账号名称或模型')"></label>
          <div class="group-account-picker"><button v-for="account in available" :key="account.id" type="button" @click="form.account_ids.push(account.id)"><span>{{ account.name }}<small>{{ account.model }} · {{ account.enabled ? $t('已启用') : $t('已停用') }}</small></span><AppIcon name="plus" :size="16" /></button><p v-if="!available.length" class="muted">{{ $t('没有更多账号，可先在模型账号中添加。') }}</p></div>
        </section>
        <label class="toggle-label"><input v-model="form.enabled" type="checkbox">{{ $t('启用分组') }}</label>
      </fieldset>
      <p v-if="error" role="alert" class="form-error">{{ error }}</p>
      <footer class="admin-editor-actions"><button type="button" class="button secondary" :disabled="busy" @click="emit('close')">{{ $t('取消') }}</button><button class="button primary" :disabled="busy"><AppIcon name="save" :size="17" />{{ $t('保存分组') }}</button></footer>
    </form>
  </AdminDialog>
</template>

<style scoped>
.group-members { border-top: 1px solid var(--admin-line); padding-top: 18px; }
.group-members h3 { margin: 0 0 8px; font-size: 15px; }
.group-members p { font-size: 13px; line-height: 1.6; }
.group-member-list { list-style: none; margin: 14px 0; padding: 0; }
.group-member-list li { display: flex; gap: 10px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--admin-line); }
.group-rank { width: 20px; color: var(--muted); font-variant-numeric: tabular-nums; }
.group-member-name { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.group-member-name small, .group-account-picker small { display: block; color: var(--muted); font-size: 12px; margin-top: 4px; }
.group-account-picker { max-height: 190px; overflow: auto; margin-top: 8px; }
.group-account-picker button { display: flex; justify-content: space-between; align-items: center; width: 100%; background: transparent; border: 0; border-bottom: 1px solid var(--admin-line); color: var(--ink); padding: 10px 4px; text-align: start; cursor: pointer; }
.group-account-picker button:hover { background: var(--admin-panel); }
</style>
