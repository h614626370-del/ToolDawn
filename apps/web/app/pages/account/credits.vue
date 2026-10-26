<script setup lang="ts">
import type { BillingPage, CreditEntry, CreditPackage, PaymentOrder } from '~/types/billing'
import type { CheckoutResult, PaymentMethod } from '~/types/payment-provider'
import { authError } from '~/composables/useAuth'
definePageMeta({ middleware: 'account', layout: 'account' })
const { t } = useI18n()
useSeoMeta({ title: () => `${t('积分与充值')} · ToolDawn`, robots: 'noindex, nofollow' })
const auth = useAuth()
const route = useRoute()
const { money, date } = useBillingFormat()
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
const methods = ref<PaymentMethod[]>([])
const offer = ref<CreditPackage | null>(null)
const channel = ref('')
const payment = ref<CheckoutResult | null>(null)
const qrImage = ref('')
const paymentOpen = ref(false)
const activeOrderId = ref('')
const channels = computed(() => methods.value.filter(item => !offer.value || item.currencies.includes(offer.value.currency)).flatMap(item => item.methods.map(method => ({ key: `${item.id || 'legacy'}:${method}`, provider: item, method }))))
const methodName = (value: string) => t(({ alipay: '支付宝', wxpay: '微信支付', card: '银行卡', airwallex: 'Airwallex' } as Record<string, string>)[value] || value)
watch(channels, list => { if (!list.some(item => item.key === channel.value)) channel.value = list[0]?.key || '' })
const requestKeys = new Map<string, string>()
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
let polls = 0
let pollSequence = 0
const orderId = typeof route.query.order === 'string' && /^[a-f0-9-]{36}$/i.test(route.query.order) ? route.query.order : ''
async function load() {
  const current = ++generation
  pending.value = true
  error.value = ''
  try {
    const [wallet, offers, history, availableMethods] = await Promise.all([
      $fetch<{ balance: number }>('/api/v1/billing/wallet'),
      $fetch<typeof packages.value>('/api/v1/billing/packages'),
      tab.value === 'entries'
        ? $fetch<BillingPage<CreditEntry>>('/api/v1/billing/entries', { query: { offset: offset.value, limit: 20 } })
        : $fetch<BillingPage<PaymentOrder>>('/api/v1/billing/orders', { query: { offset: offset.value, limit: 20 } }),
      $fetch<{ items: PaymentMethod[] }>('/api/v1/billing/methods'),
    ])
    if (current !== generation) return
    balance.value = wallet.balance
    packages.value = offers
    methods.value = availableMethods.items
    if (tab.value === 'entries') entries.value = history as BillingPage<CreditEntry>
    else orders.value = history as BillingPage<PaymentOrder>
  } catch (cause) { if (current === generation) error.value = authError(cause) }
  finally { if (current === generation) pending.value = false }
}
async function checkOrder() {
  if (timer) clearTimeout(timer)
  if (!activeOrderId.value) return
  const current = ++pollSequence
  const identity = activeOrderId.value
  try {
    const result = await $fetch<PaymentOrder>(`/api/v1/billing/orders/${identity}`)
    if (current !== pollSequence || activeOrderId.value !== identity) return
    returned.value = result
    if (returned.value.status === 'paid') { await load(); return }
    if (returned.value.status === 'pending' && ++polls < 120) timer = setTimeout(checkOrder, 5000)
  } catch (cause) { if (current === pollSequence && activeOrderId.value === identity) actionError.value = authError(cause) }
}
function checkout(value: CreditPackage) {
  offer.value = value; payment.value = null; returned.value = null; qrImage.value = ''; actionError.value = ''; paymentOpen.value = true
  if (timer) clearTimeout(timer)
  pollSequence++; activeOrderId.value = ''
  channel.value = channels.value[0]?.key || ''
}
async function showPayment(result: CheckoutResult) {
  if (result.url) {
    const url = new URL(result.url)
    if (url.protocol !== 'https:' || url.username || url.password) throw new Error()
  }
  if (!result.url && !result.qr_code) throw new Error()
  payment.value = result; paymentOpen.value = true; activeOrderId.value = result.order_id; qrImage.value = ''
  if (result.qr_code) {
    const QRCode = await import('qrcode')
    qrImage.value = await QRCode.toDataURL(result.qr_code, { width: 256, margin: 2, errorCorrectionLevel: 'M' })
  }
  polls = 0; await checkOrder()
}
async function createPayment() {
  const choice = channels.value.find(item => item.key === channel.value)
  if (!offer.value || !choice) return
  const key = `${offer.value.id}:${choice.key}`
  busy.value = offer.value.id; actionError.value = ''
  if (!requestKeys.has(key)) requestKeys.set(key, crypto.randomUUID())
  try {
    const result = await $fetch<CheckoutResult>('/api/v1/billing/checkout', {
      method: 'POST', body: { package_id: offer.value.id, request_key: requestKeys.get(key), provider_id: choice.provider.id, payment_method: choice.method },
    })
    await showPayment(result)
  } catch (cause) {
    actionError.value = authError(cause)
    if ((cause as { statusCode?: number }).statusCode === 409) requestKeys.delete(key)
  } finally { busy.value = '' }
}
async function resume(order: PaymentOrder) {
  busy.value = order.id; actionError.value = ''; returned.value = null
  try { await showPayment(await $fetch<CheckoutResult>(`/api/v1/billing/orders/${order.id}/resume`, { method: 'POST' })) }
  catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = '' }
}
function closePayment() {
  if (busy.value) return
  paymentOpen.value = false; pollSequence++; activeOrderId.value = ''
  if (timer) clearTimeout(timer)
  load()
}
onMounted(async () => {
  try {
    if (!await auth.refresh(5000)) { await navigateTo('/login?next=/account/credits'); return }
    await load()
    activeOrderId.value = orderId
    await checkOrder()
  } catch (cause) { error.value = authError(cause); pending.value = false }
})
watch(tab, () => { offset.value = 0 })
watch([tab, offset], load)
onBeforeUnmount(() => { generation++; pollSequence++; if (timer) clearTimeout(timer) })
</script>

