export interface Announcement {
  id: string
  title: string
  content: string
  status: 'draft' | 'active' | 'archived'
  notify_mode: 'silent' | 'popup'
  audience: 'all' | 'members'
  starts_at: string | null
  ends_at: string | null
  revision: number
  created_at: string
  updated_at: string
  read_at?: string | null
  read_count?: number
}

export interface AnnouncementPage {
  items: Announcement[]
  total: number
  unread_count: number
  popups: Announcement[]
  guest_versions: Record<string, number>
}

export type AnnouncementInput = Pick<Announcement, 'title' | 'content' | 'status' | 'notify_mode' | 'audience' | 'starts_at' | 'ends_at' | 'revision'>
