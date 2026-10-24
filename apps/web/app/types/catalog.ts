export interface Category {
  slug: string
  name: string
  icon: string
  color: string
  tool_count: number
}

export interface Tool {
  slug: string
  name: string
  summary: string
  description: string
  category: string
  icon: string
  color: string
  kind: 'internal' | 'external'
  status: 'available' | 'coming_soon'
  external_url: string | null
  image: string | null
  featured: boolean
  keywords: string[]
  features: string[]
  updated_at: string
  sort_order: number
}

export interface ToolPage {
  items: Tool[]
  total: number
  next_cursor: number | null
}
