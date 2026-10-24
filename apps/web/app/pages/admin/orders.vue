<script setup lang="ts">
import type { PaymentOrder, PaymentStatistics } from '~/types/billing'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t } = useI18n()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
useSeoMeta({ title: () => `${t('支付管理')} · ToolDawn` })
const tab = computed(() => ['statistics', 'list', 'config'].includes(String(route.query.tab)) ? String(route.query.tab) : 'statistics')
const tabs = computed(() => [{ key: 'statistics', name: '统计' }, { key: 'list', name: '订单列表' }, ...(auth.user.value?.is_superadmin ? [{ key: 'config', name: '供应商配置' }] : [])])
function setTab(value: string) { router.replace({ query: { ...route.query, tab: value } }) }
const { money, date, status: statusLabel } = useBillingFormat()
const { draft, filters, filterError, apply, reset } = useAdminDateFilters()
const draftStatus = ref('')
const status = ref('')
const offset = ref(0)
const states = ['pending', 'paid', 'expired', 'failed'] as const
const query = computed(() => ({ ...filters.value, status: status.value || undefined, offset: offset.value, limit: 20 }))
const { result, pending, error, refresh } = useAdminList<PaymentOrder>('billing/orders', query)
const stats = ref<PaymentStatistics | null>(null)
const statsPending = ref(true)
const statsError = ref('')
const selected = ref<PaymentOrder | null>(null)
let sequence = 0
async function loadStats() {
  const current = ++sequence
  statsPending.value = true; statsError.value = ''
  try {
    const value = await $fetch<PaymentStatistics>('/api/v1/admin/billing/statistics', { query: { ...filters.value, status: status.value || undefined } })
    if (current === sequence) stats.value = value
  } catch (cause) { if (current === sequence) statsError.value = authError(cause) }
  finally { if (current === sequence) statsPending.value = false }
}
function search() { if (apply()) { status.value = draftStatus.value; offset.value = 0 } }
function clearFilters() { draftStatus.value = ''; status.value = ''; offset.value = 0; reset() }
function inspectStatus(value: string) { draftStatus.value = value; status.value = value; offset.value = 0; setTab('list') }
onMounted(loadStats)
watch([filters, status], loadStats)
onBeforeUnmount(() => { sequence++ })
</script>

