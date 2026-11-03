import { cloneElement, isValidElement, useSyncExternalStore } from 'react'
import type { ReactNode, ReactElement } from 'react'
import { Globe } from 'lucide-react'
import { english, labels } from './messages'
import { getLanguage, setLanguage, subscribe } from './store'
import type { Language } from './store'

export type TranslationKey = keyof typeof english | keyof typeof labels
const entries = Object.entries(english).sort((a, b) => b[0].length - a[0].length)
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
// One pass over source text avoids cascading replacements or translating IDs
// inside other words. API objects, values, identifiers and event handlers are
// never traversed or mutated; only rendered React text and accessible attributes.
const fragments = new RegExp(entries.map(([key]) => `${/^[\p{L}\p{N}_]/u.test(key) ? '(?<![\\p{L}\\p{N}_])' : ''}${escape(key)}${/[\p{L}\p{N}_]$/u.test(key) ? '(?![\\p{L}\\p{N}_])' : ''}`).join('|'), 'gu')

export function text(source: string, language: Language = getLanguage()): string {
  const trimmed = source.trim()
  if (!trimmed) return source
  const pair = Object.hasOwn(labels, trimmed) ? labels[trimmed as keyof typeof labels] : undefined
  if (pair) return source.replace(trimmed, pair[language])
  if (/^(app|risk|policy|ui)\./.test(trimmed) && !Object.hasOwn(english, trimmed)) return language === 'tr' ? 'Metin kullanılamıyor.' : 'Text unavailable.'
  if (language === 'tr') return source
  const exact = Object.hasOwn(english, trimmed) ? english[trimmed as keyof typeof english] : undefined
  if (exact) return source.replace(trimmed, exact)
  // Backend rule/explanation templates: translated phrase tokens preserve the
  // exact rule IDs, numerical strengths and source feature identifiers.
  const translated = source.replace(fragments, key => english[key as keyof typeof english])
  // Only this known backend template contains Turkish fixed-decimal numbers.
  // Do not touch already localized numbers such as English "2,830,743".
  return /^(Düşük|Orta|Yüksek|Kritik) risk:/.test(trimmed) ? translated.replace(/(\d),(\d)/g, '$1.$2') : translated
}
export function t(key: TranslationKey): string { return text(key) }
export function fallback(key: string, source?: string): string {
  return Object.hasOwn(english, key) || Object.hasOwn(labels, key) ? text(key) : source ? text(source) : /^(app|risk|policy|ui)\./.test(key) ? text('Metin kullanılamıyor.') : key
}

const visibleAttributes = ['title', 'aria-label', 'aria-description', 'placeholder', 'alt']
export function localizeTree(node: ReactNode, language: Language): ReactNode {
  if (typeof node === 'string') return text(node, language)
  if (Array.isArray(node)) return node.map(child => localizeTree(child, language))
  if (!isValidElement(node)) return node
  const element = node as ReactElement<Record<string, unknown>>
  if (element.props['data-i18n-skip']) return node
  const props: Record<string, unknown> = {}
  for (const attr of visibleAttributes) if (typeof element.props[attr] === 'string') props[attr] = text(element.props[attr] as string, language)
  // An option without explicit value inherits its display text in HTML. Pin its
  // ORIGINAL value so a translated policy label cannot change API requests.
  if (element.type === 'option' && element.props.value === undefined && typeof element.props.children === 'string') props.value = element.props.children
  if ('children' in element.props) props.children = localizeTree(element.props.children as ReactNode, language)
  return cloneElement(element, props)
}
export function useI18n() {
  const language = useSyncExternalStore(subscribe, getLanguage, () => 'tr' as const)
  return { language, setLanguage, t, text: (source: string) => text(source, language), localize: (node: ReactNode) => localizeTree(node, language) }
}
export function LanguageSwitcher() {
  const { language } = useI18n()
  return <button type="button" className="language-switcher" data-i18n-skip aria-label={t(language === 'tr' ? 'ui.switchToEnglish' : 'ui.switchToTurkish')} onClick={() => setLanguage(language === 'tr' ? 'en' : 'tr')}><Globe size={18} aria-hidden="true" /><span>{language === 'tr' ? 'English' : 'Türkçe'}</span></button>
}
