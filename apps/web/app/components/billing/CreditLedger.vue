<script setup lang="ts">
import type { CreditEntry } from '~/types/billing'
import { accountToolNames } from '~/utils/accountTools'
defineProps<{ entries: CreditEntry[] }>()
const { date, kind } = useBillingFormat()
</script>

<template>
  <div v-if="entries.length" class="admin-table-scroll">
    <table class="admin-table credit-table">
      <thead><tr><th scope="col">{{ $t('时间') }}</th><th scope="col">{{ $t('类型') }}</th><th scope="col">{{ $t('积分变动') }}</th><th scope="col">{{ $t('变动后余额') }}</th><th scope="col">{{ $t('说明') }}</th></tr></thead>
      <tbody><tr v-for="entry in entries" :key="entry.id">
        <td>{{ date(entry.created_at) }}</td><td>{{ kind(entry.kind) }}</td>
        <td class="credit-amount" :class="{ positive: entry.amount > 0 }">{{ entry.amount > 0 ? '+' : '' }}{{ entry.amount.toLocaleString() }}</td>
        <td>{{ entry.balance_after.toLocaleString() }}</td><td>{{ accountToolNames[entry.reason] ? $t(accountToolNames[entry.reason]!) : $te(entry.reason) ? $t(entry.reason) : entry.reason }}</td>
      </tr></tbody>
    </table>
  </div>
  <p v-else class="billing-empty">{{ $t('暂无积分记录') }}</p>
</template>
