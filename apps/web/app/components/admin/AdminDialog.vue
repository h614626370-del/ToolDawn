<script setup lang="ts">
const props = defineProps<{ title: string; busy?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
const previous = ref<HTMLElement | null>(null)
onMounted(() => {
  previous.value = document.activeElement as HTMLElement
  dialog.value?.showModal()
})
onBeforeUnmount(() => { dialog.value?.close(); previous.value?.focus() })
function cancel(event: Event) {
  event.preventDefault()
  if (!props.busy) emit('close')
}
</script>

<template>
  <dialog ref="dialog" class="admin-dialog" aria-labelledby="editor-title" @cancel="cancel">
    <header><h2 id="editor-title">{{ title }}</h2><button class="icon-button" type="button" :disabled="busy" :aria-label="$t('关闭编辑')" :title="$t('关闭')" @click="emit('close')"><AppIcon name="close" /></button></header>
    <slot />
  </dialog>
</template>
