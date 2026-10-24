export type AdminStyle = 'sub2api' | 'vm2api'

export function useAdminStyle() {
  const cookie = useCookie<string>('tooldawn-admin-style', { path: '/', sameSite: 'lax', maxAge: 31536000 })
  const selected = useState<AdminStyle>('admin-style', () => cookie.value === 'vm2api' ? 'vm2api' : 'sub2api')
  function select(value: AdminStyle) {
    selected.value = value
    cookie.value = value
  }
  return { selected, select }
}
