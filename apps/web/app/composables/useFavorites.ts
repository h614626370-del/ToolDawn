const LEGACY_KEY = 'tooldawn:favorites:v1'
const MIGRATED_OWNER = 'tooldawn:favorites:legacy-owner'
const storageKey = (owner: string) => `tooldawn:favorites:v2:${owner}`

function parseFavorites(raw: string | null): string[] {
  const stored: unknown = JSON.parse(raw || '[]')
  return Array.isArray(stored) ? [...new Set(stored.filter((value): value is string => typeof value === 'string'))] : []
}

export function useFavorites() {
  const auth = useAuth()
  const route = useRoute()
  const slugs = useState<string[]>('favorite-slugs', () => [])
  const ready = useState('favorites-ready', () => false)
  const storageAvailable = useState('favorites-storage', () => true)
  const loadedOwner = useState<string | null>('favorites-owner', () => null)

  function load() {
    if (import.meta.server || !auth.loaded.value) return
    const owner = auth.user.value?.id || ''
    if (loadedOwner.value === owner && ready.value) return
    slugs.value = []; ready.value = false; storageAvailable.value = true
    loadedOwner.value = owner
    if (owner) {
      try {
        const existing = localStorage.getItem(storageKey(owner))
        // Adopt the old browser collection once, never into a second account.
        if (existing === null && !localStorage.getItem(MIGRATED_OWNER)) {
          const legacy = parseFavorites(localStorage.getItem(LEGACY_KEY))
          localStorage.setItem(MIGRATED_OWNER, owner)
          localStorage.setItem(storageKey(owner), JSON.stringify(legacy))
          slugs.value = legacy
        } else slugs.value = parseFavorites(existing)
      } catch { storageAvailable.value = false }
    }
    ready.value = true
  }
  watch(() => [auth.loaded.value, auth.user.value?.id], load, { flush: 'sync' })
  onMounted(load)

  async function toggle(slug: string) {
    if (!auth.loaded.value) {
      try { await auth.refresh(5000) } catch { return }
    }
    if (!auth.user.value) {
      await navigateTo({ path: '/login', query: { next: route.fullPath } })
      return
    }
    load()
    const owner = auth.user.value.id
    slugs.value = slugs.value.includes(slug) ? slugs.value.filter(item => item !== slug) : [...slugs.value, slug]
    try {
      localStorage.setItem(storageKey(owner), JSON.stringify(slugs.value))
      storageAvailable.value = true
    } catch { storageAvailable.value = false }
  }

  return { slugs, ready, storageAvailable, toggle }
}
