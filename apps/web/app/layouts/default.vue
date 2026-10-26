<script setup lang="ts">
const route = useRoute()
const { selected } = useDirectoryStyle()
const { collapsed } = useDirectoryNavigation()
const directoryPage = computed(() => route.path === '/' || route.path === '/tools' || route.path.startsWith('/tools/'))
</script>

<template>
  <div class="site-shell" :class="{ 'styled-directory-shell': directoryPage, 'directory-palette': directoryPage, 'directory-nav-collapsed': directoryPage && collapsed }" :data-directory-style="directoryPage ? selected : undefined">
    <AppHeader />
    <main id="main-content" class="main-content"><slot /></main>
    <AppFooter />
  </div>
</template>
