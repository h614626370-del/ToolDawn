<script setup lang="ts">
const { t } = useI18n()
import type { AdminCategory } from '~/types/admin'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: 'admin' })
useSeoMeta({ title: () => t('分类管理 · ToolDawn') })
const categories = ref<AdminCategory[]>([])
const pending = ref(true)
const error = ref('')
const notice = ref('')
const editing = ref(false)
const selected = ref<AdminCategory | null>(null)
async function refresh() {
  pending.value = true
  error.value = ''
  try { categories.value = await $fetch<AdminCategory[]>('/api/v1/admin/categories') }
  catch (cause) { categories.value = []; error.value = authError(cause) }
  finally { pending.value = false }
}
onMounted(refresh)
function edit(item: AdminCategory | null) { selected.value = item; editing.value = true; notice.value = '' }
async function saved() { editing.value = false; notice.value = t('分类已保存。'); await refresh() }
</script>

<template>
  <div>
    <div class="admin-page-heading"><div><h1>{{ $t('分类管理') }}</h1><p>{{ $t('调整分类名称、图标和展示顺序。') }}</p></div><button class="button primary" @click="edit(null)"><AppIcon name="plus" :size="18" />{{ $t('新增分类') }}</button></div>
    <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
    <AsyncState v-if="error" kind="error" :description="error" @retry="refresh" />
    <AsyncState v-else-if="pending" kind="loading" />
    <AsyncState v-else-if="!categories.length" kind="empty" :title="$t('还没有分类')" :description="$t('新增一个分类，开始整理工具。')" />
    <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th scope="col">{{ $t('分类') }}</th><th scope="col">{{ $t('唯一标识') }}</th><th scope="col">{{ $t('工具数量') }}</th><th scope="col">{{ $t('排序') }}</th><th scope="col">{{ $t('操作') }}</th></tr></thead><tbody><tr v-for="item in categories" :key="item.slug"><td><div class="admin-name-cell"><span class="tool-icon" :class="`tone-${item.color}`"><AppIcon :name="item.icon" :size="22" /></span><strong>{{ item.name }}</strong></div></td><td>{{ item.slug }}</td><td>{{ item.tool_count }}</td><td>{{ item.sort_order }}</td><td><button class="icon-button" :aria-label="$t('编辑 {value0}', { value0: item.name })" :title="$t('编辑分类')" @click="edit(item)"><AppIcon name="pen" :size="17" /></button></td></tr></tbody></table></div>
    <AdminCategoryEditor v-if="editing" :category="selected" @close="editing = false" @saved="saved" />
  </div>
</template>
