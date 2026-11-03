import { getLanguage, locale } from './i18n/store'
export { locale }
const formats = {
  tr: [new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 }), new Intl.NumberFormat('tr-TR', { notation: 'scientific', maximumFractionDigits: 3 })],
  en: [new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }), new Intl.NumberFormat('en-US', { notation: 'scientific', maximumFractionDigits: 3 })],
}
export function formatFixed(value: number, digits: number): string {
  return value.toFixed(digits).replace('.', getLanguage() === 'tr' ? ',' : '.')
}
export function formatNumber(value: number): string {
  const [ordinary, scientific] = formats[getLanguage()]
  const magnitude = Math.abs(value)
  return magnitude >= 1e9 || magnitude > 0 && magnitude < .001 ? scientific.format(value) : ordinary.format(value)
}
