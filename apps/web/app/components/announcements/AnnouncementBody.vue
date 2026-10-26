<script setup lang="ts">
import { renderAnnouncement } from '~/utils/announcementMarkdown'
const props = defineProps<{ content: string }>()
const html = computed(() => renderAnnouncement(props.content))
</script>

<template><div class="announcement-body" v-html="html" /></template>
