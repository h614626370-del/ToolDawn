<script setup lang="ts">
const props = withDefaults(defineProps<{ src?: string | null; name?: string; size?: number }>(), { name: '', size: 32 })
const failed = ref(false)
watch(() => props.src, () => { failed.value = false })
const initials = computed(() => [...(props.name.trim() || 'T')].slice(0, 1).join('').toUpperCase())
</script>
<template><span class="user-avatar" :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${Math.round(size * .36)}px` }" aria-hidden="true"><img v-if="src && !failed" :src="src" alt="" @error="failed = true"><span v-else>{{ initials }}</span></span></template>
<style scoped>
.user-avatar { display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; border-radius:50%; overflow:hidden; background:var(--soft,#e7ebdd); color:var(--accent,#315e50); border:1px solid var(--line,#d3d7c7); font-weight:650; vertical-align:middle; }
.user-avatar img { width:100%; height:100%; object-fit:cover; }
</style>
