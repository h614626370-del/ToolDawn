export type ModelCapability = 'text' | 'image_generate' | 'image_edit' | 'vision'
export const capabilityLabels: Record<ModelCapability, string> = {
  text: '文字生成', image_generate: '图片生成', image_edit: '图片编辑', vision: '图片理解',
}
export interface ModelGroupOption {
  id: string; name: string; enabled: boolean
}
export interface ModelGroup extends ModelGroupOption {
  description: string; account_ids: string[]; tool_slugs: string[]
  revision: number; created_at: string; updated_at: string
}
