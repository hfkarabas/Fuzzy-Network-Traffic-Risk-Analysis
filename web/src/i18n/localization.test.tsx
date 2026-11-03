import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../App'
import fixture from '../test-fixture.json'
import replay from '../live-test-fixture.json'
import plots from '../visualization-test-fixture.json'
import { fallback, localizeTree, text } from './index'
import { getLanguage, LANGUAGE_KEY, readLanguage, setLanguage } from './store'
import { formatFixed, formatNumber } from '../format'
import LiveFlowDetail from '../components/LiveFlowDetail'
import type { LiveFlow } from '../LiveTraffic'
import type { AppData } from '../types'

function installAPI() {
  const mock = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const path = String(url)
    if (path === '/api/analyze') {
      const body = JSON.parse(String(init?.body))
      const historical = Object.values(fixture.analyses).find(p => JSON.stringify(p.Balanced.input_values) === JSON.stringify(body.features))
      if (historical) return new Response(JSON.stringify(historical[body.policy as 'Balanced']))
      const protocol = replay.flows.find(f => JSON.stringify(f.features) === JSON.stringify(body.features))!.protocol.toLowerCase() as 'tcp' | 'udp'
      return new Response(JSON.stringify(plots.liveAnalyses[protocol][body.policy as 'Balanced']))
    }
    if (path === '/api/visualization/output') {
      const body = JSON.parse(String(init?.body))
      const flow = replay.flows.find(f => JSON.stringify(f.features) === JSON.stringify(body.features))
      return new Response(JSON.stringify(flow ? plots[flow.protocol.toLowerCase() as 'tcp' | 'udp'] : plots.historical))
    }
    if (path.startsWith('/api/live/status')) return new Response(JSON.stringify(replay))
    if (path === '/api/live/interfaces') return new Response(JSON.stringify({ interfaces: [], error: { code: 'capture_unavailable', message: 'Npcap kullanılamıyor. Npcap kurulumu ve yakalama izinlerini kontrol edin; çevrimdışı analiz kullanılabilir.' } }))
    return new Response(JSON.stringify(fixture[path.replace('/api/', '') as 'health' | 'model' | 'policies' | 'examples' | 'evaluation']))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}
function untranslated() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const found: string[] = []
  while (walker.nextNode()) {
    const node = walker.currentNode
    if (node.parentElement?.closest('[data-i18n-skip]')) continue
    if (/[çğıöşüÇĞİÖŞÜ]/u.test(node.textContent ?? '')) found.push(node.textContent!.trim())
  }
  for (const element of document.querySelectorAll('[aria-label],[placeholder],[title]')) {
    if (element.closest('[data-i18n-skip]')) continue
    for (const key of ['aria-label', 'placeholder', 'title']) {
      const value = element.getAttribute(key)
      if (value && /[çğıöşüÇĞİÖŞÜ]/u.test(value)) found.push(`${key}: ${value}`)
    }
  }
  return [...new Set(found)].filter(Boolean)
}
beforeEach(() => { localStorage.clear(); act(() => setLanguage('tr')); window.location.hash = '#analysis' })
afterEach(() => { cleanup(); act(() => setLanguage('tr')); localStorage.clear(); vi.unstubAllGlobals() })

