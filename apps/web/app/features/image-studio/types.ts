import type { TextRun } from '~/types/ai-tools'

export type StudioMode = 'generate' | 'edit'
export type ImageQuality = 'low' | 'medium' | 'high'
export interface StudioConfig {
  enabled: boolean
  edit_enabled: boolean
  cost: number
  costs: Record<ImageQuality, number>
}
export interface ImageRun extends TextRun {
  mode: StudioMode
  size: string
  background: 'auto' | 'transparent'
  quality: ImageQuality
}
export interface ReferenceImage {
  id: string
  width: number
  height: number
  expires_at: string
  preview: string
  name: string
}
