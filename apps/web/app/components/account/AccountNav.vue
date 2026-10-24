<script setup lang="ts">
const route = useRoute()
</script>

<template>
  <nav class="account-nav" :aria-label="$t('个人中心')">
    <NuxtLink v-for="item in [{ path: '/account', icon: 'user', name: '个人信息' }, { path: '/account/usage', icon: 'history', name: '使用记录' }, { path: '/account/credits', icon: 'wallet', name: '积分与充值' }, { path: '/account/tickets', icon: 'support', name: '我的工单' }, { path: '/account/security', icon: 'shield', name: '账户安全' }]" :key="item.path" :to="item.path" :class="{ active: route.path === item.path }"><AppIcon :name="item.icon" :size="17" />{{ $t(item.name) }}</NuxtLink>
  </nav>
</template>
