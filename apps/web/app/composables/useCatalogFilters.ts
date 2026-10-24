export function useCatalogFilters() {
  const route = useRoute()
  const router = useRouter()
  const query = computed(() => typeof route.query.q === 'string' ? route.query.q : '')
  const category = computed(() => typeof route.query.category === 'string' ? route.query.category : '')
  const sort = computed(() => route.query.sort === 'recent' ? 'recent' : 'recommended')
  const favoritesOnly = computed(() => route.query.saved === '1')
  const active = computed(() => !!query.value || !!category.value || favoritesOnly.value)

  function update(values: Record<string, string | undefined>) {
    return router.push({ path: route.path, query: { ...route.query, ...values } })
  }

  return {
    query, category, sort, favoritesOnly, active, update,
    clear: () => router.push({ path: route.path }),
  }
}
