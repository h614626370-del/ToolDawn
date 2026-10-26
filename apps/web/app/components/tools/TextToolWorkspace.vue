<script setup lang="ts">
import type { Tool } from '~/types/catalog'
import type { TextToolConfig } from '~/types/ai-tools'
const props = defineProps<{ tool: Tool; config: TextToolConfig }>()
const { t } = useI18n()
const {
  auth, text, context, style, language, balance, busy, loading, error, feedback,
  active, history, generate, sample, copy, download, clearOutput, refresh,
} = useTextTool(props.config)
const { date } = useBillingFormat()
const languages = [
  ['zh', '简体中文'], ['en', 'English'], ['ja', '日本語'], ['ko', '한국어'],
  ['fr', 'Français'], ['de', 'Deutsch'], ['es', 'Español'],
]
const canGenerate = computed(() => props.config.enabled && !!auth.user.value
  && !busy.value && !loading.value && text.value.trim().length >= 2
  && (balance.value ?? 0) >= props.config.cost)
</script>

<template>
  <article class="text-workspace">
    <ToolPageHeading :tool="tool" />
    <div v-if="config.enabled" class="workspace-meta">
      <span><AppIcon name="sparkles" :size="16" />{{ config.cost ? t('每次 {cost} 积分', { cost: config.cost }) : t('免费使用') }}</span>
      <NuxtLink v-if="auth.user.value" to="/account/credits" class="text-link"><AppIcon name="wallet" :size="16" />{{ balance === null ? t('读取余额中') : t('余额 {balance}', { balance }) }}</NuxtLink>
    </div>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <div class="workspace-editors">
      <form class="workspace-input" @submit.prevent="generate">
        <div class="editor-bar"><label for="tool-source">{{ $t(config.input_label) }}</label><button type="button" class="text-button" :disabled="busy" @click="sample"><AppIcon name="sparkles" :size="15" />{{ $t('填入示例') }}</button></div>
        <textarea id="tool-source" v-model="text" :maxlength="config.max_length" :placeholder="$t(config.placeholder)" :disabled="busy" required minlength="2" />
        <div class="source-footer"><span>{{ text.length.toLocaleString() }} / {{ config.max_length.toLocaleString() }}</span><button type="button" class="icon-button" :title="$t('清空输入')" :aria-label="$t('清空输入')" :disabled="busy || !text" @click="text = ''"><AppIcon name="trash" :size="16" /></button></div>
        <div class="workspace-options">
          <div><label for="tool-style">{{ $t('表达风格') }}</label><select id="tool-style" v-model="style" :disabled="busy"><option v-for="item in config.styles" :key="item" :value="item">{{ $t(item) }}</option></select></div>
          <div><label for="tool-language">{{ $t('输出语言') }}</label><select id="tool-language" v-model="language" :disabled="busy"><option v-for="[code, name] in languages" :key="code" :value="code">{{ name }}</option></select></div>
        </div>
        <details class="workspace-extra"><summary>{{ $t('补充要求（选填）') }}<AppIcon name="chevron" :size="16" /></summary>
        <label class="sr-only" for="tool-context">{{ $t('补充要求（选填）') }}</label>
        <textarea id="tool-context" v-model="context" class="context-input" maxlength="1000" :disabled="busy" :placeholder="$t('例如：面向新用户，保留专业术语，控制在 200 字以内…')" />
        </details>
        <div class="workspace-submit">
          <button v-if="!config.enabled" class="button primary" type="button" disabled>{{ $t('暂不可用') }}</button>
          <NuxtLink v-else-if="!loading && !auth.user.value" :to="`/login?next=/tools/${tool.slug}`" class="button primary"><AppIcon name="login" :size="18" />{{ $t('登录后使用') }}</NuxtLink>
          <button v-else class="button primary" type="submit" :disabled="!canGenerate"><AppIcon :name="busy ? 'loader' : 'sparkles'" :size="18" :class="{ spin: busy }" />{{ busy ? t('正在生成') : t('开始生成') }}</button>
          <NuxtLink v-if="config.enabled && auth.user.value && balance !== null && balance < config.cost" to="/account/credits" class="text-link">{{ $t('积分不足，查看积分') }}</NuxtLink>
        </div>
      </form>
      <section class="workspace-result" :aria-label="$t('生成结果')" :aria-busy="busy">
        <div class="editor-bar"><h2>{{ $t('生成结果') }}</h2>
          <div class="workspace-result-actions">
            <button class="icon-button" :disabled="!active?.output || busy" :title="$t('复制结果')" :aria-label="$t('复制结果')" @click="copy"><AppIcon name="copy" :size="17" /></button>
            <button class="icon-button" :disabled="!active?.output || busy" :title="$t('下载文本')" :aria-label="$t('下载文本')" @click="download"><AppIcon name="download" :size="17" /></button>
            <button class="icon-button" :disabled="!active?.output || busy" :title="$t('删除此结果')" :aria-label="$t('删除此结果')" @click="clearOutput"><AppIcon name="trash" :size="17" /></button>
          </div>
        </div>
        <div v-if="busy" class="result-empty" role="status"><AppIcon name="loader" :size="32" class="spin" /><p>{{ $t('正在整理你的内容…') }}</p></div>
        <div v-else-if="active?.status === 'failed'" class="result-empty" role="alert"><AppIcon name="alert" :size="30" /><p>{{ $t(active.error || '生成未完成，已退回本次积分，请重新尝试。') }}</p></div>
        <pre v-else-if="active?.output" class="result-text" tabindex="0">{{ active.output }}</pre>
        <div v-else class="result-empty"><span class="result-empty-icon"><AppIcon name="text" :size="28" /></span><h3>{{ $t('让想法变成合适的表达') }}</h3><p>{{ $t('填写内容并选择偏好，生成结果后即可复制或下载。') }}</p></div>
        <p class="result-feedback" role="status">{{ feedback }}</p>
      </section>
    </div>
    <p class="workspace-footnote">{{ $t('内容将发送给模型服务商处理。AI 可能出错，请核实后使用。失败自动退分。') }}</p>
    <details v-if="auth.user.value" class="workspace-history">
      <summary>{{ $t('最近生成记录') }}<span class="history-count">{{ history.length }}</span><AppIcon name="chevron" :size="16" /></summary>
      <div class="history-toolbar"><span>{{ $t('选择记录可再次查看结果') }}</span><button class="icon-button" :title="$t('刷新')" :aria-label="$t('刷新')" :disabled="loading || busy" @click="refresh"><AppIcon name="refresh" :size="17" /></button></div>
      <p v-if="!history.length" class="muted">{{ $t('还没有生成记录') }}</p>
      <ul v-else>
        <li v-for="run in history" :key="run.id">
          <button :disabled="busy || (run.status === 'succeeded' && !run.output)" :class="{ selected: active?.id === run.id }" @click="active = run; feedback = ''">
            <AppIcon :name="run.status === 'succeeded' ? 'check' : run.status === 'running' ? 'loader' : 'alert'" :size="17" />
            <time :datetime="run.created_at">{{ date(run.created_at) }}</time>
            <span class="history-excerpt">{{ run.output?.slice(0, 90) || (run.status === 'failed' ? t('生成失败，积分已退回') : run.status === 'running' ? t('正在生成') : t('结果已删除')) }}</span>
            <AppIcon name="arrow" :size="16" />
          </button>
        </li>
      </ul>
    </details>
  </article>
</template>
