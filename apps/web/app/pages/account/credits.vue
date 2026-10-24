<script setup lang="ts">
import type { BillingPage, CreditEntry, CreditPackage, PaymentOrder } from '~/types/billing'
import { authError } from '~/composables/useAuth'
definePageMeta({ middleware: 'account' })
const { t } = useI18n()
useSeoMeta({ title: () => `${t('积分与充值')} · ToolDawn`, robots: 'noindex, nofollow' })
const auth = useAuth()
const route = useRoute()
const { money } = useBillingFormat()
const balance = ref(0)
const packages = ref<{ enabled: boolean; items: CreditPackage[] }>({ enabled: false, items: [] })
const entries = shallowRef<BillingPage<CreditEntry>>({ items: [], total: 0 })
const orders = shallowRef<BillingPage<PaymentOrder>>({ items: [], total: 0 })
const tab = ref('entries')
const offset = ref(0)
const pending = ref(true)
const busy = ref('')
const error = ref('')
const actionError = ref('')
const returned = ref<PaymentOrder | null>(null)
const requestKeys = new Map<string, string>()
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
let polls = 0
const orderId = typeof route.query.order === 'string' && /^[a-f0-9-]{36}$/i.test(route.query.order) ? route.query.order : ''
async function load() {
  const current = ++generation
  pending.value = true
  error.value = ''
  try {
    const [wallet, offers, history] = await Promise.all([
      $fetch<{ balance: number }>('/api/v1/billing/wallet'),
      $fetch<typeof packages.value>('/api/v1/billing/packages'),
      tab.value === 'entries'
        ? $fetch<BillingPage<CreditEntry>>('/api/v1/billing/entries', { query: { offset: offset.value, limit: 20 } })
        : $fetch<BillingPage<PaymentOrder>>('/api/v1/billing/orders', { query: { offset: offset.value, limit: 20 } }),
    ])
    if (current !== generation) return
    balance.value = wallet.balance
    packages.value = offers
    if (tab.value === 'entries') entries.value = history as BillingPage<CreditEntry>
    else orders.value = history as BillingPage<PaymentOrder>
  } catch (cause) { if (current === generation) error.value = authError(cause) }
  finally { if (current === generation) pending.value = false }
}
async function checkOrder() {
  if (timer) clearTimeout(timer)
  if (!orderId) return
  try {
    returned.value = await $fetch<PaymentOrder>(`/api/v1/billing/orders/${orderId}`)
    if (returned.value.status === 'paid') { await load(); return }
    if (returned.value.status === 'pending' && ++polls < 12) timer = setTimeout(checkOrder, 5000)
  } catch (cause) { actionError.value = authError(cause) }
}
async function checkout(offer: CreditPackage) {
  busy.value = offer.id
  actionError.value = ''
  if (!requestKeys.has(offer.id)) requestKeys.set(offer.id, crypto.randomUUID())
  try {
    const result = await $fetch<{ url: string }>('/api/v1/billing/checkout', {
      method: 'POST', body: { package_id: offer.id, request_key: requestKeys.get(offer.id) },
    })
    const url = new URL(result.url)
    if (url.protocol !== 'https:' || url.hostname !== 'checkout.stripe.com') throw new Error()
    window.location.assign(url.href)
  } catch (cause) {
    actionError.value = authError(cause)
    const status = (cause as { statusCode?: number }).statusCode
    if (status === 409) requestKeys.delete(offer.id)
  } finally { busy.value = '' }
}
onMounted(async () => {
  try {
    if (!await auth.refresh()) { await navigateTo('/login?next=/account/credits'); return }
    await load()
    await checkOrder()
  } catch (cause) { error.value = authError(cause); pending.value = false }
})
watch(tab, () => { offset.value = 0 })
watch([tab, offset], load)
onBeforeUnmount(() => { generation++; if (timer) clearTimeout(timer) })
</script>

<template>
  <div class="container billing-page">
    <AccountNav />
    <NuxtLink to="/account" class="back-link"><AppIcon name="back" :size="16" />{{ $t('我的账户') }}</NuxtLink>
    <div class="billing-heading"><div><h1>{{ $t('积分与充值') }}</h1><p>{{ $t('查看余额、充值订单和积分变动。') }}</p></div><button class="icon-button" :disabled="pending" :title="$t('刷新')" :aria-label="$t('刷新')" @click="load(); polls = 0; checkOrder()"><AppIcon name="refresh" :size="19" /></button></div>
    <p v-if="returned" role="status" class="billing-notice">{{ returned.status === 'paid' ? t('支付已确认，积分已入账。') : returned.status === 'pending' ? t('正在等待支付确认，积分到账后会自动更新。') : t('订单已结束，尚未入账。') }}</p>
    <p v-else-if="route.query.canceled" role="status" class="billing-notice">{{ $t('你已返回本站，订单状态以支付记录为准。') }}</p>
    <p v-if="actionError" role="alert" class="form-error">{{ actionError }}</p>
    <AsyncState v-if="error" kind="error" :description="error" @retry="load" />
    <AsyncState v-else-if="pending && !packages.items.length && !entries.total && !orders.total" kind="loading" :title="$t('正在读取积分')" />
    <template v-else>
      <section class="wallet-strip" :aria-label="$t('当前积分')"><span class="wallet-icon"><AppIcon name="wallet" :size="28" /></span><div><h2>{{ $t('可用积分') }}</h2><strong>{{ balance.toLocaleString() }}</strong></div><NuxtLink to="/tools" class="text-link">{{ $t('浏览工具') }}<AppIcon name="arrow" :size="17" /></NuxtLink></section>
      <section class="recharge-section"><h2>{{ $t('充值积分') }}</h2>
        <p v-if="!packages.enabled" class="billing-empty">{{ $t('在线充值尚未开放。') }}</p>
        <div v-if="packages.items.length" class="credit-packages">
          <article v-for="offer in packages.items" :key="offer.id" class="credit-package">
            <h3>{{ offer.credits.toLocaleString() }} {{ t('积分') }}</h3><p>{{ money(offer.unit_amount, offer.currency) }}</p>
            <button class="button primary" :disabled="!!busy || !packages.enabled" @click="checkout(offer)"><AppIcon :name="busy === offer.id ? 'loader' : 'card'" :size="18" :class="{ spin: busy === offer.id }" />{{ busy === offer.id ? t('请稍候') : t('前往支付') }}</button>
          </article>
        </div>
      </section>
      <section class="billing-history" :aria-busy="pending">
        <div class="billing-tabs" role="tablist" :aria-label="$t('账户记录')"><button id="entries-tab" role="tab" :aria-selected="tab === 'entries'" aria-controls="billing-panel" @click="tab = 'entries'">{{ $t('积分明细') }}</button><button id="orders-tab" role="tab" :aria-selected="tab === 'orders'" aria-controls="billing-panel" @click="tab = 'orders'">{{ $t('支付订单') }}</button></div>
        <div id="billing-panel" role="tabpanel" :aria-labelledby="tab === 'entries' ? 'entries-tab' : 'orders-tab'"><CreditLedger v-if="tab === 'entries'" :entries="entries.items" /><OrderTable v-else :orders="orders.items" /></div>
        <AdminPagination :total="tab === 'entries' ? entries.total : orders.total" :offset="offset" :limit="20" :busy="pending" @change="offset = $event" />
      </section>
    </template>
  </div>
</template>
