<script setup lang="ts">
const { data: site } = await useSiteSettings()
</script>
<template>
  <footer class="site-footer">
    <div class="container footer-inner">
    <NuxtLink to="/" class="footer-brand"><SiteLogo :variant="site.site_logo" :size="32" />{{ site.site_name }}</NuxtLink>
    <span class="footer-note">{{ $t('让好工具，遇见需要它的人。') }}</span>
    <nav :aria-label="$t('页脚导航')">
      <a v-if="site.contact_email" :href="`mailto:${site.contact_email}`">{{ $t('联系我们') }}</a>
      <NuxtLink to="/about">{{ $t('关于') }}</NuxtLink>
      <NuxtLink to="/privacy">{{ $t('隐私说明') }}</NuxtLink>
    </nav>
    </div>
  </footer>
</template>
