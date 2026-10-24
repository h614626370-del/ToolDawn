import type { Tool } from './catalog'
import type { AuthUser } from './auth'

export interface AdminTool extends Tool { published: boolean; revision: number }
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
