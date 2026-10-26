<script setup lang="ts">defineProps<{ title: string; description: string }>()</script>
<template><header class="account-heading"><div><p class="account-eyebrow">{{ $t('账户中心') }}</p><h1>{{ $t(title) }}</h1><p>{{ $t(description) }}</p></div><slot /></header></template>