<template>
  <div>
    <div class="admin-page-heading"><div><h1>{{ $t('支付管理') }}</h1><p>{{ $t('查看交易表现、追踪订单，管理支付接入。') }}</p></div><button v-if="tab !== 'config'" class="icon-button" :disabled="pending || statsPending" :title="$t('刷新')" :aria-label="$t('刷新')" @click="refresh(); loadStats()"><AppIcon name="refresh" :size="19" /></button></div>
    <div class="mode-tabs settings-tabs" role="group" :aria-label="$t('支付管理')"><button v-for="item in tabs" :key="item.key" :class="{ active: tab === item.key }" :aria-pressed="tab === item.key" @click="setTab(item.key)">{{ $t(item.name) }}</button></div>
    <div v-show="tab !== 'config'">
      <form class="admin-toolbar payment-filters" role="search" @submit.prevent="search">
        <label class="admin-search"><AppIcon name="search" :size="18" /><input v-model="draft.q" :aria-label="$t('邮箱、订单号或套餐标识')" :placeholder="$t('邮箱、订单号或套餐标识')" maxlength="100"></label>
        <select v-model="draftStatus" :aria-label="$t('支付状态')"><option value="">{{ $t('全部状态') }}</option><option v-for="value in states" :key="value" :value="value">{{ statusLabel(value) }}</option></select>
        <label class="date-filter">{{ $t('开始日期') }}<input v-model="draft.start" type="date"></label><label class="date-filter">{{ $t('结束日期') }}<input v-model="draft.end" type="date"></label>
        <button class="button primary">{{ $t('查询') }}</button><button class="text-button" type="button" @click="clearFilters">{{ $t('重置筛选') }}</button>
      </form>
      <p v-if="filterError" role="alert" class="form-error">{{ filterError }}</p>
      <p class="payment-help">{{ $t('日期按本地时区的订单创建时间筛选，包含结束当天；收入仅统计这些订单中已支付的金额，按币种分别展示。') }}</p>
      <section v-if="tab === 'statistics'">
        <AsyncState v-if="statsError" kind="error" :title="$t('支付数据加载失败')" :description="statsError" @retry="loadStats" /><AsyncState v-else-if="statsPending" kind="loading" :title="$t('正在加载数据')" />
        <template v-else-if="stats">
          <dl class="metric-grid"><div><dt>{{ $t('订单总数') }}<AppIcon name="receipt" /></dt><dd>{{ stats.total.toLocaleString() }}</dd></div><div><dt>{{ $t('已支付订单') }}<AppIcon name="check" /></dt><dd>{{ stats.statuses.paid.toLocaleString() }}</dd></div><div><dt>{{ $t('订单支付率') }}<AppIcon name="chart" /></dt><dd>{{ stats.total ? `${(stats.statuses.paid / stats.total * 100).toFixed(1)}%` : '—' }}</dd></div><div><dt>{{ $t('已发放积分') }}<AppIcon name="wallet" /></dt><dd>{{ stats.revenue.reduce((sum, row) => sum + row.credits, 0).toLocaleString() }}</dd></div></dl>
          <div class="dashboard-columns payment-summary-columns"><section class="settings-section"><h2>{{ $t('实收金额') }}</h2><p v-if="!stats.revenue.length" class="billing-empty">{{ $t('暂无已支付订单') }}</p><dl v-else class="detail-list"><div v-for="row in stats.revenue" :key="row.currency"><dt>{{ row.currency.toUpperCase() }} <small>· {{ row.orders }} {{ $t('笔订单') }}</small></dt><dd>{{ money(row.amount, row.currency) }}</dd></div></dl></section><section class="settings-section"><h2>{{ $t('订单状态分布') }}</h2><div v-for="value in states" :key="value" class="payment-status-row"><button class="text-button" @click="inspectStatus(value)">{{ statusLabel(value) }}</button><meter min="0" :max="Math.max(stats.total, 1)" :value="stats.statuses[value]" :aria-label="statusLabel(value)" /><strong>{{ stats.statuses[value] }}</strong></div></section></div>
        </template>
      </section>
      <section v-else-if="tab === 'list'">
        <AsyncState v-if="error" kind="error" :title="$t('支付数据加载失败')" :description="error" @retry="refresh" /><AsyncState v-else-if="pending" kind="loading" :title="$t('正在加载数据')" />
        <OrderTable v-else :orders="result.items" admin @select="selected = $event" />
        <AdminPagination :total="result.total" :offset="offset" :limit="20" :busy="pending" @change="offset = $event" />
      </section>
    </div>
    <PaymentProvider v-if="auth.user.value?.is_superadmin" v-show="tab === 'config'" />
    <p v-else-if="tab === 'config'" class="payment-help">{{ $t('支付配置仅对超级管理员开放。') }}</p>
    <AdminDialog v-if="selected" :title="$t('订单详情')" @close="selected = null"><div class="admin-editor"><dl class="detail-list payment-detail"><div><dt>{{ $t('订单') }}</dt><dd><code>{{ selected.id }}</code></dd></div><div><dt>{{ $t('邮箱') }}</dt><dd>{{ selected.email }}</dd></div><div><dt>{{ $t('套餐标识') }}</dt><dd>{{ selected.package_id }}</dd></div><div><dt>{{ $t('状态') }}</dt><dd>{{ statusLabel(selected.status) }}</dd></div><div><dt>{{ $t('金额') }}</dt><dd>{{ money(selected.unit_amount, selected.currency) }}</dd></div><div><dt>{{ $t('积分') }}</dt><dd>{{ selected.credits }}</dd></div><div><dt>{{ $t('创建时间') }}</dt><dd>{{ date(selected.created_at) }}</dd></div><div><dt>{{ $t('到期时间') }}</dt><dd>{{ date(selected.expires_at) }}</dd></div><div><dt>{{ $t('支付时间') }}</dt><dd>{{ selected.paid_at ? date(selected.paid_at) : '—' }}</dd></div></dl></div></AdminDialog>
  </div>
</template>
