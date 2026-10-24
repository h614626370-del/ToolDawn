<script setup lang="ts">
import type { PaymentOrder } from '~/types/billing'
defineProps<{ orders: PaymentOrder[]; admin?: boolean }>()
const { money, date, status } = useBillingFormat()
</script>

<template>
  <div v-if="orders.length" class="admin-table-scroll">
    <table class="admin-table credit-table">
      <thead><tr><th scope="col">{{ $t('订单') }}</th><th v-if="admin" scope="col">{{ $t('邮箱') }}</th><th scope="col">{{ $t('积分') }}</th><th scope="col">{{ $t('金额') }}</th><th scope="col">{{ $t('状态') }}</th><th scope="col">{{ $t('创建时间') }}</th></tr></thead>
      <tbody><tr v-for="order in orders" :key="order.id">
        <td><code class="order-id">{{ order.id }}</code></td><td v-if="admin">{{ order.email }}</td>
        <td>{{ order.credits.toLocaleString() }}</td><td>{{ money(order.unit_amount, order.currency) }}</td>
        <td><span class="admin-state" :class="{ enabled: order.status === 'paid' }">{{ status(order.status) }}</span></td>
        <td>{{ date(order.created_at) }}</td>
      </tr></tbody>
    </table>
  </div>
  <p v-else class="billing-empty">{{ $t('暂无支付订单') }}</p>
</template>
