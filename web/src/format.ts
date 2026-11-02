const ordinary = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 })
const scientific = new Intl.NumberFormat('tr-TR', { notation: 'scientific', maximumFractionDigits: 3 })
export function formatNumber(value: number): string {
  const magnitude = Math.abs(value)
  return magnitude >= 1e9 || magnitude > 0 && magnitude < .001 ? scientific.format(value) : ordinary.format(value)
}
