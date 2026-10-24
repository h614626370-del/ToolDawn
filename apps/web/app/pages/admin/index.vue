<script setup lang="ts">
import type { Dashboard } from '~/types/operations'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t, locale } = useI18n()
const days = ref(7)
const data = ref<Dashboard | null>(null)
const pending = ref(true)
const error = ref('')
useSeoMeta({ title: () => t('仪表盘') })
async function load() {
  pending.value = true; error.value = ''
  try { data.value = await $fetch<Dashboard>('/api/v1/admin/dashboard', { query: { days: days.value } }) }
  catch (cause) { error.value = authError(cause) }
  finally { pending.value = false }
}
onMounted(load)
watch(days, load)
const max = computed(() => Math.max(1, ...(data.value?.daily.map(row => row.total) || [])))
const metrics = computed(() => data.value ? [
  { label: '工具调用', value: data.value.runs, icon: 'wrench' },
  { label: '成功率', value: data.value.runs ? `${Math.round(data.value.succeeded / data.value.runs * 100)}%` : '-', icon: 'check' },
  { label: '消耗积分', value: data.value.credits_used, icon: 'wallet' },
  { label: '待处理工单', value: data.value.open_tickets, icon: 'support' },
] : [])
</script>

<template>
  <div>
    <div class="admin-page-heading"><h1>{{ $t('仪表盘') }}</h1><div class="heading-actions"><select v-model="days" :aria-label="$t('统计周期')"><option :value="7">{{ $t('近 7 天') }}</option><option :value="30">{{ $t('近 30 天') }}</option></select><button class="icon-button" :disabled="pending" :title="$t('刷新')" :aria-label="$t('刷新')" @click="load"><AppIcon name="refresh" :size="18" /></button></div></div>
    <AsyncState v-if="error" kind="error" :description="error" @retry="load" />
    <AsyncState v-else-if="pending" kind="loading" />
    <template v-else-if="data">
      <dl class="metric-grid"><div v-for="metric in metrics" :key="metric.label"><dt><AppIcon :name="metric.icon" :size="18" />{{ $t(metric.label) }}</dt><dd>{{ metric.value }}</dd></div></dl>
      <section class="settings-section"><div class="section-heading"><h2>{{ $t('调用趋势') }}</h2><NuxtLink to="/admin/usage" class="text-button">{{ $t('查看记录') }}<AppIcon name="arrow" :size="16" /></NuxtLink></div>
        <div class="usage-chart" :aria-label="$t('每日调用次数')"><div v-for="day in data.daily" :key="day.day" class="chart-column"><span class="chart-count">{{ day.total }}</span><div class="chart-track"><div class="chart-bar" :style="{ height: `${day.total / max * 100}%` }" :title="`${day.day}: ${day.total}`"><span v-if="day.failed" class="chart-failed" :style="{ height: `${day.failed / day.total * 100}%` }" /></div></div><time>{{ day.day.slice(5) }}</time></div></div>
      </section>
      <div class="dashboard-columns"><section class="settings-section"><h2>{{ $t('账户概况') }}</h2><dl class="detail-list"><div><dt>{{ $t('用户总数') }}</dt><dd>{{ data.users }}</dd></div><div><dt>{{ $t('新增用户') }}</dt><dd>{{ data.new_users }}</dd></div><div><dt>{{ $t('有效会话') }}</dt><dd>{{ data.active_sessions }}</dd></div></dl></section><section class="settings-section"><h2>{{ $t('执行概况') }}</h2><dl class="detail-list"><div><dt>{{ $t('失败调用') }}</dt><dd>{{ data.failed }}</dd></div><div><dt>{{ $t('生成中') }}</dt><dd>{{ data.running }}</dd></div><div><dt>{{ $t('平均耗时') }}</dt><dd>{{ (data.average_ms / 1000).toFixed(1) }}s</dd></div></dl></section><section class="settings-section"><h2>{{ $t('实收金额') }}</h2><p v-if="!data.revenue.length" class="empty-inline">{{ $t('暂无支付收入') }}</p><dl v-else class="detail-list"><div v-for="revenue in data.revenue" :key="revenue.currency"><dt>{{ revenue.currency.toUpperCase() }}</dt><dd>{{ new Intl.NumberFormat(locale, { style: 'currency', currency: revenue.currency }).format(revenue.amount / 100) }}</dd></div></dl></section></div>
    </template>
  </div>
</template>
