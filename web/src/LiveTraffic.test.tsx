import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import LiveTraffic from './LiveTraffic'
import type { LiveSnapshot } from './LiveTraffic'
import actual from './live-test-fixture.json'
import historical from './test-fixture.json'
import outputs from './visualization-test-fixture.json'
import type { AppData } from './types'
const data = { model: historical.model, policies: historical.policies.policies, examples: historical.examples.examples, evaluation: historical.evaluation } as unknown as AppData

const finished = actual as unknown as LiveSnapshot // Actual local API replay output; no real traffic.
const stopped = { ...finished, mode: null, counts: {}, flows: [], errors: [], state: 'stopped', running: false }
beforeEach(() => { vi.restoreAllMocks() })

function server(options: { unavailable?: boolean; fail?: string; running?: boolean } = {}) {
  let status = options.running ? { ...stopped, mode: 'capture', state: 'waiting_for_flows', running: true } : stopped
  const mock = vi.fn(async (path: string | URL | Request, init?: RequestInit) => {
    const url = String(path)
    if (url === '/api/visualization/output' || url === '/api/analyze') {
      const body = JSON.parse(String(init?.body)); const proto = finished.flows.find(f => JSON.stringify(f.features) === JSON.stringify(body.features))!.protocol.toLowerCase() as 'tcp' | 'udp'
      return new Response(JSON.stringify(url.endsWith('/output') ? outputs[proto] : outputs.liveAnalyses[proto][body.policy as 'Balanced']))
    }
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
  const mock = server(); render(<LiveTraffic data={data} />)
  await screen.findByText('Monitoring stopped')
  expect(screen.getByRole('button', { name: 'Start monitoring' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Network interface'), { target: { value: 'chosen' } })
  fireEvent.click(screen.getByRole('checkbox'))
  expect(screen.getByRole('button', { name: 'Start monitoring' })).toBeEnabled()
  expect(mock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})

it('labels unavailable capture and keeps explicit synthetic replay usable', async () => {
  const mock = server({ unavailable: true }); render(<LiveTraffic data={data} />)
  await screen.findByText(/Npcap eksik/)
  expect(screen.getByRole('button', { name: 'Start monitoring' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Data source'), { target: { value: 'replay' } })
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Start monitoring' }))
  await screen.findByText(/SYNTHETIC REPLAY/)
  expect(screen.getAllByText(/192.0.2/).length).toBeGreaterThan(0)
  expect(screen.getByText('TCP · 0.300 s')).toBeVisible()
  expect(screen.getByText('UDP · 0.100 s')).toBeVisible()
  const start = mock.mock.calls.find(([url]) => String(url).endsWith('/start'))!
  expect(JSON.parse(String(start[1]?.body))).toEqual({ mode: 'replay', interface: null, authorized: true })
  expect(start[1]?.headers).toMatchObject({ 'X-Monitor-Token': 'test-only-token' })
  fireEvent.click(screen.getAllByRole('button', { name: 'Inspect flow' })[0])
  await screen.findByRole('tab', { name: 'Membership degrees' })
  expect(screen.getAllByRole('img', { name: /membership functions from the server/ })).toHaveLength(5)
  await screen.findByRole('img', { name: /Output memberships, aggregate/ })
  fireEvent.click(screen.getByRole('tab', { name: /Active rules/ }))
  expect(screen.getByText(finished.flows[0].analysis!.activated_rules[0].text)).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Policy comparison' })).toBeVisible()
  const row = finished.flows[0]
  expect(screen.getByText('Dominant rules: ' + row.analysis!.activated_rules.slice(0, 3).map(r => r.id).join(' · '))).toBeVisible()
  fireEvent.change(screen.getByLabelText('Live alert policy'), { target: { value: 'Conservative' } })
  await waitFor(() => expect(mock.mock.calls.some(([url]) => String(url).includes('policy=Conservative'))).toBe(true))
})

it('shows waiting state and explicitly stops a running session', async () => {
  const mock = server({ running: true }); render(<LiveTraffic data={data} />)
  await screen.findByText('Monitoring active · waiting for flows')
  expect(screen.getByText(/Waiting for flows; TCP/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Start monitoring' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Stop monitoring' }))
  await screen.findByText('Monitoring stopped')
  expect(mock.mock.calls.some(([url]) => String(url).endsWith('/stop'))).toBe(true)
})

it('reports permission failure without inventing live results', async () => {
  server({ fail: 'Capture permission denied.' }); render(<LiveTraffic data={data} />)
  await screen.findByText('Monitoring stopped')
  fireEvent.change(screen.getByLabelText('Network interface'), { target: { value: 'chosen' } })
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Start monitoring' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Capture permission denied.')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('displays analyzing and inference failure states, never a fake score', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('interfaces') ? { interfaces: [], error: null } : {
    ...finished, state: 'analyzing', running: true, counts: { inference_failed: 1 },
    flows: [{ ...finished.flows[0], status: 'inference_failed', analysis: null, policy_comparison: {} }],
    errors: [{ code: 'inference_failed', fatal: false }],
  }))))
  render(<LiveTraffic data={data} />)
  await screen.findByText(/analyzing finalized flows/)
  expect(screen.getByText('Inference failed · no score')).toBeVisible()
})

it('pins an inspected flow when polling evicts it and returns focus on close', async () => {
  let visible: LiveSnapshot = finished
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url.includes('/interfaces') ? { interfaces: [], error: null } : url.endsWith('/output') ? outputs.udp : visible,
  ))))
  render(<LiveTraffic data={data} />)
  const inspect = (await screen.findAllByRole('button', { name: 'Inspect flow' }))[0]
  fireEvent.click(inspect)
  await screen.findByTestId('output-centroid')
  visible = { ...finished, flows: [] }
  fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }))
  await screen.findByText('No flows have been observed in this session yet.')
  expect(screen.getByRole('heading', { name: 'Flow details · UDP' })).toBeVisible()
  expect(screen.getAllByRole('img', { name: /membership functions from the server/ })).toHaveLength(5)
  fireEvent.click(screen.getByRole('button', { name: 'Close flow details' }))
  expect(screen.queryByRole('heading', { name: 'Flow details · UDP' })).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Recent flows · up to 50 shown' })).toHaveFocus()
})
