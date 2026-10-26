<script setup lang="ts">
import { authError } from '~/composables/useAuth'
import type { AuthUser } from '~/types/auth'
import type { Page, Usage } from '~/types/operations'
import { accountToolNames } from '~/utils/accountTools'
definePageMeta({ middleware:'account', layout:'account' })
const { t, locale } = useI18n()
const auth = useAuth()
const displayName = ref('')
const notice = ref('')
const error = ref('')
const pending = ref(true)
const busy = ref(false)
const wallet = ref<number | null>(null)
const recent = ref<Usage[]>([])
const summaryError = ref('')
useSeoMeta({ title:() => `${t('个人信息')} · ToolDawn`, robots:'noindex, nofollow' })
async function summary() {
  summaryError.value = ''
  try {
    const [balance, usage] = await Promise.all([$fetch<{balance:number}>('/api/v1/billing/wallet'),$fetch<Page<Usage>>('/api/v1/me/usage',{query:{limit:3}})])
    wallet.value = balance.balance; recent.value = usage.items
  } catch (cause) { summaryError.value = authError(cause) }
}
async function load() {
  error.value = ''; pending.value = true
  try { await auth.refresh(5000); displayName.value = auth.user.value?.display_name || ''; await summary() }
  catch (cause) { error.value = authError(cause) }
  finally { pending.value = false }
}
async function save() {
  busy.value = true; error.value = ''; notice.value = ''
  try { auth.user.value = await $fetch<AuthUser>('/api/v1/me/profile',{method:'PATCH',body:{display_name:displayName.value}}); displayName.value = auth.user.value.display_name; notice.value = t('个人信息已保存。') }
  catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <div>
    <AccountHeading title="个人信息" description="管理你的资料，让工具更贴近你的使用习惯。" />
    <AsyncState v-if="pending" kind="loading" :title="$t('正在加载')" />
    <AsyncState v-else-if="!auth.user.value" kind="error" :title="$t('暂时无法加载')" :description="error" @retry="load" />
    <div v-else class="account-profile-grid">
      <div class="account-stack">
        <section class="account-panel"><AvatarEditor /><div class="account-section-title"><h2>{{ $t('基本资料') }}</h2><p>{{ $t('昵称和头像会用于站内个人展示。') }}</p></div>
          <form class="account-profile-form" @submit.prevent="save"><label class="admin-field"><span>{{ $t('昵称') }}</span><input v-model="displayName" maxlength="60" autocomplete="nickname" :disabled="busy"></label>
            <dl class="account-info-list"><div><dt>{{ $t('邮箱地址') }}</dt><dd>{{ auth.user.value.email }}</dd></div><div><dt>{{ $t('账户身份') }}</dt><dd>{{ $t(auth.user.value.is_superadmin ? '超级管理员' : auth.user.value.role === 'admin' ? '管理员' : '普通用户') }}</dd></div><div><dt>{{ $t('加入日期') }}</dt><dd>{{ new Date(auth.user.value.created_at).toLocaleDateString(locale) }}</dd></div></dl>
            <p v-if="notice" role="status" class="account-notice">{{ notice }}</p><p v-if="error" role="alert" class="form-error">{{ error }}</p>
            <button class="button primary" :disabled="busy || displayName === auth.user.value.display_name"><AppIcon name="save" :size="16" />{{ $t(busy ? '正在保存' : '保存更改') }}</button>
          </form>
        </section>
        <section class="account-panel"><div class="account-section-title"><h2>{{ $t('使用偏好') }}</h2><p>{{ $t('在首页、工具工作台与账户中心保持一致。') }}</p></div><div class="account-preference"><div><strong>{{ $t('界面风格') }}</strong><p>{{ $t('选择喜欢的配色，系统会自动记住。') }}</p></div><StyleSwitcher /></div><div class="account-preference"><div><strong>{{ $t('界面语言') }}</strong><p>{{ $t('切换语言不会影响你的资料和作品。') }}</p></div><LanguageSelect /></div></section>
      </div>
      <aside class="account-stack">
        <section class="account-panel account-wallet-preview"><AppIcon name="wallet" :size="22" /><h2>{{ $t('可用积分') }}</h2><strong>{{ wallet === null ? '—' : wallet.toLocaleString() }}</strong><p>{{ $t('用于本站工具，消费与退款均可查询。') }}</p><NuxtLink to="/account/credits" class="button primary">{{ $t('积分与充值') }}<AppIcon name="arrow" :size="16" /></NuxtLink></section>
        <section class="account-panel"><div class="account-section-title"><h2>{{ $t('最近使用') }}</h2></div><p v-if="summaryError" class="form-error" role="alert">{{ summaryError }} <button class="text-button" @click="summary">{{ $t('重试') }}</button></p><p v-else-if="!recent.length" class="muted">{{ $t('从一件想完成的小事开始。') }}</p><NuxtLink v-for="item in recent" :key="item.id" :to="`/tools/${item.tool_slug}`" class="account-recent-item"><AppIcon :name="item.tool_slug === 'image-generate' ? 'image' : 'pen'" :size="18" /><div><strong>{{ $t(accountToolNames[item.tool_slug] || item.tool_slug) }}</strong><small>{{ new Date(item.created_at).toLocaleDateString(locale) }}</small></div><AppIcon name="arrow" :size="16" /></NuxtLink><NuxtLink to="/account/usage" class="account-text-link">{{ $t('查看全部记录') }}<AppIcon name="arrow" :size="14" /></NuxtLink></section>
        <NuxtLink to="/account/security" class="account-security-link"><AppIcon name="shield" :size="22" /><div><strong>{{ $t('账户安全') }}</strong><span>{{ $t('管理密码与登录会话') }}</span></div><AppIcon name="arrow" :size="16" /></NuxtLink>
      </aside>
    </div>
  </div>
</template>
