import { expect, it } from 'vitest'
import { validateAnalysis } from './api'
import type { Analysis } from './types'
import fixture from './test-fixture.json'
it('validates actual Python responses and rejects nonfinite memberships', () => {
  const actual = fixture.analyses['policy-contrast'].Balanced as Analysis
  expect(validateAnalysis(actual)).toBe(actual)
  const bad = structuredClone(actual); bad.membership_degrees[' Flow Packets/s'].sparse = Infinity
  expect(() => validateAnalysis(bad)).toThrow('Üyelik dereceleri geçersiz')
})
it('rejects unavailable results containing a numerical score', () => {
  const bad = { ...fixture.analyses['policy-contrast'].Balanced, status: 'invalid_input' } as Analysis
  expect(() => validateAnalysis(bad)).toThrow('Geçersiz girdi için sayısal sonuç')
})
