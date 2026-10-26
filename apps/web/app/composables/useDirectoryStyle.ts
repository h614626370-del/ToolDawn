import { directoryStyles, validDirectoryStyle, type DirectoryStyleId } from '~/utils/directoryStyles'

export function useDirectoryStyle() {
  const preference = useCookie<string>('tooldawn-directory-style-v2', { sameSite: 'lax', maxAge: 31536000, path: '/' })
  const selected = useState<DirectoryStyleId>('directory-style-v2', () => validDirectoryStyle(preference.value) ? preference.value : 'cream')
  const style = computed(() => directoryStyles.find(item => item.id === selected.value) || directoryStyles[0])

  function select(value: string) {
    if (!validDirectoryStyle(value)) return
    selected.value = value
    preference.value = value
  }
  return { selected, style, select, styles: directoryStyles }
}
