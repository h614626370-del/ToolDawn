<script setup lang="ts">
import type { PaymentOrder } from '~/types/billing'
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t } = useI18n()
useSeoMeta({ title: () => `${t('支付订单')} · ToolDawn` })
const offset = ref(0)
const query = computed(() => ({ offset: offset.value, limit: 20 }))
const { result, pending, error, refresh } = useAdminList<PaymentOrder>('billing/orders', query)
</script>

<template>
  <div><div class="admin-page-heading"><div><h1>{{ $t('支付订单') }}</h1><p>{{ $t('查看充值金额、积分和支付状态。') }}</p></div><button class="icon-button" :disabled="pending" :title="$t('刷新')" :aria-label="$t('刷新')" @click="refresh"><AppIcon name="refresh" :size="19" /></button></div>
    <AsyncState v-if="error" kind="error" :description="error" @retry="refresh" />
    <AsyncState v-else-if="pending" kind="loading" />
    <OrderTable v-else :orders="result.items" admin />
    <AdminPagination :total="result.total" :offset="offset" :limit="20" :busy="pending" @change="offset = $event" />
  </div>
</template>
