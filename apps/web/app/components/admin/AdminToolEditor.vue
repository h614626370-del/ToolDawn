<script setup lang="ts">
import type { AdminCategory, AdminTool, ToolInput } from '~/types/admin'
import { authError } from '~/composables/useAuth'
const props = defineProps<{ tool: AdminTool | null; categories: AdminCategory[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { updated_at: _updated, ...existing } = props.tool || {} as AdminTool
const form = reactive<ToolInput>(props.tool ? {
  ...existing as ToolInput,
  keywords: [...props.tool.keywords],
  features: [...props.tool.features],
} : {
  slug: '', name: '', summary: '', description: '', category: props.categories[0]?.slug || '',
  icon: 'wrench', color: 'blue', kind: 'external', status: 'available',
  external_url: null, image: null, featured: false, published: false,
  keywords: [], features: [], sort_order: 100, revision: 1,
})
const keywords = ref(form.keywords.join('\n'))
const features = ref(form.features.join('\n'))
const busy = ref(false)
const error = ref('')
watch(() => form.kind, kind => {
  if (kind === 'internal') { form.external_url = null; form.status = 'coming_soon' }
})
async function save() {
  busy.value = true
  error.value = ''
  try {
    await $fetch(`/api/v1/admin/tools${props.tool ? `/${props.tool.slug}` : ''}`, {
      method: props.tool ? 'PUT' : 'POST',
      body: {
        ...form, external_url: form.external_url || null, image: form.image || null,
        keywords: keywords.value.split('\n').map(s => s.trim()).filter(Boolean),
        features: features.value.split('\n').map(s => s.trim()).filter(Boolean),
      },
    })
    emit('saved')
  } catch (cause) { error.value = authError(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <AdminDialog :title="tool ? $t('编辑工具') : $t('新增工具')" :busy="busy" @close="emit('close')">
    <form class="admin-editor" @submit.prevent="save">
      <fieldset :disabled="busy" class="admin-form-fields">
        <div class="admin-form-grid">
          <label class="admin-field"><span>{{ $t('工具名称') }}</span><input v-model="form.name" required maxlength="100" autofocus></label>
          <label class="admin-field"><span>{{ $t('唯一标识') }}</span><input v-model="form.slug" required maxlength="80" pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="my-tool" :readonly="!!tool" :title="$t('小写字母、数字和连字符')"></label>
        </div>
        <label class="admin-field"><span>{{ $t('简介') }}</span><input v-model="form.summary" required maxlength="300"></label>
        <label class="admin-field"><span>{{ $t('详细介绍') }}</span><textarea v-model="form.description" required maxlength="10000" rows="3" /></label>
        <div class="admin-form-grid">
          <label class="admin-field"><span>{{ $t('分类') }}</span><select v-model="form.category" required><option v-for="item in categories" :key="item.slug" :value="item.slug">{{ item.name }}</option></select></label>
          <label class="admin-field"><span>{{ $t('排序值') }}</span><input v-model.number="form.sort_order" type="number" min="0" max="100000" required></label>
          <label class="admin-field"><span>{{ $t('工具类型') }}</span><select v-model="form.kind"><option value="external">{{ $t('站外工具') }}</option><option value="internal">{{ $t('本站工具') }}</option></select></label>
          <label class="admin-field"><span>{{ $t('使用状态') }}</span><select v-model="form.status" :disabled="form.kind === 'internal'"><option value="available">{{ $t('可使用') }}</option><option value="coming_soon">{{ $t('开发中') }}</option></select></label>
        </div>
        <label v-if="form.kind === 'external'" class="admin-field"><span>{{ $t('站外地址') }}</span><input v-model="form.external_url" type="url" pattern="https://.*" required placeholder="https://example.com"></label>
        <AdminAppearance v-model:icon="form.icon" v-model:color="form.color" />
        <label class="admin-field"><span>{{ $t('预览图片') }}</span><select v-model="form.image"><option :value="null">{{ $t('不使用图片') }}</option><option value="/images/mountain.jpg">{{ $t('山景') }}</option><option value="/images/product.jpg">{{ $t('运动鞋') }}</option><option value="/images/food.jpg">{{ $t('餐食') }}</option><option v-if="form.image && !['/images/mountain.jpg', '/images/product.jpg', '/images/food.jpg'].includes(form.image)" :value="form.image">{{ form.image }}</option></select></label>
        <div class="admin-form-grid">
          <label class="admin-field"><span>{{ $t('搜索关键词（每行一个）') }}</span><textarea v-model="keywords" rows="3" /></label>
          <label class="admin-field"><span>{{ $t('功能说明（每行一个）') }}</span><textarea v-model="features" rows="3" /></label>
        </div>
        <div class="admin-checks"><label><input v-model="form.published" type="checkbox">{{ $t('上架') }}</label><label><input v-model="form.featured" type="checkbox">{{ $t('首页精选') }}</label></div>
      </fieldset>
      <p v-if="error" role="alert" class="form-error">{{ error }}</p>
      <footer class="admin-editor-actions"><button type="button" class="button secondary" :disabled="busy" @click="emit('close')">{{ $t('取消') }}</button><button class="button primary" :disabled="busy"><AppIcon :name="busy ? 'loader' : 'save'" :class="{ spin: busy }" :size="17" />{{ busy ? $t('保存中') : $t('保存工具') }}</button></footer>
    </form>
  </AdminDialog>
</template>
