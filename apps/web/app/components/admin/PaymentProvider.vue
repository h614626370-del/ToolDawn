<script setup lang="ts">
import type { PaymentConfig } from '~/types/billing'
import { authError } from '~/composables/useAuth'
const { t } = useI18n()
const config = ref<PaymentConfig | null>(null)
const pending = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const keys = ['stripe_secret_key', 'stripe_webhook_secret'] as const
const secrets = reactive({ stripe_secret_key: '', stripe_webhook_secret: '' })
const clear = reactive({ stripe_secret_key: false, stripe_webhook_secret: false })
function reset() { for (const key of keys) { secrets[key] = ''; clear[key] = false } }
async function load() {
  pending.value = true; error.value = ''; notice.value = ''
  try { config.value = await $fetch<PaymentConfig>('/api/v1/admin/billing/config'); reset() }
  catch (cause) { error.value = authError(cause) }
  finally { pending.value = false }
}
async function save() {
  if (!config.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    config.value = await $fetch<PaymentConfig>('/api/v1/admin/billing/config', { method: 'PUT', body: {
      revision: config.value.revision, credit_packages: config.value.credit_packages,
      ...Object.fromEntries(keys.map(key => [key, clear[key] ? '' : secrets[key] || null])),
    } })
    reset(); notice.value = t('设置已保存并生效。')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <div>
    <ProviderManager />
    <AsyncState v-if="pending" kind="loading" :title="$t('正在加载数据')" />
    <p v-if="error" class="form-error" role="alert">{{ error }} <button class="text-button" :disabled="busy || pending" @click="load">{{ $t('重新加载') }}</button></p>
    <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
    <form v-if="config && !pending" @submit.prevent="save">
      <fieldset class="admin-form-fields" :disabled="busy">
        <details class="settings-section legacy-payment">
          <summary>{{ $t('原有 Stripe 配置（兼容入口）') }}</summary>
          <div class="section-heading"><div><h2>Stripe Checkout</h2><p class="muted">{{ $t('支付供应商') }}</p></div><span class="admin-state" :class="{ enabled: config.stripe_secret_key_set && config.stripe_webhook_secret_set && config.credit_packages.length }">{{ config.stripe_secret_key_set && config.stripe_webhook_secret_set && config.credit_packages.length ? $t('配置已就绪') : $t('待完善配置') }}</span></div>
          <p class="payment-help">{{ $t('当前支持 Stripe。配置就绪仅表示必填项齐全，实际支付以供应商和签名回调为准。') }}</p>
          <div class="admin-form-grid"><div v-for="key in keys" :key="key"><label class="admin-field"><span>{{ key === 'stripe_secret_key' ? 'Secret Key' : 'Webhook Secret' }} <small>{{ config[`${key}_set`] ? $t('已配置，留空保留') : $t('尚未配置') }}</small></span><input v-model="secrets[key]" type="password" autocomplete="new-password" maxlength="1000" :disabled="clear[key]"></label><label class="toggle-label"><input v-model="clear[key]" type="checkbox">{{ $t('清除保存的密钥') }}</label></div></div>
          <div class="payment-help"><strong>{{ $t('回调接入') }}</strong><p>{{ $t('在 Stripe 中配置站点公开 HTTPS 域名加以下路径，并订阅这些事件。') }}</p><code>/api/v1/billing/webhook</code><ul><li><code>checkout.session.completed</code></li><li><code>checkout.session.async_payment_succeeded</code></li><li><code>checkout.session.async_payment_failed</code></li><li><code>checkout.session.expired</code></li></ul></div>
        </details>
        <SettingsPayments :config="config" />
      </fieldset>
      <div class="settings-save"><button class="button primary" :disabled="busy"><AppIcon :name="busy ? 'loader' : 'save'" :size="17" :class="{ spin: busy }" />{{ $t('保存支付配置') }}</button></div>
    </form>
  </div>
</template>
