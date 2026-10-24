export default defineI18nConfig(() => ({
  legacy: false,
  fallbackLocale: 'zh',
  missingWarn: false,
  fallbackWarn: false,
  messageResolver: (messages, path) => (messages as Record<string, string>)[path] ?? null,
}))
