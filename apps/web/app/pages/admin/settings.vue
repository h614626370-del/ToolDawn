<script setup lang="ts">
import type { ModelAccount, Page, RuntimeConfig } from '~/types/operations'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: ['admin', 'superadmin'] })
const { t } = useI18n()
useSeoMeta({ title: () => t('系统设置') })
const config = ref<RuntimeConfig | null>(null)
const accounts = ref<ModelAccount[]>([])
const definitions = ref<{ slug: string; name: string; instruction: string }[]>([])
const tab = ref('site')
const pending = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const secrets = reactive({ smtp_password: '', stripe_secret_key: '', stripe_webhook_secret: '' })
const clear = reactive({ smtp_password: false, stripe_secret_key: false, stripe_webhook_secret: false })
function resetSecrets() {
  for (const key of Object.keys(secrets) as (keyof typeof secrets)[]) { secrets[key] = ''; clear[key] = false }
}
function populate(value: RuntimeConfig) {
  for (const tool of definitions.value) {
    value.tool_overrides[tool.slug] ||= { account_id: null, cost: null, enabled: true, instruction: '' }
  }
  config.value = value
}
async function load() {
  pending.value = true; error.value = ''
  try {
    const [value, list, tools] = await Promise.all([
      $fetch<RuntimeConfig>('/api/v1/admin/settings'),
      $fetch<Page<ModelAccount>>('/api/v1/admin/model-accounts'),
      $fetch<typeof definitions.value>('/api/v1/admin/tool-definitions'),
    ])
    accounts.value = list.items; definitions.value = tools; populate(value); resetSecrets()
  } catch (cause) { error.value = authError(cause) }
  finally { pending.value = false }
}
async function save() {
  if (!config.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    if (!config.value.site_name.trim() || (config.value.mail_mode === 'smtp' && !config.value.smtp_host?.trim())) {
      error.value = t('邮件或支付配置不完整，请检查配置。')
      return
    }
    const { smtp_password_set, stripe_secret_key_set, stripe_webhook_secret_set, ...values } = config.value
    const secretValues = Object.fromEntries((Object.keys(secrets) as (keyof typeof secrets)[]).map(key => [key, clear[key] ? '' : secrets[key] || null]))
    populate(await $fetch<RuntimeConfig>('/api/v1/admin/settings', { method: 'PUT', body: { ...values, ...secretValues } }))
    resetSecrets()
    notice.value = t('设置已保存并生效。')
    await refreshNuxtData('site-settings')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template><div><div class="admin-page-heading"><h1>{{ $t('系统设置') }}</h1><button class="icon-button" :disabled="busy || pending" :title="$t('重新加载')" :aria-label="$t('重新加载')" @click="load"><AppIcon name="refresh" :size="18" /></button></div>
  <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p><p v-if="error" class="form-error" role="alert">{{ error }}</p><AsyncState v-if="pending" kind="loading" />
  <form v-else-if="config" novalidate @submit.prevent="save"><div class="mode-tabs settings-tabs" role="group" :aria-label="$t('设置分类')"><button v-for="item in [{ key: 'site', name: '站点设置' }, { key: 'ai', name: 'AI 工具' }, { key: 'mail', name: '邮件服务' }, { key: 'payments', name: '支付与套餐' }]" :key="item.key" type="button" :aria-pressed="tab === item.key" :class="{ active: tab === item.key }" @click="tab = item.key">{{ $t(item.name) }}</button></div>
    <fieldset class="admin-form-fields" :disabled="busy">
      <section v-show="tab === 'site'" class="settings-section"><div class="admin-form-grid"><label class="admin-field"><span>{{ $t('站点名称') }}</span><input v-model="config.site_name" required maxlength="60"></label><label class="admin-field"><span>{{ $t('联系邮箱') }}</span><input v-model="config.contact_email" type="email" maxlength="254"></label></div><label class="admin-field"><span>{{ $t('站点公告') }}</span><textarea v-model="config.announcement" rows="3" maxlength="500" /></label><div class="admin-checks"><label><input v-model="config.registration_enabled" type="checkbox">{{ $t('开放注册') }}</label><label><input v-model="config.tickets_enabled" type="checkbox">{{ $t('开放工单') }}</label></div><NuxtLink class="text-button" to="/account/security"><AppIcon name="key" :size="16" />{{ $t('修改超级管理员账号密码') }}</NuxtLink></section>
      <SettingsBrand v-show="tab === 'site'" v-model="config.site_logo" :site-name="config.site_name" />
      <SettingsTools v-show="tab === 'ai'" :config="config" :accounts="accounts" :definitions="definitions" />
      <section v-show="tab === 'mail'" class="settings-section"><div class="admin-form-grid"><label class="admin-field"><span>{{ $t('发送方式') }}</span><select v-model="config.mail_mode"><option value="smtp">SMTP</option><option value="file">{{ $t('开发邮件文件') }}</option></select></label><label class="admin-field"><span>{{ $t('发件人') }}</span><input v-model="config.smtp_from" required maxlength="254"></label></div><div v-if="config.mail_mode === 'smtp'" class="admin-form-grid"><label class="admin-field"><span>SMTP Host</span><input v-model="config.smtp_host" required maxlength="254"></label><label class="admin-field"><span>{{ $t('端口') }}</span><input v-model.number="config.smtp_port" type="number" required min="1" max="65535"></label><label class="admin-field"><span>{{ $t('用户名') }}</span><input v-model="config.smtp_username" maxlength="254" autocomplete="off"></label><label class="admin-field"><span>{{ $t('加密方式') }}</span><select v-model="config.smtp_security"><option value="starttls">STARTTLS</option><option value="tls">TLS</option></select></label></div><label class="admin-field"><span>{{ $t('SMTP 密码') }} <small>{{ config.smtp_password_set ? $t('已配置，留空保留') : $t('尚未配置') }}</small></span><input v-model="secrets.smtp_password" type="password" autocomplete="off" maxlength="1000" :disabled="clear.smtp_password"></label><label class="toggle-label"><input v-model="clear.smtp_password" type="checkbox">{{ $t('清除保存的密钥') }}</label></section>
      <section v-show="tab === 'payments'" class="settings-section"><div v-for="key in (['stripe_secret_key', 'stripe_webhook_secret'] as const)" :key="key"><label class="admin-field"><span>{{ key === 'stripe_secret_key' ? 'Stripe Secret Key' : 'Stripe Webhook Secret' }} <small>{{ config[`${key}_set`] ? $t('已配置，留空保留') : $t('尚未配置') }}</small></span><input v-model="secrets[key]" type="password" autocomplete="off" maxlength="1000" :disabled="clear[key]"></label><label class="toggle-label"><input v-model="clear[key]" type="checkbox">{{ $t('清除保存的密钥') }}</label></div><SettingsPayments :config="config" /></section>
    </fieldset>
    <div class="settings-save"><button class="button primary" :disabled="busy"><AppIcon :name="busy ? 'loader' : 'save'" :class="{ spin: busy }" :size="17" />{{ $t('保存设置') }}</button></div>
  </form>
</div></template>
