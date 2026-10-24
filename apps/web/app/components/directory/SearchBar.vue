<script setup lang="ts">
const props = withDefaults(defineProps<{ modelValue?: string; busy?: boolean }>(), { modelValue: '' })
const emit = defineEmits<{ search: [query: string] }>()
const draft = ref(props.modelValue)
watch(() => props.modelValue, value => { draft.value = value })
</script>

<template>
  <form class="search-bar" role="search" @submit.prevent="emit('search', draft.trim())">
    <AppIcon name="search" :size="21" />
    <input v-model="draft" type="search" maxlength="100" :placeholder="$t('搜索工具名称或用途')" :aria-label="$t('搜索工具名称或用途')">
    <button class="search-submit" type="submit" :aria-busy="busy">{{ $t('搜索') }}<AppIcon name="arrow" :size="18" /></button>
  </form>
</template>
