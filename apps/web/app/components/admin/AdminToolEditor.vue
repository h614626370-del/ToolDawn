<script setup lang="ts">
import { capabilityLabels, type ModelGroupOption } from '~/types/model-groups'
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
  model_group_id: null, model_capability: null,
  slug: '', name: '', summary: '', description: '', category: props.categories[0]?.slug || '',
  icon: 'wrench', color: 'blue', kind: 'internal', status: 'coming_soon',
  external_url: null, image: null, featured: false, published: false,
  keywords: [], features: [], sort_order: 100, revision: 1,
})
const groupOptions = ref<ModelGroupOption[]>([])
const textTools = ref<string[]>([])
const groupsLoading = ref(true)
const groupsError = ref('')
async function loadGroups() {
  groupsLoading.value = true; groupsError.value = ''
  try {
    const result = await $fetch<{ items: ModelGroupOption[]; text_tools: string[] }>('/api/v1/admin/model-group-options')
    groupOptions.value = result.items; textTools.value = result.text_tools
    if (textTools.value.includes(form.slug)) form.model_capability = 'text'
    if (form.slug === 'image-generate') form.model_capability = 'image_generate'
  } catch (cause) { groupsError.value = authError(cause) }
  finally { groupsLoading.value = false }
}
onMounted(loadGroups)
const keywords = ref(form.keywords.join('\n'))
const features = ref(form.features.join('\n'))
const busy = ref(false)
const error = ref('')
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
          <label class="admin-field"><span>{{ $t('使用状态') }}</span><select v-model="form.status" :disabled="!tool || tool.status !== 'available'"><option value="available">{{ $t('可使用') }}</option><option value="coming_soon">{{ $t('开发中') }}</option></select></label>
        </div>
        <section class="tool-routing">
          <h3>{{ $t('模型调用分组') }}</h3>
          <p class="muted">{{ $t('绑定后优先使用分组内账号；未绑定时沿用系统默认或单账号配置。') }}</p>
          <p v-if="groupsError" class="form-error" role="alert">{{ groupsError }} <button type="button" class="button secondary" @click="loadGroups">{{ $t('重试') }}</button></p>
          <div class="admin-form-grid">
            <label class="admin-field"><span>{{ $t('所需能力') }}</span><select v-model="form.model_capability" :disabled="groupsLoading || !!groupsError || textTools.includes(form.slug) || form.slug === 'image-generate'"><option :value="null">{{ $t('不使用模型能力') }}</option><option v-for="(label, value) in capabilityLabels" :key="value" :value="value">{{ $t(label) }}</option></select></label>
            <label class="admin-field"><span>{{ $t('账号分组') }}</span><select v-model="form.model_group_id" :disabled="groupsLoading || !!groupsError"><option :value="null">{{ $t('未绑定分组') }}</option><option v-if="form.model_group_id && !groupOptions.some(g => g.id === form.model_group_id)" :value="form.model_group_id">{{ $t('当前绑定分组') }}</option><option v-for="group in groupOptions" :key="group.id" :value="group.id">{{ group.name }}{{ group.enabled ? '' : ` (${$t('已停用')})` }}</option></select></label>
          </div>
          <p v-if="form.status === 'coming_soon'" class="muted">{{ $t('分组配置仅准备调用资源，不会开放尚未实现的工具。') }}</p>
        </section>
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

<style scoped>
.tool-routing { border-block: 1px solid var(--admin-line); padding: 16px 0; }
.tool-routing h3 { margin: 0 0 8px; font-size: 15px; }
.tool-routing p { font-size: 13px; line-height: 1.6; }
</style>
