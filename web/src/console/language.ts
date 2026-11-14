import { createContext, useContext } from 'react'
export type Language = 'en' | 'tr'
export const LanguageContext = createContext<Language>('en')
export const languageKey = 'fuzzy-network-risk.language'
export function initialLanguage(): Language {
  try { return localStorage.getItem(languageKey) === 'tr' ? 'tr' : 'en' } catch { return 'en' }
}
export function useLabels() {
  const language = useContext(LanguageContext)
  const locale = language === 'tr' ? 'tr-TR' : 'en-US'
  const t = (en: string, tr: string) => language === 'tr' ? tr : en
  const n = (value: number, digits = 2) => new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value)
  return { language, locale, t, n }
}
const words: Record<string, string> = {
  Low: 'Düşük', Medium: 'Orta', High: 'Yüksek', Critical: 'Kritik', Balanced: 'Dengeli', Sensitive: 'Hassas', Conservative: 'Temkinli',
  'Packet rate': 'Paket hızı', 'Forward packet count': 'İleri paket sayısı', 'Mean packet length': 'Ortalama paket uzunluğu',
  'Backward length variability': 'Geri paket boyu değişkenliği', 'Direction balance': 'Yön oranı',
  Sparse: 'Seyrek', Moderate: 'Orta', Intensive: 'Yoğun', Few: 'Az', Many: 'Çok', Small: 'Küçük', Large: 'Büyük',
  Uniform: 'Tekdüze', Variable: 'Değişken', 'Highly variable': 'Çok değişken', 'Forward-dominated': 'İleri ağırlıklı', 'Backward-dominated': 'Geri ağırlıklı',
  'packets/s': 'paket/sn', packets: 'paket', bytes: 'bayt', ratio: 'oran',
}
export function useWord() {
  const { language } = useLabels()
  return (value: string) => language === 'tr' ? words[value] ?? value : value
}
export function useRuleText() {
  const { language } = useLabels()
  const phrases = Object.keys(words).sort((a,b) => b.length - a.length).join('|')
  return (value: string) => language === 'en' ? value : value.replace(new RegExp(`\\b(?:${phrases}|IF|AND|OR|THEN risk is|is)\\b`, 'gi'), part => {
    const exact = { IF: 'EĞER', AND: 'VE', OR: 'VEYA', 'THEN risk is': 'İSE risk', is: '=' }[part]
    return exact ?? Object.entries(words).find(([key]) => key.toLowerCase() === part.toLowerCase())?.[1] ?? part
  })
}
