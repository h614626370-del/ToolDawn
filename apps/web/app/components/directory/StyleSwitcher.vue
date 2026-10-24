<script setup lang="ts">
const { selected, style, styles, select } = useDirectoryStyle()
const popupId = useId()
const popup = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
const open = ref(false)
function choose(value: string) {
  select(value)
  popup.value?.hidePopover()
  trigger.value?.focus()
}
</script>

<template>
  <div class="style-switcher">
    <button ref="trigger" class="style-trigger" :popovertarget="popupId" :aria-expanded="open" :aria-controls="popupId" :aria-label="$t('切换风格')">
      <span class="style-swatch" :style="{ background: style.color }" aria-hidden="true" />
      <span class="style-trigger-label">{{ $t('风格') }}</span><span class="style-trigger-name">{{ $t(style.name) }}</span>
      <AppIcon name="chevron" :size="14" />
    </button>
    <div :id="popupId" ref="popup" popover="auto" class="style-popover" @toggle="open = ($event as ToggleEvent).newState === 'open'">
      <div class="style-popover-heading"><strong>{{ $t('选择你的风格') }}</strong><span>{{ $t('自动记住选择') }}</span></div>
      <div class="style-options" role="group" :aria-label="$t('切换风格')">
        <button v-for="item in styles" :key="item.id" class="style-option" :aria-pressed="selected === item.id" :data-style-option="item.id" @click="choose(item.id)">
          <img :src="`/images/directory/${item.scene}-small.webp`" alt="" width="96" height="54" loading="lazy">
          <span><strong>{{ $t(item.name) }}</strong><small>{{ $t(item.description) }}</small></span>
          <AppIcon v-if="selected === item.id" name="check" :size="18" />
        </button>
      </div>
    </div>
  </div>
</template>
