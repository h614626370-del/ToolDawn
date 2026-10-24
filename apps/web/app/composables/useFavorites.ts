const STORAGE_KEY = 'tooldawn:favorites:v1'

export function useFavorites() {
  const slugs = useState<string[]>('favorite-slugs', () => [])
  const ready = useState('favorites-ready', () => false)
  const storageAvailable = useState('favorites-storage', () => true)

  onMounted(() => {
    if (ready.value) return
    try {
      const stored: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
      slugs.value = Array.isArray(stored)
        ? [...new Set(stored.filter((value): value is string => typeof value === 'string'))]
        : []
    } catch {
      storageAvailable.value = false
    }
    ready.value = true
  })

  function toggle(slug: string) {
    const next = slugs.value.includes(slug)
      ? slugs.value.filter(item => item !== slug)
      : [...slugs.value, slug]
    slugs.value = next
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      storageAvailable.value = true
    } catch {
      storageAvailable.value = false
    }
  }

  return { slugs, ready, storageAvailable, toggle }
}
