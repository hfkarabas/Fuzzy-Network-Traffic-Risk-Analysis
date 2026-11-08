export const LOCALE = 'en-US'
const ordinary = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 2 })
const scientific = new Intl.NumberFormat(LOCALE, { notation: 'scientific', maximumFractionDigits: 3 })
export function formatFixed(value: number, digits: number): string {
  return value.toFixed(digits)
}
export function formatNumber(value: number): string {
  const magnitude = Math.abs(value)
  return magnitude >= 1e9 || magnitude > 0 && magnitude < .001 ? scientific.format(value) : ordinary.format(value)
}
