import { afterEach, expect, it, vi } from 'vitest'

afterEach(() => { localStorage.clear(); vi.resetModules() })
it('restores English on a fresh module load and defaults to Turkish without a preference', async () => {
  localStorage.setItem('fuzzy-network-risk.language', 'en')
  vi.resetModules()
  const restored = await import('./store')
  expect(restored.getLanguage()).toBe('en')
  expect(document.documentElement.lang).toBe('en')
  localStorage.clear(); vi.resetModules()
  const initial = await import('./store')
  expect(initial.getLanguage()).toBe('tr')
  expect(document.documentElement.lang).toBe('tr')
})
