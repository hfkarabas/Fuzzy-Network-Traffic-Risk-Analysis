export type Language = 'tr' | 'en'
export const LANGUAGE_KEY = 'fuzzy-network-risk.language'
const listeners = new Set<() => void>()
export function readLanguage(): Language {
  try { return typeof localStorage !== 'undefined' && localStorage.getItem(LANGUAGE_KEY) === 'en' ? 'en' : 'tr' }
  catch { return 'tr' }
}
let language: Language = readLanguage()
function documentLanguage() {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = language
    document.title = 'Fuzzy Network Security'
  }
}
documentLanguage()
export const getLanguage = () => language
export const locale = () => language === 'tr' ? 'tr-TR' : 'en-US'
export function setLanguage(next: Language) {
  if (next !== 'tr' && next !== 'en') return
  language = next
  try { localStorage.setItem(LANGUAGE_KEY, next) } catch { /* Storage may be disabled; switching still works. */ }
  documentLanguage()
  listeners.forEach(notify => notify())
}
export function subscribe(notify: () => void) {
  listeners.add(notify)
  return () => { listeners.delete(notify) }
}
