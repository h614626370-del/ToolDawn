<script setup lang="ts">
import type { Tool } from '~/types/catalog'
import { featureHeadlines } from '~/utils/directoryStyles'
const props = defineProps<{ tools: Tool[] }>()
const { style, selected } = useDirectoryStyle()
const slides = computed(() => {
  const curated = style.value.slides.map(slug => props.tools.find(tool => tool.slug === slug)).filter((tool): tool is Tool => !!tool)
  return curated.length ? curated : props.tools.filter(tool => tool.kind === 'internal').slice(0, 3)
})
const index = ref(0)
const active = computed(() => slides.value[index.value] || slides.value[0])
const paused = ref(false)
const hovering = ref(false)
const hidden = ref(false)
const reduced = ref(false)
const playing = computed(() => !paused.value && !hovering.value && !hidden.value && !reduced.value && slides.value.length > 1)
let timer: ReturnType<typeof setInterval> | undefined
let motion: MediaQueryList | undefined
const checkMotion = () => { reduced.value = motion?.matches || false }
const checkVisibility = () => { hidden.value = document.hidden }
function pauseOnFocus(event: FocusEvent) {
  // The rotation button owns its toggle; do not invert its state before click fires.
  if (!(event.target as HTMLElement).closest('.carousel-pause')) paused.value = true
}
function go(next: number) {
  if (!slides.value.length) return
  index.value = (next + slides.value.length) % slides.value.length
  paused.value = true
}
watch(selected, () => { index.value = 0 })
watch(() => slides.value.length, () => { index.value = 0 })
onMounted(() => {
  motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  checkMotion()
  checkVisibility()
  motion.addEventListener('change', checkMotion)
  document.addEventListener('visibilitychange', checkVisibility)
  timer = setInterval(() => { if (playing.value) index.value = (index.value + 1) % slides.value.length }, 6500)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  motion?.removeEventListener('change', checkMotion)
  document.removeEventListener('visibilitychange', checkVisibility)
})
</script>

<template>
  <section v-if="active" class="feature-carousel" role="region" :aria-label="$t('工具推荐轮播')" aria-roledescription="carousel" @mouseenter="hovering = true" @mouseleave="hovering = false" @focusin="pauseOnFocus" @keydown.left.prevent="go(index - 1)" @keydown.right.prevent="go(index + 1)">
    <img :key="active.slug + '-scene'" class="carousel-scene" :src="`/images/directory/banner-${active.slug}.webp`" alt="" width="1920" height="640" fetchpriority="high">
    <div class="carousel-shade" />
    <div :key="active.slug" class="carousel-slide" role="group" aria-roledescription="slide" :aria-label="`${index + 1} / ${slides.length}`">
      <div class="carousel-copy">
        <span class="carousel-tool-name">{{ $t(active.name) }}<span>{{ active.status === 'available' ? $t('在线使用') : $t('开发中') }}</span></span>
        <h2>{{ $t(featureHeadlines[active.slug] || active.name) }}</h2>
        <p>{{ $t(active.summary) }}</p>
        <NuxtLink :to="`/tools/${active.slug}`" class="carousel-action">{{ active.status === 'available' ? $t('打开工具') : $t('了解工具') }}<AppIcon name="arrow" :size="16" /></NuxtLink>
      </div>
    </div>
    <div v-if="slides.length > 1" class="carousel-controls">
      <button class="carousel-arrow" :aria-label="$t('上一张')" @click="go(index - 1)"><AppIcon name="back" :size="16" /></button>
      <div class="carousel-dots">
        <button v-for="(tool, i) in slides" :key="tool.slug" :aria-label="$t('显示推荐：{name}', { name: $t(tool.name) })" :aria-pressed="index === i" @click="go(i)"><span /></button>
      </div>
      <button class="carousel-arrow" :aria-label="$t('下一张')" @click="go(index + 1)"><AppIcon name="arrow" :size="16" /></button>
      <button v-if="!reduced" class="carousel-pause" :aria-label="paused ? $t('播放轮播') : $t('暂停轮播')" @click="paused = !paused"><span aria-hidden="true">{{ paused ? '▶' : 'Ⅱ' }}</span></button>
      <span class="carousel-counter" aria-hidden="true">{{ String(index + 1).padStart(2, '0') }} / {{ String(slides.length).padStart(2, '0') }}</span>
    </div>
    <p class="sr-only" :aria-live="paused ? 'polite' : 'off'">{{ $t(active.name) }}, {{ index + 1 }} / {{ slides.length }}</p>
  </section>
</template>
