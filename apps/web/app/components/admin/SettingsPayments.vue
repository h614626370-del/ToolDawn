<script setup lang="ts">
import type { CreditPackage } from '~/types/billing'
defineProps<{ config: { credit_packages: CreditPackage[] } }>()
</script>
<template>
  <section class="settings-section">
    <div class="section-heading"><h2>{{ $t('积分套餐') }}</h2>
      <button class="button secondary" type="button" :disabled="config.credit_packages.length >= 20" @click="config.credit_packages.push({ id: '', credits: 100, unit_amount: 500, currency: 'usd' })"><AppIcon name="plus" :size="16" />{{ $t('添加套餐') }}</button>
    </div>
    <div v-for="(pack, index) in config.credit_packages" :key="index" class="package-setting-row">
      <div class="admin-form-grid">
        <label class="admin-field"><span>{{ $t('套餐标识') }}</span><input v-model="pack.id" required maxlength="50" pattern="[a-z0-9][a-z0-9-]*"></label>
        <label class="admin-field"><span>{{ $t('积分数量') }}</span><input v-model.number="pack.credits" type="number" required min="1" max="100000000"></label>
        <label class="admin-field"><span>{{ $t('价格（最小货币单位）') }}</span><input v-model.number="pack.unit_amount" type="number" required min="50" max="100000000"></label>
        <label class="admin-field"><span>{{ $t('币种') }}</span><select v-model="pack.currency"><option value="usd">USD</option><option value="cny">CNY</option><option value="eur">EUR</option></select></label>
      </div>
      <button class="icon-button" type="button" :title="$t('删除套餐')" :aria-label="$t('删除套餐')" @click="config.credit_packages.splice(index, 1)"><AppIcon name="trash" :size="18" /></button>
    </div>
  </section>
</template>
