export function useDirectoryNavigation() {
  const preference = useCookie<string>('tooldawn-directory-navigation', { sameSite: 'lax', maxAge: 31536000, path: '/' })
  const collapsed = useState('directory-navigation-collapsed', () => preference.value === 'collapsed')

  function toggle() {
    collapsed.value = !collapsed.value
    preference.value = collapsed.value ? 'collapsed' : 'expanded'
  }

  return { collapsed, toggle }
}
