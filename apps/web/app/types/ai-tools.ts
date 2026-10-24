export interface TextToolConfig {
  slug: string
  name: string
  summary: string
  input_label: string
  placeholder: string
  sample_zh: string
  sample_en: string
  styles: string[]
  enabled: boolean
  cost: number
  max_length: number
}

export interface TextRun {
  id: string
  request_key: string
  tool_slug: string
  status: 'running' | 'succeeded' | 'failed'
  output: string | null
  cost: number
  language: string
  error: string | null
  created_at: string
}
