<script setup lang="ts">
import type { AdminCategory, CategoryInput } from '~/types/admin'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ category: AdminCategory | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const form = reactive<CategoryInput>({
  slug: props.category?.slug || '', name: props.category?.name || '',
  icon: props.category?.icon || 'grid', color: props.category?.color || 'green',
  sort_order: props.category?.sort_order || 0, revision: props.category?.revision || 1,
})
const busy = ref(false)
const error = ref('')
async function save() {
  busy.value = true
  error.value = ''
  try {
    await $fetch(`/api/v1/admin/categories${props.category ? `/${props.category.slug}` : ''}`, {
      method: props.category ? 'PUT' : 'POST', body: form,
    })
    emit('saved')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <AdminDialog :title="category ? $t('编辑分类') : $t('新增分类')" :busy="busy" @close="emit('close')">
    <form class="admin-editor" @submit.prevent="save">
      <fieldset class="admin-form-fields" :disabled="busy">
        <label class="admin-field"><span>{{ $t('分类名称') }}</span><input v-model="form.name" required maxlength="100" autofocus></label>
        <label class="admin-field"><span>{{ $t('唯一标识') }}</span><input v-model="form.slug" required maxlength="80" pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="my-category" :readonly="!!category" :title="$t('小写字母、数字和连字符')"></label>
        <AdminAppearance v-model:icon="form.icon" v-model:color="form.color" />
        <label class="admin-field"><span>{{ $t('排序值') }}</span><input v-model.number="form.sort_order" type="number" min="0" max="100000" required></label>
      </fieldset>
      <p v-if="error" role="alert" class="form-error">{{ error }}</p>
      <footer class="admin-editor-actions"><button type="button" class="button secondary" :disabled="busy" @click="emit('close')">{{ $t('取消') }}</button><button class="button primary" :disabled="busy"><AppIcon :name="busy ? 'loader' : 'save'" :class="{ spin: busy }" :size="17" />{{ $t('保存分类') }}</button></footer>
    </form>
  </AdminDialog>
</template>
