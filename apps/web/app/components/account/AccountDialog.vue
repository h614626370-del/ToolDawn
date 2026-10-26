<script setup lang="ts">
defineProps<{ title: string; busy?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const titleId = useId()
let previous: HTMLElement | null = null
onMounted(() => { previous = document.activeElement as HTMLElement; dialog.value?.showModal() })
onBeforeUnmount(() => { dialog.value?.close(); previous?.focus() })
</script>
<template><dialog ref="dialog" class="account-dialog" :aria-labelledby="titleId" @cancel.prevent="!busy && emit('close')"><header><h2 :id="titleId">{{ title }}</h2><button class="icon-button" :disabled="busy" :aria-label="$t('关闭')" @click="emit('close')"><AppIcon name="close" :size="20" /></button></header><slot /></dialog></template>
