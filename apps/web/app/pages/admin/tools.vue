<script setup lang="ts">
const { t } = useI18n()
import type { AdminCategory, AdminTool } from '~/types/admin'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: 'admin' })
useSeoMeta({ title: () => t('工具管理 · ToolDawn') })
const draft = ref('')
const search = ref('')
const category = ref('')
const published = ref('')
const offset = ref(0)
const limit = 20
const query = computed(() => ({ q: search.value, category: category.value || undefined, published: published.value === '' ? undefined : published.value === 'true', offset: offset.value, limit }))
const { result, pending, error, refresh } = useAdminList<AdminTool>('tools', query)
const categories = ref<AdminCategory[]>([])
const categoryError = ref('')
const editing = ref(false)
const selected = ref<AdminTool | null>(null)
const notice = ref('')
async function loadCategories() {
  categoryError.value = ''
  try { categories.value = await $fetch<AdminCategory[]>('/api/v1/admin/categories') }
  catch (cause) { categoryError.value = authError(cause) }
}
onMounted(loadCategories)
watch([search, category, published], () => { offset.value = 0 })
function edit(tool: AdminTool | null) { selected.value = tool; editing.value = true; notice.value = '' }
async function saved() { editing.value = false; notice.value = t('工具已保存。'); await refresh() }
const names = computed(() => Object.fromEntries(categories.value.map(item => [item.slug, item.name])))
</script>

<template>
  <div>
    <div class="admin-page-heading"><div><h1>{{ $t('工具管理') }}</h1><p>{{ $t('管理工具内容、展示顺序和上架状态。') }}</p></div><button class="button primary" :disabled="!categories.length" @click="edit(null)"><AppIcon name="plus" :size="18" />{{ $t('新增工具') }}</button></div>
    <form class="admin-toolbar" role="search" @submit.prevent="search = draft.trim(); offset = 0">
      <label class="admin-search"><AppIcon name="search" :size="18" /><input v-model="draft" :aria-label="$t('搜索工具名称')" :placeholder="$t('搜索工具名称')" maxlength="100"><button class="icon-button" type="submit" :title="$t('搜索')" :aria-label="$t('搜索')"><AppIcon name="arrow" :size="18" /></button></label>
      <select v-model="category" :aria-label="$t('分类筛选')"><option value="">{{ $t('全部分类') }}</option><option v-for="item in categories" :key="item.slug" :value="item.slug">{{ item.name }}</option></select>
      <select v-model="published" :aria-label="$t('上架筛选')"><option value="">{{ $t('全部状态') }}</option><option value="true">{{ $t('已上架') }}</option><option value="false">{{ $t('已下架') }}</option></select>
      <button class="icon-button" type="button" :disabled="pending" :title="$t('刷新')" :aria-label="$t('刷新')" @click="refresh(); loadCategories()"><AppIcon name="refresh" :size="18" /></button>
    </form>
    <p v-if="notice" role="status" class="admin-notice">{{ notice }}</p>
    <p v-if="categoryError" role="alert" class="form-error">{{ categoryError }} <button class="text-button" @click="loadCategories">{{ $t('重试分类') }}</button></p>
    <AsyncState v-if="error" kind="error" :description="error" @retry="refresh" />
    <AsyncState v-else-if="pending" kind="loading" />
    <AsyncState v-else-if="!result.items.length" kind="empty" :title="$t('没有找到工具')" :description="$t('调整筛选条件，或新增一个工具。')" />
    <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th scope="col">{{ $t('工具') }}</th><th scope="col">{{ $t('分类') }}</th><th scope="col">{{ $t('使用状态') }}</th><th scope="col">{{ $t('展示') }}</th><th scope="col">{{ $t('排序') }}</th><th scope="col">{{ $t('操作') }}</th></tr></thead><tbody>
      <tr v-for="tool in result.items" :key="tool.slug"><td><div class="admin-name-cell"><span class="tool-icon" :class="`tone-${tool.color}`"><AppIcon :name="tool.icon" :size="22" /></span><div><strong>{{ tool.name }}</strong><small>{{ tool.slug }}</small></div></div></td><td>{{ names[tool.category] || tool.category }}</td><td><span class="admin-state" :class="{ enabled: tool.status === 'available' }">{{ tool.status === 'available' ? $t('可使用') : $t('开发中') }}</span><small>{{ tool.kind === 'external' ? $t('站外工具') : $t('本站工具') }}</small></td><td><span class="admin-state" :class="{ enabled: tool.published }">{{ tool.published ? $t('已上架') : $t('已下架') }}</span><small v-if="tool.featured">{{ $t('首页精选') }}</small></td><td>{{ tool.sort_order }}</td><td><div class="admin-row-actions"><NuxtLink :to="`/tools/${tool.slug}`" class="icon-button" :aria-label="$t('预览 {value0}', { value0: tool.name })" :title="$t('预览')" target="_blank" v-if="tool.published"><AppIcon name="external" :size="17" /></NuxtLink><button class="icon-button" :disabled="!categories.length" :aria-label="$t('编辑 {value0}', { value0: tool.name })" :title="$t('编辑工具')" @click="edit(tool)"><AppIcon name="pen" :size="17" /></button></div></td></tr>
    </tbody></table></div>
    <AdminPagination :total="result.total" :offset="offset" :limit="limit" :busy="pending" @change="offset = $event" />
    <AdminToolEditor v-if="editing" :tool="selected" :categories="categories" @close="editing = false" @saved="saved" />
  </div>
</template>
