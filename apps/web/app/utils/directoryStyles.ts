import type { Tool } from '~/types/catalog'

export const directoryStyles = [
  { id: 'cream', name: '奶油', description: '默认主题 · 温暖纯色，轻松专注', preview: '', color: '#b45639', slides: ['text-polish', 'birthday-message', 'copy-rewrite'] },
  { id: 'midnight', name: '远山夜色', description: '全屏背景 · 层叠远山与深蓝夜空', preview: '/images/wallpapers/mountains-small.webp', color: '#dcb879', slides: ['text-polish', 'birthday-message', 'copy-rewrite'] },
  { id: 'olive', name: '林间光影', description: '全屏背景 · 日光穿过枝叶，舒展安静', preview: '/images/wallpapers/forest-small.webp', color: '#536341', slides: ['text-polish', 'birthday-message', 'copy-rewrite'] },
  { id: 'plum', name: '暮色微光', description: '全屏背景 · 落日、湖面与柔和暮色', preview: '/images/wallpapers/dusk-small.webp', color: '#eab4aa', slides: ['text-polish', 'birthday-message', 'copy-rewrite'] },
  { id: 'library', name: '晴空海岸', description: '全屏背景 · 白色崖岸与碧蓝海面', preview: '/images/wallpapers/coast-small.webp', color: '#216a7a', slides: ['text-polish', 'birthday-message', 'copy-rewrite'] },
] as const

export type DirectoryStyleId = typeof directoryStyles[number]['id']
export function validDirectoryStyle(value: unknown): value is DirectoryStyleId {
  return directoryStyles.some(style => style.id === value)
}

const previews: Record<string, string> = {
  'photo-restyle': 'photo-restyle', 'background-removal': 'background-removal',
  'image-compress': 'image-compress', 'format-convert': 'format-convert',
  'food-analysis': 'food-analysis', 'text-polish': 'text-polish',
  'copy-rewrite': 'copy-rewrite', 'text-summary': 'text-summary',
  'email-writer': 'email-assistant', 'text-translate': 'natural-translate',
  'birthday-message': 'birthday-message',
}
export function toolArtwork(tool: Tool) {
  // Keep custom catalogue artwork, replacing only the original generic seed photos.
  if (tool.image && !['/images/mountain.jpg', '/images/product.jpg', '/images/food.jpg'].includes(tool.image)) return tool.image
  if (previews[tool.slug]) return `/images/directory/${previews[tool.slug]}.webp`
  return tool.image || `/images/directory/${tool.category === 'image' ? 'format-convert' : tool.category === 'life' ? 'birthday-message' : 'text-summary'}.webp`
}

export const featureHeadlines: Record<string, string> = {
  'email-writer': '把要说的话，写得恰到好处。',
  'text-polish': '让每一句话，都更接近你的想法。',
  'text-summary': '读得更少，抓住更多重点。',
  'birthday-message': '特别的日子，留一句真心话。',
  'copy-rewrite': '同一个想法，换一种好表达。',
  'text-translate': '让表达，自然跨越语言。',
}
