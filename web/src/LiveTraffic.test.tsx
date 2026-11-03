import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import LiveTraffic from './LiveTraffic'
import type { LiveSnapshot } from './LiveTraffic'
import actual from './live-test-fixture.json'

const finished = actual as unknown as LiveSnapshot // Actual local API replay output; no real traffic.
const stopped = { ...finished, mode: null, counts: {}, flows: [], errors: [], state: 'stopped', running: false }
beforeEach(() => { vi.restoreAllMocks() })

function server(options: { unavailable?: boolean; fail?: string; running?: boolean } = {}) {
  let status = options.running ? { ...stopped, mode: 'capture', state: 'waiting_for_flows', running: true } : stopped
  const mock = vi.fn(async (path: string | URL | Request, init?: RequestInit) => {
    const url = String(path)
    if (url.includes('/interfaces')) return new Response(JSON.stringify({ interfaces: options.unavailable ? [] : [{ id: 'chosen', name: 'Local interface', description: 'Test device' }], error: options.unavailable ? { message: 'Npcap eksik' } : null }))
    if (url.endsWith('/start')) {
      if (options.fail) return new Response(JSON.stringify({ error: { message: options.fail } }), { status: 403 })
      status = finished as typeof status
    }
    if (url.endsWith('/stop')) status = { ...stopped, mode: 'capture' }
    if (url.includes('status?policy=Conservative')) return new Response(JSON.stringify({ ...status, policy: 'Conservative' }))
    return new Response(JSON.stringify(status))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

it('never starts automatically; requires explicit interface and authorization', async () => {
  const mock = server(); render(<LiveTraffic />)
  await screen.findByText('İzleme durduruldu')
  expect(screen.getByRole('button', { name: 'İzlemeyi başlat' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Ağ arayüzü'), { target: { value: 'chosen' } })
  fireEvent.click(screen.getByRole('checkbox'))
  expect(screen.getByRole('button', { name: 'İzlemeyi başlat' })).toBeEnabled()
  expect(mock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})

it('labels unavailable capture and keeps explicit synthetic replay usable', async () => {
  const mock = server({ unavailable: true }); render(<LiveTraffic />)
  await screen.findByText(/Npcap eksik/)
  expect(screen.getByRole('button', { name: 'İzlemeyi başlat' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Veri kaynağı'), { target: { value: 'replay' } })
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'İzlemeyi başlat' }))
  await screen.findByText(/SENTETİK REPLAY/)
  expect(screen.getAllByText(/192.0.2/).length).toBeGreaterThan(0)
  expect(screen.getByText('TCP · 0.300 s')).toBeVisible()
  expect(screen.getByText('UDP · 0.100 s')).toBeVisible()
  const start = mock.mock.calls.find(([url]) => String(url).endsWith('/start'))!
  expect(JSON.parse(String(start[1]?.body))).toEqual({ mode: 'replay', interface: null, authorized: true })
  expect(start[1]?.headers).toMatchObject({ 'X-Monitor-Token': 'test-only-token' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Akışı incele' })[0])
  await screen.findByRole('heading', { name: 'Üyelik dereceleri' })
  expect(screen.getByRole('heading', { name: 'Etkin kurallar' })).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Politika karşılaştırması' })).toBeVisible()
  const row = finished.flows[0]
  expect(screen.getByText(row.analysis!.explanation_tr)).toBeVisible()
  fireEvent.change(screen.getByLabelText('Canlı alarm politikası'), { target: { value: 'Conservative' } })
  await waitFor(() => expect(mock.mock.calls.some(([url]) => String(url).includes('policy=Conservative'))).toBe(true))
})

it('shows waiting state and explicitly stops a running session', async () => {
  const mock = server({ running: true }); render(<LiveTraffic />)
  await screen.findByText('İzleme açık · akış bekleniyor')
  expect(screen.getByText(/Akış bekleniyor; TCP/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'İzlemeyi başlat' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'İzlemeyi durdur' }))
  await screen.findByText('İzleme durduruldu')
  expect(mock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
})

it('reports permission failure without inventing live results', async () => {
  server({ fail: 'Yakalama izni reddedildi.' }); render(<LiveTraffic />)
  await screen.findByText('İzleme durduruldu')
  fireEvent.change(screen.getByLabelText('Ağ arayüzü'), { target: { value: 'chosen' } })
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'İzlemeyi başlat' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Yakalama izni reddedildi.')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('displays analyzing and inference failure states, never a fake score', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('interfaces') ? { interfaces: [], error: null } : {
    ...finished, state: 'analyzing', running: true, counts: { inference_failed: 1 },
    flows: [{ ...finished.flows[0], status: 'inference_failed', analysis: null, policy_comparison: {} }],
    errors: [{ code: 'inference_failed', fatal: false }],
  }))))
  render(<LiveTraffic />)
  await screen.findByText(/tamamlanan akışlar analiz ediliyor/)
  expect(screen.getByText('Çıkarım başarısız · puan yok')).toBeVisible()
})
