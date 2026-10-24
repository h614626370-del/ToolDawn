import en from './en'

export default Object.fromEntries(Object.keys(en).map(key => [key, key]))
