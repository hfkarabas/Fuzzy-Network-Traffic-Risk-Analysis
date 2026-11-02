import { expect, it } from 'vitest'
import { formatNumber } from './format'
it('keeps ordinary values readable and extreme finite values compact', () => {
  expect(formatNumber(2830743)).toBe('2.830.743')
  expect(formatNumber(53.274634837391)).toBe('53,27')
  expect(formatNumber(1e308)).toContain('E308')
  expect(formatNumber(1e308).length).toBeLessThan(20)
  expect(formatNumber(.00000001).length).toBeLessThan(20)
})
