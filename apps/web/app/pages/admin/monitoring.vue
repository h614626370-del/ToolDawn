<script setup lang="ts">
import type { Monitoring } from '~/types/operations'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t, locale } = useI18n()
const data = ref<Monitoring | null>(null)
const busy = ref(false)
const error = ref('')
const automatic = ref(false)
let timer: ReturnType<typeof setInterval> | undefined
useSeoMeta({ title: () => t('系统监控') })
async function load() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { data.value = await $fetch<Monitoring>('/api/v1/admin/monitoring') }
  catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
onMounted(() => { load(); timer = setInterval(() => { if (automatic.value) load() }, 15000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>
<template>
  <div><div class="admin-page-heading"><h1>{{ $t('系统监控') }}</h1><div class="heading-actions"><label class="toggle-label"><input v-model="automatic" type="checkbox">{{ $t('自动刷新') }}</label><button class="icon-button" :disabled="busy" :title="$t('刷新')" :aria-label="$t('刷新')" @click="load"><AppIcon name="refresh" :size="18" :class="{ spin: busy }" /></button></div></div>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p><AsyncState v-if="!data && busy" kind="loading" />
    <template v-if="data"><p class="monitor-timestamp">{{ $t('最近检查') }} {{ new Date(data.checked_at).toLocaleString(locale) }}</p><div class="monitor-services"><div v-for="(probe, key) in { PostgreSQL: data.database, Redis: data.redis }" :key="key"><span class="service-dot" :class="{ healthy: probe.ok }" /><strong>{{ key }}</strong><span>{{ probe.ok ? $t('正常') : $t('连接失败') }}</span><span>{{ probe.duration_ms }} ms</span></div></div>
      <section class="settings-section"><h2>{{ $t('当前进程') }}</h2><dl class="metric-grid"><div><dt>{{ $t('运行时长') }}</dt><dd>{{ Math.floor(data.uptime_seconds / 3600) }}h {{ Math.floor(data.uptime_seconds % 3600 / 60) }}m</dd></div><div><dt>{{ $t('累计请求') }}</dt><dd>{{ data.http.total }}</dd></div><div><dt>{{ $t('近一分钟请求') }}</dt><dd>{{ data.http.requests_last_minute }}</dd></div><div><dt>{{ $t('处理中请求') }}</dt><dd>{{ data.http.inflight }}</dd></div><div><dt>{{ $t('服务端错误') }}</dt><dd>{{ data.http.server_errors }}</dd></div><div><dt>{{ $t('近一分钟 P95') }}</dt><dd>{{ data.http.p95_ms }}<small> ms</small></dd></div></dl><div class="http-statuses"><span v-for="(count, status) in data.http.statuses" :key="status">{{ status }} <strong>{{ count }}</strong></span></div></section>
    </template>
  </div>
</template>
