<script setup lang="ts">
import type { PaymentOrder } from '~/types/billing'
defineProps<{ orders: PaymentOrder[]; admin?: boolean; payable?: boolean; busy?: boolean }>()
defineEmits<{ select: [order: PaymentOrder]; resume: [order: PaymentOrder] }>()
const { money, date, status } = useBillingFormat()
</script>

<template>
  <div v-if="orders.length" class="admin-table-scroll">
    <table class="admin-table credit-table">
      <thead><tr><th scope="col">{{ $t('订单') }}</th><th v-if="admin" scope="col">{{ $t('邮箱') }}</th><th scope="col">{{ $t('支付供应商') }}</th><th scope="col">{{ $t('积分') }}</th><th scope="col">{{ $t('金额') }}</th><th scope="col">{{ $t('状态') }}</th><th scope="col">{{ $t('创建时间') }}</th><th v-if="payable">{{ $t('操作') }}</th></tr></thead>
      <tbody><tr v-for="order in orders" :key="order.id">
        <td><button v-if="admin" class="text-button" :aria-label="`${$t('订单详情')} ${order.id}`" @click="$emit('select', order)"><code class="order-id">{{ order.id }}</code></button><code v-else class="order-id">{{ order.id }}</code></td><td v-if="admin">{{ order.email }}</td>
        <td>{{ order.provider_name || 'Stripe' }}</td><td>{{ order.credits.toLocaleString() }}</td><td>{{ money(order.unit_amount, order.currency) }}</td>
        <td><span class="admin-state" :class="{ enabled: order.status === 'paid' }">{{ status(order.status) }}</span></td>
        <td>{{ date(order.created_at) }}</td>
        <td v-if="payable"><button v-if="order.status === 'pending' && new Date(order.expires_at).getTime() > Date.now()" class="text-button" :disabled="busy" @click="$emit('resume', order)">{{ $t('继续支付') }}</button><span v-else>—</span></td>
      </tr></tbody>
    </table>
  </div>
  <p v-else class="billing-empty">{{ $t('暂无支付订单') }}</p>
</template>