<template>
  <div class="account-billing">


    <AccountHeading title="积分与充值" description="查看余额、充值订单和积分变动。"><button class="icon-button" :disabled="pending" :title="$t('刷新')" :aria-label="$t('刷新')" @click="load(); polls = 0; checkOrder()"><AppIcon name="refresh" :size="19" /></button></AccountHeading>
    <p v-if="returned" role="status" class="billing-notice">{{ returned.status === 'paid' ? t('支付已确认，积分已入账。') : returned.status === 'pending' ? t('正在等待支付确认，积分到账后会自动更新。') : t('订单已结束，尚未入账。') }}</p>
    <p v-else-if="route.query.canceled" role="status" class="billing-notice">{{ $t('你已返回本站，订单状态以支付记录为准。') }}</p>
    <p v-if="actionError" role="alert" class="form-error">{{ actionError }}</p>
    <AsyncState v-if="error" kind="error" :title="$t('暂时无法加载')" :description="error" @retry="load" />
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
        <div id="billing-panel" role="tabpanel" :aria-labelledby="tab === 'entries' ? 'entries-tab' : 'orders-tab'"><CreditLedger v-if="tab === 'entries'" :entries="entries.items" /><OrderTable v-else :orders="orders.items" payable :busy="!!busy" @resume="resume" /></div>
        <AdminPagination :total="tab === 'entries' ? entries.total : orders.total" :offset="offset" :limit="20" :busy="pending" @change="offset = $event" />
      </section>
    </template>
    <AccountDialog v-if="paymentOpen" :title="$t('充值支付')" :busy="!!busy" @close="closePayment">
      <div class="payment-checkout">
        <template v-if="!payment">
          <div v-if="offer" class="payment-offer"><strong>{{ money(offer.unit_amount, offer.currency) }}</strong><span>{{ offer.credits.toLocaleString() }} {{ $t('积分') }}</span></div>
          <fieldset class="payment-methods" :disabled="!!busy"><legend>{{ $t('选择支付方式') }}</legend><label v-for="item in channels" :key="item.key" :class="{ selected: channel === item.key }"><input v-model="channel" type="radio" name="payment-method" :value="item.key"><span><strong>{{ methodName(item.method) }}</strong><small>{{ item.provider.name }}</small></span><AppIcon name="card" :size="22" /></label></fieldset>
          <p v-if="!channels.length" class="billing-empty">{{ $t('此套餐暂时没有可用的支付渠道，请选择其他币种套餐。') }}</p>
          <button class="button primary" :disabled="!!busy || !channel" @click="createPayment"><AppIcon :name="busy ? 'loader' : 'card'" :class="{ spin: busy }" :size="18" />{{ $t('创建支付订单') }}</button>
        </template>
        <template v-else>
          <div v-if="returned?.status === 'paid'" class="payment-success"><AppIcon name="check" :size="36" /><h3>{{ $t('支付已确认，积分已入账。') }}</h3></div>
          <template v-else-if="!returned || returned.status === 'pending'">
            <img v-if="qrImage" :src="qrImage" class="payment-qr" :alt="$t('微信支付二维码')" width="256" height="256">
            <p v-if="payment.qr_code">{{ $t('请使用微信扫一扫完成支付。') }}</p>
            <a v-if="payment.url" class="button primary" :href="payment.url" target="_blank" rel="noopener noreferrer">{{ $t('打开支付收银台') }}<AppIcon name="external" :size="17" /></a>
            <p class="muted">{{ $t('完成支付后此页会自动更新，也可以手动查询结果。') }}</p>
            <button class="button secondary" @click="polls = 0; checkOrder()">{{ $t('查询支付结果') }}</button>
          </template>
          <p v-else>{{ $t('订单已结束，尚未入账。') }}</p>
          <code class="payment-order-reference">{{ payment.order_id }}</code>
          <p v-if="payment.expires_at" class="muted">{{ $t('到期时间') }} · {{ date(payment.expires_at) }}</p>
        </template>
        <p v-if="actionError" role="alert" class="form-error">{{ actionError }}</p>
      </div>
    </AccountDialog>
  </div>
</template>
