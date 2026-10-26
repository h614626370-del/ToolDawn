import type { Tool } from './catalog'
import type { AuthUser } from './auth'

import type { ModelCapability } from './model-groups'

export interface AdminTool extends Tool { model_group_id: string | null; model_capability: ModelCapability | null; published: boolean; revision: number }
export type ToolInput = Omit<AdminTool, 'updated_at'>
export interface AdminCategory {
  slug: string
  name: string
  icon: string
  color: string
  sort_order: number
  revision: number
  tool_count: number
}
export type CategoryInput = Omit<AdminCategory, 'tool_count'>
export interface AdminUser extends AuthUser { disabled: boolean }
export interface AdminPage<T> { items: T[]; total: number }
