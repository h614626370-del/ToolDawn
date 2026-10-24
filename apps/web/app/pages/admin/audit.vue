<script setup lang="ts">
definePageMeta({ layout: 'admin', middleware: 'admin' })
const { t, locale } = useI18n()
useSeoMeta({ title: () => t('操作日志') })
const q = ref('')
const offset = ref(0)
const query = computed(() => ({ q: q.value, offset: offset.value, limit: 20 }))
watch(q, () => { offset.value = 0 })
const { result, error, pending, refresh } = useApiList<{ id: string; email: string | null; action: string; target: string; changed_fields: string[]; created_at: string }>('/api/v1/admin/audit', query)
</script>
<template><div><div class="admin-page-heading"><h1>{{ $t('操作日志') }}</h1></div><form class="admin-toolbar" @submit.prevent="refresh"><input v-model.lazy="q" class="filter-input" :aria-label="$t('搜索操作类型')" :placeholder="$t('搜索操作类型')" maxlength="100"><button class="icon-button" :title="$t('刷新')" :aria-label="$t('刷新')" :disabled="pending"><AppIcon name="refresh" :size="18" /></button></form><AsyncState v-if="error" kind="error" :description="error" @retry="refresh" /><AsyncState v-else-if="pending" kind="loading" /><AsyncState v-else-if="!result.items.length" kind="empty" :title="$t('暂无操作日志')" /><div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th>{{ $t('操作者') }}</th><th>{{ $t('操作类型') }}</th><th>{{ $t('目标') }}</th><th>{{ $t('变更字段') }}</th><th>{{ $t('时间') }}</th></tr></thead><tbody><tr v-for="row in result.items" :key="row.id"><td>{{ row.email || '-' }}</td><td>{{ row.action }}</td><td class="audit-target">{{ row.target }}</td><td>{{ row.changed_fields.join(', ') }}</td><td>{{ new Date(row.created_at).toLocaleString(locale) }}</td></tr></tbody></table></div><AdminPagination :total="result.total" :offset="offset" :limit="20" :busy="pending" @change="offset = $event" /></div></template>