it('defaults to Turkish, places a navigation-sized language action at the sidebar footer without an information box and persists selection', async () => {
  const mock = installAPI(); const { unmount } = render(<App />)
  await screen.findByText('Alarm üretildi')
  await screen.findByTestId('output-centroid')
  expect(document.documentElement.lang).toBe('tr')
  const button = screen.getByRole('button', { name: 'İngilizceye geç' })
  expect(button).toHaveTextContent('English')
  expect(button.parentElement).toHaveClass('sidebar-tail')
  expect(document.querySelector('.sidebar-bottom')).toBeNull()
  expect(screen.queryByText('Yerel çalışır. Paket yakalamaz.')).not.toBeInTheDocument()
  const before = mock.mock.calls.filter(([url]) => String(url) === '/api/analyze').length
  const allBefore = mock.mock.calls.length
  fireEvent.click(button)
  expect(document.documentElement.lang).toBe('en')
  expect(screen.getByRole('heading', { name: 'Risk Analysis' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Switch to Turkish' })).toHaveTextContent('Türkçe')
  expect(localStorage.getItem(LANGUAGE_KEY)).toBe('en')
  expect(readLanguage()).toBe('en')
  expect(mock.mock.calls.filter(([url]) => String(url) === '/api/analyze')).toHaveLength(before)
  expect(mock.mock.calls).toHaveLength(allBefore)
  unmount(); render(<App />)
  await screen.findByText('Alert raised')
  expect(screen.getByRole('heading', { name: 'Risk Analysis' })).toBeVisible()
})

it('translates every route, visible backend metadata and accessible labels without reloading', async () => {
  installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
  fireEvent.click(screen.getByRole('button', { name: 'İngilizceye geç' }))
  const routes = [
    ['Security Overview', /^Security Overview$/], ['Recorded Traffic', /^Recorded Traffic$/],
    ['Model Performance', /^Model Performance$/], ['System Information', /^System Information$/],
    ['Live Traffic', /^Live Traffic$/], ['Risk Analysis', /^Risk Analysis$/], ['Dataset Information', /^Dataset Information$/],
  ] as const
  for (const [link, heading] of routes) {
    fireEvent.click(screen.getByRole('link', { name: link }))
    await screen.findByRole('heading', { name: heading })
    await waitFor(() => expect(untranslated()).toEqual([]))
    if (link !== 'Dataset Information') expect(document.body.textContent).not.toMatch(/TASK\s*\d|CIC-IDS2017|FUZZY NETWORK LAB|Eğitim amaçlı|Educational research|Deneysel bir karar|experimental decision/i)
    fireEvent.click(screen.getByRole('button', { name: 'Switch to Turkish' }))
    expect(document.documentElement.lang).toBe('tr')
    fireEvent.click(screen.getByRole('button', { name: 'İngilizceye geç' }))
    expect(document.documentElement.lang).toBe('en')
    expect(screen.getByRole('heading', { name: heading })).toBeVisible()
  }
})

it('localizes memberships, rules, centroid output and live detail while preserving raw policy IDs and score', async () => {
  const mock = installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
  fireEvent.click(screen.getByRole('button', { name: 'İngilizceye geç' }))
  expect(screen.getAllByRole('img', { name: /membership functions from the server/ })).toHaveLength(5)
  await screen.findByRole('img', { name: /Output memberships, aggregate and centroid/ })
  fireEvent.click(screen.getByRole('tab', { name: /Active rules/ }))
  expect(screen.getByRole('tabpanel').textContent).toMatch(/IF .* THEN risk/)
  expect(untranslated()).toEqual([])
  fireEvent.click(screen.getByRole('link', { name: 'Live Traffic' }))
  fireEvent.click((await screen.findAllByRole('button', { name: 'Inspect flow' }))[0])
  await screen.findByRole('heading', { name: 'Flow details · UDP' })
  await screen.findByTestId('output-centroid')
  expect(screen.getAllByRole('img', { name: /membership functions from the server/ })).toHaveLength(5)
  expect(screen.getByRole('heading', { name: 'Policy comparison' })).toBeVisible()
  expect(untranslated()).toEqual([])
  const select = screen.getByRole('combobox', { name: 'Live alert policy' }) as HTMLSelectElement
  expect([...select.options].map(o => o.value)).toEqual(['Sensitive', 'Balanced', 'Conservative'])
  const before = mock.mock.calls.filter(([url]) => String(url) === '/api/analyze').length
  fireEvent.click(screen.getByRole('button', { name: 'Switch to Turkish' }))
  expect(screen.getByRole('heading', { name: 'Akış ayrıntısı · UDP' })).toBeVisible()
  expect(mock.mock.calls.filter(([url]) => String(url) === '/api/analyze')).toHaveLength(before)
})

it('translates every known backend explanation and rule without mutating original reference objects', () => {
  const original = JSON.stringify(fixture)
  const values: string[] = []
  function collect(value: unknown) {
    if (Array.isArray(value)) value.forEach(collect)
    else if (value && typeof value === 'object') Object.values(value).forEach(collect)
    else if (typeof value === 'string' && /[çğıöşüÇĞİÖŞÜ]/u.test(value)) values.push(value)
  }
  collect(fixture); collect(replay)
  const remaining = [...new Set(values.map(v => text(v, 'en')).filter(v => /[çğıöşüÇĞİÖŞÜ]/u.test(v)))]
  expect(remaining).toEqual([])
  expect(JSON.stringify(fixture)).toBe(original)
})

it('has explicit missing-key fallback and never changes API object props or input values', () => {
  act(() => setLanguage('en'))
  expect(fallback('ui.future.key')).toBe('Text unavailable.')
  expect(text('ui.future.key')).toBe('Text unavailable.')
  expect(fallback('future', 'Yerel API referansı')).toBe('Local API reference')
  expect(fallback('An unfamiliar source message')).toBe('An unfamiliar source message')
  const features = { ' Flow Packets/s': 13.333333333333334 }
  const element = <input aria-label="Paket yoğunluğu" value="13,33" data-features={features} readOnly />
  const clone = localizeTree(element, 'en') as typeof element
  expect(clone.props.value).toBe('13,33')
  expect(clone.props['data-features']).toBe(features)
  expect(clone.props['aria-label']).toBe('Packet rate')
  expect(text(formatNumber(2830743))).toBe('2,830,743')
  expect(formatFixed(53.274634837391, 2)).toBe('53.27')
})

it('switches even when persistence is blocked and safely ignores invalid saved languages', () => {
  localStorage.setItem(LANGUAGE_KEY, 'invalid')
  expect(readLanguage()).toBe('tr')
  const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  act(() => setLanguage('en'))
  expect(getLanguage()).toBe('en')
  expect(document.documentElement.lang).toBe('en')
  spy.mockRestore()
})

it('localizes partial/invalid flows and failed connections without drawing fabricated charts', async () => {
  act(() => setLanguage('en'))
  const data = { model: fixture.model, policies: fixture.policies.policies, examples: fixture.examples.examples, evaluation: fixture.evaluation } as unknown as AppData
  const flow = { ...replay.flows[0], provisional: true, finalization: 'monitoring_stopped', status: 'insufficient_data', analysis: null, quality_errors: ['zero_duration_rate_unavailable'], features: { ...replay.flows[0].features, ' Flow Packets/s': null } } as unknown as LiveFlow
  const rendered = render(<LiveFlowDetail flow={flow} data={data} policy="Balanced" onClose={() => {}} />)
  expect(screen.getAllByText('Partial-flow estimate')).toHaveLength(2)
  expect(screen.getByText('No risk score produced')).toBeVisible()
  expect(screen.getByText('Zero duration; packets per second cannot be calculated.')).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(untranslated()).toEqual([])
  rendered.unmount()
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  render(<App />)
  await screen.findByRole('heading', { name: 'Cannot connect to the local server' })
  expect(screen.getByRole('button', { name: 'Try again' })).toBeVisible()
  expect(untranslated()).toEqual([])
})
