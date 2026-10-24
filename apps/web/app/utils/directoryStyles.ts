import type { Tool } from '~/types/catalog'

export const directoryStyles = [
  { id: 'midnight', name: '午夜暖灯', description: '深蓝与暖金，安静的夜间工作室', scene: 'scene-midnight', color: '#dcb879', slides: ['email-writer', 'text-polish', 'text-summary'] },
  { id: 'cream', name: '奶油拼贴', description: '柔和杏色，错落有致的创意拼贴', scene: 'scene-cream', color: '#b45639', slides: ['text-polish', 'birthday-message', 'copy-rewrite'] },
  { id: 'olive', name: '橄榄工作台', description: '自然日光，按用途展开的工具架', scene: 'scene-olive', color: '#536341', slides: ['text-summary', 'text-polish', 'text-translate'] },
  { id: 'plum', name: '酒红夜色', description: '酒红与玫瑰，温暖的夜色图册', scene: 'scene-plum', color: '#eab4aa', slides: ['birthday-message', 'email-writer', 'copy-rewrite'] },
  { id: 'library', name: '墨绿书房', description: '墨绿与纸白，井然有序的灵感书房', scene: 'scene-library', color: '#c6a452', slides: ['text-translate', 'text-summary', 'email-writer'] },
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
