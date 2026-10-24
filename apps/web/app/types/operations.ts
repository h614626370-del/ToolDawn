export interface Page<T> { items: T[]; total: number }
export interface ModelAccount {
  id: string; name: string; base_url: string; model: string; enabled: boolean
  key_set: boolean; revision: number; created_at: string; updated_at: string
  last_test_at: string | null; last_test_ok: boolean | null; last_test_ms: number | null
}
export interface ToolOverride { account_id: string | null; cost: number | null; enabled: boolean; instruction: string }
export interface RuntimeConfig {
  revision: number; site_name: string; announcement: string; contact_email: string
  registration_enabled: boolean; ai_enabled: boolean; tickets_enabled: boolean
  ai_tool_cost: number; ai_requests_per_minute: number; default_account_id: string | null
  tool_overrides: Record<string, ToolOverride>
  mail_mode: 'file' | 'smtp'; smtp_host: string | null; smtp_port: number
  smtp_username: string | null; smtp_from: string; smtp_security: 'starttls' | 'tls'
  smtp_password_set: boolean; stripe_secret_key_set: boolean; stripe_webhook_secret_set: boolean
  credit_packages: { id: string; credits: number; unit_amount: number; currency: string }[]
}
export interface Usage {
  id: string; tool_slug: string; status: 'running' | 'succeeded' | 'failed'; cost: number
  charged: number; language: string; model: string | null; duration_ms: number | null
  email: string; account_name: string | null; created_at: string; completed_at: string | null
  error: string | null
}
export interface Ticket {
  id: string; subject: string; category: string; status: string; revision: number
  email: string; user_id: string; created_at: string; updated_at: string
  messages: { id: string; author: string; staff: boolean; body: string; created_at: string }[]
}
export interface Dashboard {
  days: number; users: number; new_users: number; active_sessions: number; open_tickets: number
  runs: number; succeeded: number; failed: number; running: number; credits_used: number
  average_ms: number; revenue: { currency: string; amount: number }[]
  daily: { day: string; total: number; failed: number }[]
}
export interface Monitoring {
  checked_at: string; uptime_seconds: number
  database: { ok: boolean; duration_ms: number }; redis: { ok: boolean; duration_ms: number }
  http: { total: number; server_errors: number; inflight: number; requests_last_minute: number
    p95_ms: number; statuses: Record<string, number> }
}
