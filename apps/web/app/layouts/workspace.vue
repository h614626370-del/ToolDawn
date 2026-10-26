<script setup lang="ts">
import '~/features/image-studio/studio.css'
const { data: site } = await useSiteSettings()
const auth = useAuth()
const balance = useState<number | null>('studio-balance', () => null)
const { selected } = useDirectoryStyle()
</script>

<template>
  <div class="studio-shell directory-palette" :data-directory-style="selected">
    <a href="#studio-main" class="skip-link">{{ $t('跳到主要内容') }}</a>
    <header class="studio-header">
      <NuxtLink to="/tools" class="studio-back" :aria-label="$t('返回工具目录')" :title="$t('返回工具目录')"><AppIcon name="back" :size="18" /></NuxtLink>
      <NuxtLink to="/" class="studio-brand" :aria-label="site.site_name"><SiteLogo :variant="site.site_logo" :size="28" /><span>{{ site.site_name }}</span></NuxtLink>
      <span class="studio-header-divider" aria-hidden="true" />
      <span class="studio-product">{{ $t('图像工作台') }}</span>
      <div class="studio-header-actions">
        <NuxtLink v-if="auth.user.value" to="/account/credits" class="studio-credit"><AppIcon name="wallet" :size="16" />{{ balance === null ? '—' : balance.toLocaleString() }}<span>{{ $t('积分') }}</span></NuxtLink>
        <StyleSwitcher />
        <LanguageSelect />
        <NuxtLink :to="auth.user.value ? '/account' : '/login?next=/tools/image-generate'" class="studio-icon" :aria-label="$t(auth.user.value ? '我的账户' : '登录')" :title="$t(auth.user.value ? '我的账户' : '登录')"><UserAvatar v-if="auth.user.value" :src="auth.user.value.avatar_url" :name="auth.user.value.display_name || auth.user.value.email" :size="28" /><AppIcon v-else name="user" :size="18" /></NuxtLink>
      </div>
    </header>
    <main id="studio-main" class="studio-main"><slot /></main>
  </div>
</template>
