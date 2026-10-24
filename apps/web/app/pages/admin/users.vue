<script setup lang="ts">
const { t, locale } = useI18n()
import type { AdminUser } from '~/types/admin'
import { authError } from '~/composables/useAuth'
definePageMeta({ layout: 'admin', middleware: 'admin' })
useSeoMeta({ title: () => t('用户管理 · ToolDawn') })
const draft = ref('')
const search = ref('')
const offset = ref(0)
const limit = 20
const role = ref('')
const state = ref('')
watch([role, state], () => { offset.value = 0 })
const query = computed(() => ({ q: search.value, role: role.value || undefined, disabled: state.value === '' ? undefined : state.value === 'disabled', offset: offset.value, limit }))
const { result, pending, error, refresh } = useAdminList<AdminUser>('users', query)
const selected = ref<AdminUser | null>(null)
const creditUser = ref<AdminUser | null>(null)
const busy = ref(false)
const actionError = ref('')
const notice = ref('')
async function confirm() {
  if (!selected.value) return
  busy.value = true
  actionError.value = ''
  try {
    await $fetch(`/api/v1/admin/users/${selected.value.id}`, { method: 'PATCH', body: { disabled: !selected.value.disabled } })
    notice.value = selected.value.disabled ? t('用户已恢复，需要重新登录。') : t('用户已禁用，现有登录已撤销。')
    selected.value = null
    await refresh()
  } catch (cause) { actionError.value = authError(cause) }
  finally { busy.value = false }
}
function choose(user: AdminUser) { selected.value = user; actionError.value = ''; notice.value = '' }
</script>

<template>
  <div>
    <div class="admin-page-heading"><div><h1>{{ $t('用户管理') }}</h1><p>{{ $t('查看注册用户，管理普通账户的访问权限。') }}</p></div></div>
    <form class="admin-toolbar" role="search" @submit.prevent="search = draft.trim(); offset = 0"><label class="admin-search"><AppIcon name="search" :size="18" /><input v-model="draft" :aria-label="$t('搜索用户邮箱')" :placeholder="$t('搜索用户邮箱')" maxlength="100"><button class="icon-button" :title="$t('搜索')" :aria-label="$t('搜索')"><AppIcon name="arrow" :size="18" /></button></label><select v-model="role" :aria-label="$t('身份')"><option value="">{{ $t('全部身份') }}</option><option value="user">{{ $t('普通用户') }}</option><option value="admin">{{ $t('管理员') }}</option></select><select v-model="state" :aria-label="$t('状态')"><option value="">{{ $t('全部状态') }}</option><option value="active">{{ $t('正常') }}</option><option value="disabled">{{ $t('已禁用') }}</option></select><button class="text-button" type="button" @click="draft = ''; search = ''; role = ''; state = ''; offset = 0">{{ $t('重置筛选') }}</button><button class="icon-button" type="button" :disabled="pending" :title="$t('刷新')" :aria-label="$t('刷新')" @click="refresh"><AppIcon name="refresh" :size="18" /></button></form>
    <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
    <AsyncState v-if="error" kind="error" :title="$t('用户列表加载失败')" :description="error" @retry="refresh" />
    <AsyncState v-else-if="pending" kind="loading" :title="$t('正在加载数据')" />
    <AsyncState v-else-if="!result.items.length" kind="empty" :title="$t('没有找到用户')" :description="$t('尝试使用其他邮箱关键词搜索。')" />
    <div v-else class="admin-table-scroll"><table class="admin-table"><thead><tr><th scope="col">{{ $t('邮箱') }}</th><th scope="col">{{ $t('身份') }}</th><th scope="col">{{ $t('状态') }}</th><th scope="col">{{ $t('加入日期') }}</th><th scope="col">{{ $t('操作') }}</th></tr></thead><tbody><tr v-for="user in result.items" :key="user.id"><td class="admin-email">{{ user.email }}</td><td>{{ user.role === 'admin' ? $t('管理员') : $t('普通用户') }}</td><td><span class="admin-state" :class="{ enabled: !user.disabled }">{{ user.disabled ? $t('已禁用') : $t('正常') }}</span></td><td>{{ new Date(user.created_at).toLocaleDateString(locale === 'en' ? 'en-US' : 'zh-CN') }}</td><td><div class="admin-row-actions"><button class="icon-button" :title="$t('查看用户积分')" :aria-label="$t('查看用户积分')" @click="creditUser = user"><AppIcon name="wallet" :size="18" /></button><button v-if="user.role !== 'admin'" class="text-button" @click="choose(user)"><AppIcon :name="user.disabled ? 'check' : 'ban'" :size="16" />{{ user.disabled ? $t('恢复') : $t('禁用') }}</button><span v-else class="muted">{{ $t('受保护') }}</span></div></td></tr></tbody></table></div>
    <AdminPagination :total="result.total" :offset="offset" :limit="limit" :busy="pending" @change="offset = $event" />
    <AdminCredits v-if="creditUser" :user="creditUser" @close="creditUser = null" />
    <AdminDialog v-if="selected" :title="selected.disabled ? $t('恢复用户') : $t('禁用用户')" :busy="busy" @close="selected = null"><div class="admin-editor"><p class="admin-confirm-email">{{ selected.email }}</p><p class="admin-confirm-description">{{ selected.disabled ? $t('恢复后，用户可以重新获取验证码登录。') : $t('禁用后，该用户将立即退出，且无法获取有效登录会话。') }}</p><p v-if="actionError" role="alert" class="form-error">{{ actionError }}</p><div class="admin-editor-actions"><button class="button secondary" :disabled="busy" @click="selected = null">{{ $t('取消') }}</button><button class="button" :class="selected.disabled ? 'primary' : 'danger'" :disabled="busy" @click="confirm"><AppIcon :name="busy ? 'loader' : selected.disabled ? 'check' : 'ban'" :class="{ spin: busy }" :size="17" />{{ $t('确认') }}{{ selected.disabled ? $t('恢复') : $t('禁用') }}</button></div></div></AdminDialog>
  </div>
</template>
