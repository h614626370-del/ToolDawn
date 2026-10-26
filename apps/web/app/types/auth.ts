export interface AuthUser {
  id: string
  email: string
  role: 'user' | 'admin'
  created_at: string
  display_name: string
  avatar_url?: string | null
  is_superadmin: boolean
  must_change_password: boolean
  has_password: boolean
}

export interface EmailChallenge {
  challenge_id: string
  expires_in: number
  resend_after: number
}
