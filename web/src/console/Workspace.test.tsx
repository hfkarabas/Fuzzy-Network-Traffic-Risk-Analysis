import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import Workspace from './Workspace'
import fixture from '../test-fixture.json'
import replay from '../live-test-fixture.json'
import curves from '../visualization-test-fixture.json'
import type { Snapshot } from './transport'

const replayed = replay as unknown as Snapshot
beforeEach(() => localStorage.clear())

function server() {
  let snapshot: Snapshot = { ...replayed, session_id: null, mode: null, running: false, state: 'stopped', flows: [], counts: {} }
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/live/interfaces') return Response.json({ interfaces: [], error: { message: 'Npcap unavailable' } })
    if (url.startsWith('/api/live/status')) return Response.json({ ...snapshot, policy: new URLSearchParams(url.split('?')[1]).get('policy') })
    if (url === '/api/live/start') { snapshot = replayed; return Response.json(snapshot) }
    if (url === '/api/visualization/output') {
      const inputs = JSON.parse(String(init?.body)).features
      const row = replayed.flows.find(f => JSON.stringify(f.features) === JSON.stringify(inputs))
      return Response.json(row?.protocol === 'TCP' ? curves.tcp : row?.protocol === 'UDP' ? curves.udp : curves.historical)
    }
    if (url === '/api/analyze') {
      const body = JSON.parse(String(init?.body))
      return Response.json(fixture.analyses['policy-contrast'][body.policy as 'Balanced'])
    }
    return Response.json(fixture[url.slice(5) as 'health'])
  })
  vi.stubGlobal('fetch', fetch)
  return { fetch, update: (value: Snapshot) => { snapshot = value } }
}

it('starts on the monitor, requires opt-in and displays actual replay evidence across languages', async () => {
  const { fetch } = server()
  render(<Workspace/>)
  await screen.findByText('Stopped')
  const start = screen.getByRole('button', { name: 'Start monitoring' })
  expect(start).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'replay' } })
  expect(start).toBeDisabled()
  expect(fetch.mock.calls.some(([path]) => path === '/api/live/start')).toBe(false)
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(start)
  await screen.findByText('Synthetic replay · recorded packets for testing')
  expect(fetch.mock.calls.find(([path]) => path === '/api/live/start')?.[1]).toMatchObject({
    headers: { 'X-Monitor-Token': replayed.control_token },
    body: JSON.stringify({ mode: 'replay', interface: null, authorized: true }),
  })
  expect(screen.getByRole('button', { name: /Inspect TCP/ })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /Inspect UDP/ }))
  fireEvent.click(screen.getByRole('button', { name: /Open full fuzzy analysis/ }))
  await screen.findByTestId('new-centroid')
  expect(screen.getAllByRole('img', { name: /membership curves/ })).toHaveLength(5)
  fireEvent.click(screen.getByRole('button', { name: 'Türkçeye geç' }))
  expect(screen.getByRole('heading', { name: 'UDP akışı' })).toBeVisible()
  expect(screen.getAllByRole('img', { name: /üyelik eğrileri/ })).toHaveLength(5)
  expect(screen.getByTestId('new-centroid')).toBeInTheDocument()
  expect(localStorage.getItem('fuzzy-network-risk.language')).toBe('tr')
})

it('filters protocol and freezes the displayed rows during polling', async () => {
  const { update } = server()
  update({ ...replayed, counts: { finalized_flows: 2 } })
  render(<Workspace/>)
  await screen.findByRole('button', { name: /Inspect UDP/ })
  fireEvent.change(screen.getByLabelText('Protocol'), { target: { value: 'TCP' } })
  expect(screen.queryByRole('button', { name: /Inspect UDP/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Freeze list' }))
  update({ ...replayed, flows: [], counts: { finalized_flows: 3 } })
  fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  const resume = await screen.findByRole('button', { name: 'Resume list · +1' })
  expect(screen.getByRole('button', { name: /Inspect TCP/ })).toBeVisible()
  fireEvent.click(resume)
  expect(screen.queryByRole('button', { name: /Inspect TCP/ })).not.toBeInTheDocument()
})

it('preserves abstention, the source reason and the raw measurements', async () => {
  const { update, fetch } = server()
  const row = replayed.flows[0]
  update({ ...replayed, flows: [{ ...row, status: 'insufficient_data', analysis: null, quality_errors: ['zero_duration_rate_unavailable'] }] })
  render(<Workspace/>)
  fireEvent.click(await screen.findByRole('button', { name: /Inspect UDP/ }))
  expect(screen.getByText('No valid score')).toBeVisible()
  expect(screen.getByText('zero_duration_rate_unavailable')).toBeVisible()
  expect(screen.getByText('Observed measurements')).toBeVisible()
  expect(screen.queryByTestId('new-centroid')).not.toBeInTheDocument()
  expect(fetch.mock.calls.some(([url]) => url === '/api/visualization/output')).toBe(false)
})

it('rejects missing inputs and compares policies using recorded engine results', async () => {
  window.location.hash = '#analysis'
  const { fetch } = server()
  render(<Workspace/>)
  fireEvent.click(await screen.findByRole('button', { name: 'Analyze flow' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a finite, nonnegative value')
  expect(fetch.mock.calls.some(([url]) => url === '/api/analyze')).toBe(false)
  fireEvent.change(screen.getByLabelText('Load a recorded flow'), { target: { value: 'policy-contrast' } })
  fireEvent.click(screen.getByRole('button', { name: 'Analyze flow' }))
  await screen.findByTestId('new-centroid')
  const first = within(screen.getByRole('heading', { name: 'Decision' }).closest('section')!)
  expect(first.getByText('53.27')).toBeVisible()
  fireEvent.change(screen.getByLabelText('Alert policy'), { target: { value: 'Conservative' } })
  await waitFor(() => expect(first.getByText(/Conservative · threshold/)).toBeVisible())
  expect(first.getByText('53.27')).toBeVisible()
})

it('shows the research comparison and original confusion matrix', async () => {
  window.location.hash = '#evaluation'
  server(); render(<Workspace/>)
  await screen.findByText('Accuracy study')
  expect(screen.getByText('93.507%')).toBeVisible()
  expect(screen.getByText('Confusion matrix · raw flows')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Historical by day' }))
  expect(screen.getByText('376,010')).toBeVisible()
})
