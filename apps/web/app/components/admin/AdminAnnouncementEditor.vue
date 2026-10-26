<script setup lang="ts">
import type { Announcement, AnnouncementInput } from '~/types/announcements'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ announcement: Announcement | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { t } = useI18n()
const form = reactive<AnnouncementInput>({
  title: props.announcement?.title || '', content: props.announcement?.content || '',
  status: props.announcement?.status || 'draft', notify_mode: props.announcement?.notify_mode || 'silent',
  audience: props.announcement?.audience || 'all', revision: props.announcement?.revision || 1,
  starts_at: props.announcement?.starts_at || null, ends_at: props.announcement?.ends_at || null,
})
function localDate(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
const starts = ref(localDate(form.starts_at))
const ends = ref(localDate(form.ends_at))
const preview = ref(false)
const busy = ref(false)
const error = ref('')
async function save() {
  error.value = ''
  if (!form.title.trim() || !form.content.trim()) { error.value = t('请填写公告标题和正文。'); return }
  const start = starts.value ? new Date(starts.value) : null
  const end = ends.value ? new Date(ends.value) : null
  if ((start && !Number.isFinite(start.getTime())) || (end && !Number.isFinite(end.getTime()))) { error.value = t('请填写有效的展示时间。'); return }
  if (start && end && end <= start) { error.value = t('结束时间必须晚于开始时间。'); return }
  busy.value = true
  try {
    await $fetch(`/api/v1/admin/announcements${props.announcement ? `/${props.announcement.id}` : ''}`, {
      method: props.announcement ? 'PUT' : 'POST',
      body: { ...form, starts_at: start?.toISOString() || null, ends_at: end?.toISOString() || null },
    })
    emit('saved')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <AdminDialog :title="$t(announcement ? '编辑公告' : '新增公告')" :busy="busy" @close="emit('close')">
    <form class="admin-editor" @submit.prevent="save">
      <fieldset class="admin-form-fields" :disabled="busy">
        <label class="admin-field"><span>{{ $t('公告标题') }}</span><input v-model="form.title" required maxlength="200" autofocus :placeholder="$t('例如：本周工具更新')"></label>
        <div class="announcement-editor-tabs"><span>{{ $t('公告正文') }}</span><div role="group" :aria-label="$t('正文编辑方式')"><button type="button" :aria-pressed="!preview" @click="preview = false">{{ $t('编辑') }}</button><button type="button" :aria-pressed="preview" @click="preview = true">{{ $t('预览') }}</button></div></div>
        <label v-show="!preview" class="admin-field"><span class="sr-only">{{ $t('公告正文') }}</span><textarea v-model="form.content" :required="!preview" maxlength="30000" rows="9" :placeholder="$t('写下需要告诉用户的消息…')" /></label>
        <div v-if="preview" class="announcement-preview"><AnnouncementBody v-if="form.content.trim()" :content="form.content" /><p v-else>{{ $t('输入正文后可预览。') }}</p></div>
        <p class="announcement-field-help">{{ $t('支持 Markdown 标题、列表、链接和代码；不支持 HTML 或嵌入图片。') }}</p>
        <div class="announcement-form-grid">
          <label class="admin-field"><span>{{ $t('发布状态') }}</span><select v-model="form.status"><option value="draft">{{ $t('草稿') }}</option><option value="active">{{ $t('已发布') }}</option><option value="archived">{{ $t('已归档') }}</option></select></label>
          <label class="admin-field"><span>{{ $t('提醒方式') }}</span><select v-model="form.notify_mode"><option value="silent">{{ $t('仅铃铛提醒') }}</option><option value="popup">{{ $t('弹窗提醒') }}</option></select></label>
          <label class="admin-field announcement-full-field"><span>{{ $t('可见范围') }}</span><select v-model="form.audience"><option value="all">{{ $t('所有访客') }}</option><option value="members">{{ $t('仅登录用户') }}</option></select></label>
          <label class="admin-field"><span>{{ $t('开始展示时间') }}</span><input v-model="starts" type="datetime-local"><small>{{ $t('留空表示立即展示') }}</small></label>
          <label class="admin-field"><span>{{ $t('结束展示时间') }}</span><input v-model="ends" type="datetime-local"><small>{{ $t('留空表示长期展示') }}</small></label>
        </div>
        <p class="announcement-field-help">{{ $t('时间按当前设备时区填写；只有已发布且在展示时间内的公告对用户可见。') }}</p>
        <p v-if="announcement" class="announcement-field-help">{{ $t('修改后视为新版本，用户需要重新确认已读；归档可停止展示。') }}</p>
      </fieldset>
      <p v-if="error" role="alert" class="form-error">{{ error }}</p>
      <footer class="admin-editor-actions"><button type="button" class="button secondary" :disabled="busy" @click="emit('close')">{{ $t('取消') }}</button><button class="button primary" :disabled="busy"><AppIcon :name="busy ? 'loader' : 'save'" :size="17" />{{ $t(form.status === 'active' ? '保存并发布' : '保存公告') }}</button></footer>
    </form>
  </AdminDialog>
</template>
