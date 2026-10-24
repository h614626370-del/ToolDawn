<script setup lang="ts">
import type { ModelAccount, RuntimeConfig, ToolOverride } from '~/types/operations'
const props = defineProps<{ config: RuntimeConfig; accounts: ModelAccount[]; definitions: { slug: string; name: string; instruction: string }[] }>()
function override(slug: string): ToolOverride {
  return props.config.tool_overrides[slug]!
}
</script>
<template>
  <section class="settings-section">
    <div class="admin-checks"><label><input v-model="config.ai_enabled" type="checkbox">{{ $t('开放 AI 工具') }}</label></div>
    <div class="admin-form-grid">
      <label class="admin-field"><span>{{ $t('默认模型账号') }}</span><select v-model="config.default_account_id"><option :value="null">{{ $t('服务器默认账号') }}</option><option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.name }}{{ account.enabled ? '' : ` (${$t('已停用')})` }}</option></select></label>
      <label class="admin-field"><span>{{ $t('默认单次积分') }}</span><input v-model.number="config.ai_tool_cost" type="number" min="0" max="1000" required></label>
      <label class="admin-field"><span>{{ $t('每用户每分钟调用上限') }}</span><input v-model.number="config.ai_requests_per_minute" type="number" min="1" max="100" required></label>
    </div>
    <div v-for="tool in definitions" :key="tool.slug" class="tool-setting-row">
      <div class="section-heading"><h3>{{ $t(tool.name) }}</h3><label class="toggle-label"><input v-model="override(tool.slug).enabled" type="checkbox">{{ $t('启用') }}</label></div>
      <div class="admin-form-grid"><label class="admin-field"><span>{{ $t('模型账号') }}</span><select v-model="override(tool.slug).account_id"><option :value="null">{{ $t('跟随默认') }}</option><option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.name }}</option></select></label><label class="admin-field"><span>{{ $t('单次积分（留空跟随默认）') }}</span><input :value="override(tool.slug).cost ?? ''" type="number" min="0" max="1000" @input="override(tool.slug).cost = ($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value)"></label></div>
      <details><summary>{{ $t('内置提示词') }}</summary><label class="admin-field"><textarea v-model="override(tool.slug).instruction" rows="5" maxlength="8000" :aria-label="$t('内置提示词')" :placeholder="tool.instruction" /></label><button type="button" class="text-button" @click="override(tool.slug).instruction = ''"><AppIcon name="refresh" :size="15" />{{ $t('恢复默认提示词') }}</button></details>
    </div>
  </section>
</template>
