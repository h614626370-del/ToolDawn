<script setup lang="ts">
const route = useRoute()
const { selected } = useDirectoryStyle()
const directoryPage = computed(() => route.path === '/' || route.path === '/tools')
</script>

<template>
  <div class="site-shell" :class="{ 'styled-directory-shell': directoryPage }" :data-directory-style="directoryPage ? selected : undefined">
    <AppHeader />
    <main id="main-content" class="main-content"><slot /></main>
    <AppFooter />
  </div>
</template>
