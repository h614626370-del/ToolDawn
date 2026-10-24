import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  compatibilityDate: '2026-10-24',
  devtools: { enabled: false },
  modules: ['@nuxtjs/i18n'],
  i18n: {
    strategy: 'no_prefix',
    defaultLocale: 'zh',
    locales: [
      { code: 'zh', language: 'zh-CN', name: '简体中文', file: 'zh.ts' },
      { code: 'en', language: 'en', name: 'English', file: 'en.ts' },
    ],
    detectBrowserLanguage: false,
    vueI18n: './i18n.config.ts',
  },
  components: [{ path: '~/components', pathPrefix: false }],
  css: ['~/assets/css/main.css', '~/assets/css/auth.css', '~/assets/css/admin.css', '~/assets/css/billing.css', '~/assets/css/workspace.css', '~/assets/css/operations.css', '~/assets/css/directory-styles.css', '~/assets/css/admin-themes.css'],
  vite: { plugins: [tailwindcss()] },
  runtimeConfig: {
    apiBase: 'http://127.0.0.1:8000',
  },
  typescript: { strict: true },
  routeRules: {
    '/admin': { ssr: false, headers: { 'cache-control': 'no-store' } },
    '/admin/**': { ssr: false, headers: { 'cache-control': 'no-store' } },
    '/account/**': { headers: { 'cache-control': 'no-store' } },
    '/login': { headers: { 'cache-control': 'no-store' } },
    '/forgot-password': { headers: { 'cache-control': 'no-store' } },
  },
  app: {
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      title: 'ToolDawn · 发现好工具',
      meta: [{ name: 'theme-color', content: '#252b2d' }],
      link: [
        { rel: 'preload', href: '/fonts/tooldawn-sans-sc.woff2', as: 'font', type: 'font/woff2', crossorigin: 'anonymous' },
      ],
    },
  },
})
