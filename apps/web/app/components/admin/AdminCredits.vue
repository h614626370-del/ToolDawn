<script setup lang="ts">
const { t } = useI18n()
import type { AdminUser } from '~/types/admin'
import type { BillingPage, CreditEntry } from '~/types/billing'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ user: AdminUser }>()
const emit = defineEmits<{ close: [] }>()
const balance = ref(0)
const entries = shallowRef<BillingPage<CreditEntry>>({ items: [], total: 0 })
const pending = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const amount = ref<number | ''>('')
const reason = ref('')
const offset = ref(0)
let requestKey = crypto.randomUUID()
async function load() {
  pending.value = true
  error.value = ''
  try {
    const [wallet, history] = await Promise.all([
      $fetch<{ balance: number }>(`/api/v1/admin/users/${props.user.id}/wallet`),
      $fetch<BillingPage<CreditEntry>>(`/api/v1/admin/users/${props.user.id}/credits`, { query: { offset: offset.value, limit: 10 } }),
    ])
    balance.value = wallet.balance
    entries.value = history
  } catch (cause) { error.value = authError(cause) }
  finally { pending.value = false }
}
async function adjust() {
  busy.value = true
  notice.value = ''
  error.value = ''
  try {
    await $fetch(`/api/v1/admin/users/${props.user.id}/credits`, {
      method: 'POST', body: { amount: amount.value, reason: reason.value.trim(), request_key: requestKey },
    })
    requestKey = crypto.randomUUID()
    amount.value = ''
    reason.value = ''
    notice.value = t('积分已调整。')
    offset.value = 0
    await load()
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
watch([amount, reason], () => { if (!busy.value) requestKey = crypto.randomUUID() })
watch(offset, load)
onMounted(load)
</script>

<template>
  <AdminDialog :title="$t('用户积分')" :busy="busy" @close="emit('close')"><div class="admin-editor">
    <p class="admin-confirm-email">{{ user.email }}</p>
    <p v-if="!pending" class="credit-balance-label">{{ $t('可用积分') }} <strong>{{ balance.toLocaleString() }}</strong></p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p><p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
    <form class="credit-adjustment" @submit.prevent="adjust">
      <fieldset class="admin-form-fields" :disabled="busy || pending">
        <label class="admin-field"><span>{{ $t('调整积分（正数增加，负数扣减）') }}</span><input v-model.number="amount" type="number" min="-100000000" max="100000000" step="1" required></label>
        <label class="admin-field"><span>{{ $t('调整原因') }}</span><input v-model="reason" minlength="3" maxlength="300" required></label>
        <button class="button primary" :disabled="!amount || reason.trim().length < 3"><AppIcon :name="busy ? 'loader' : 'save'" :size="17" :class="{ spin: busy }" />{{ $t('确认调整') }}</button>
      </fieldset>
    </form>
    <AsyncState v-if="pending" kind="loading" /><CreditLedger v-else :entries="entries.items" />
    <AdminPagination :total="entries.total" :offset="offset" :limit="10" :busy="pending || busy" @change="offset = $event" />
  </div></AdminDialog>
</template>
