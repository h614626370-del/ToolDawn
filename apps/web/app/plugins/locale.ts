export default defineNuxtPlugin({
  name: 'tooldawn-locale',
  dependsOn: ['i18n:plugin:route-locale-detect'],
  async setup(app) {
    const preference = useCookie<string>('tooldawn_locale', { sameSite: 'lax', maxAge: 31536000 })
    await app.$i18n.setLocale(preference.value === 'en' ? 'en' : 'zh')
  },
})
