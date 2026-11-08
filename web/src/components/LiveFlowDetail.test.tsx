import { render, screen, fireEvent } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { Analysis, AppData } from '../types'
import type { LiveFlow } from '../LiveTraffic'
import historical from '../test-fixture.json'
import live from '../live-test-fixture.json'
import outputs from '../visualization-test-fixture.json'
import LiveFlowDetail from './LiveFlowDetail'

const data = { model: historical.model, policies: historical.policies.policies, examples: historical.examples.examples, evaluation: historical.evaluation } as unknown as AppData
const flow = live.flows.find(f => f.protocol === 'TCP') as unknown as LiveFlow
afterEach(() => vi.unstubAllGlobals())
function api() {
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    const value = path.endsWith('/output') ? outputs.tcp : outputs.liveAnalyses.tcp[JSON.parse(String(init?.body)).policy as 'Balanced']
    return new Response(JSON.stringify(value))
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

it('renders shared graphical live analysis, all metadata and backend policy comparisons', async () => {
  api(); const close = vi.fn()
  const { container } = render(<LiveFlowDetail flow={flow} data={data} policy="Balanced" onClose={close} />)
  expect(screen.getByText(`${flow.source} : ${flow.source_port}`)).toBeVisible()
  expect(screen.getByText(`${flow.destination} : ${flow.destination_port}`)).toBeVisible()
  expect(screen.getByText('TCP RST')).toBeVisible()
  expect(screen.getByText('Eligible for inference')).toBeVisible()
  expect(screen.getByText(/Finalized observed flow/)).toBeVisible()
  expect(screen.getAllByRole('img', { name: /membership functions from the server/ })).toHaveLength(5)
  expect(screen.getByRole('img', { name: /Risk score/ })).toBeVisible()
  expect(screen.getByTitle(String(flow.features[' Bwd Packet Length Std']))).toBeVisible()
  expect(container.querySelector('pre')).toBeNull()
  await screen.findByTestId('output-centroid')
  expect(screen.getByRole('heading', { name: 'Policy comparison' })).toBeVisible()
  for (const policy of ['Sensitive', 'Balanced', 'Conservative']) expect(screen.getByRole('heading', { name: policy, level: 3 })).toBeVisible()
  fireEvent.click(screen.getByRole('tab', { name: /Active rules/ }))
  expect(screen.getByText(flow.analysis!.activated_rules[0].text)).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Close flow details' }))
  expect(close).toHaveBeenCalledOnce()
})

it('keeps a prominent partial-segment warning and reason while allowing valid graphs', async () => {
  api(); render(<LiveFlowDetail flow={{ ...flow, provisional: true, finalization: 'monitoring_stopped' }} data={data} policy="Balanced" onClose={() => {}} />)
  expect(screen.getAllByText('Partial-flow estimate')).toHaveLength(2)
  expect(screen.getByText('Monitoring stopped')).toBeVisible()
  expect(screen.getByText(/full connection data may be unavailable/)).toBeVisible()
  await screen.findByTestId('output-centroid')
})

it('preserves metadata and available values but never fabricates invalid-flow charts', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  const insufficient = { ...flow, status: 'insufficient_data', analysis: null, features: { ...flow.features, ' Flow Packets/s': null }, quality_errors: ['zero_duration_rate_unavailable'], policy_comparison: {} }
  render(<LiveFlowDetail flow={insufficient} data={data} policy="Balanced" onClose={() => {}} />)
  expect(screen.getByText('No risk score produced')).toBeVisible()
  expect(screen.getByText('Unavailable')).toBeVisible()
  expect(screen.getByText('Zero duration; packets per second cannot be calculated.')).toBeVisible()
  expect(screen.getByText(`${flow.source} : ${flow.source_port}`)).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})

it('refuses mismatched model plots and safely wraps long source addresses', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  const address = 'very-long-observed-address.example.'.repeat(5)
  render(<LiveFlowDetail flow={{ ...flow, source: address, analysis: { ...flow.analysis!, model_id: 'old-model' } }} data={data} policy="Balanced" onClose={() => {}} />)
  expect(screen.getByText(`${address} : ${flow.source_port}`)).toBeVisible()
  expect(screen.getByText('Model identity mismatch')).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})

it('loads the selected policy for a pinned flow without changing the fuzzy score or refetching identical output', async () => {
  const fetch = api()
  const { rerender } = render(<LiveFlowDetail flow={flow} data={data} policy="Balanced" onClose={() => {}} />)
  await screen.findByTestId('output-centroid')
  const score = screen.getByRole('img', { name: /Risk score/ }).getAttribute('aria-label')
  rerender(<LiveFlowDetail flow={flow} data={data} policy="Conservative" onClose={() => {}} />)
  await screen.findByText(/Conservative policy/)
  expect(screen.getByRole('img', { name: /Risk score/ })).toHaveAttribute('aria-label', score)
  expect(fetch.mock.calls.filter(([path]) => path === '/api/analyze')).toHaveLength(1)
  expect(fetch.mock.calls.filter(([path]) => path === '/api/visualization/output')).toHaveLength(1)
})

it('keeps extreme finite input values formatted while retaining their full precision', () => {
  vi.stubGlobal('fetch', vi.fn())
  render(<LiveFlowDetail flow={{ ...flow, status: 'insufficient_data', analysis: null, features: { ...flow.features, ' Flow Packets/s': 1.234567890123456e100 } }} data={data} policy="Balanced" onClose={() => {}} />)
  expect(screen.getByTitle('1.234567890123456e+100')).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})

it('explains per-flow capture impairments without drawing charts', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  const impaired = { ...flow, status: 'insufficient_data', analysis: null, quality_errors: ['capture_queue_loss', 'concurrent_capture_error', 'endpoint_packet_rejected'], policy_comparison: {} }
  render(<LiveFlowDetail flow={impaired} data={data} policy="Balanced" onClose={() => {}} />)
  expect(screen.getByText('A packet of this flow was lost in the capture queue.')).toBeVisible()
  expect(screen.getByText('A packet between the same endpoints was unusable.')).toBeVisible()
  expect(screen.getByText('An unattributable capture error occurred while this flow was active.')).toBeVisible()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})
