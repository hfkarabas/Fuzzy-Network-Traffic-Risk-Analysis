import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import fixture from './test-fixture.json'
import replayFixture from './live-test-fixture.json'
import outputs from './visualization-test-fixture.json'

function installAPI() {
  const server = vi.fn(async (url: string | URL | Request, options?: RequestInit) => {
    const path = String(url)
    if (path === '/api/visualization/output') return new Response(JSON.stringify(outputs.historical))
    if (path === '/api/analyze') {
      const body = JSON.parse(String(options?.body))
      const example = fixture.examples.examples.find(e => JSON.stringify(e.features) === JSON.stringify(body.features))
      if (!example) throw new Error('Test requires a captured real example')
      const analyses = fixture.analyses as Record<string, Record<string, unknown>>
      return new Response(JSON.stringify(analyses[example.id][body.policy]), { status: 200 })
    }
    const key = path.replace('/api/', '') as 'health' | 'model' | 'policies' | 'examples' | 'evaluation'
    return new Response(JSON.stringify(fixture[key]), { status: 200 })
  })
  vi.stubGlobal('fetch', server)
  return server
}
beforeEach(() => { window.location.hash = '#analysis' })

it('opens opt-in live monitoring from existing application navigation', async () => {
  const offline = installAPI()
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL | Request, options?: RequestInit) => {
    if (String(url).includes('/api/live/interfaces')) return new Response(JSON.stringify({ interfaces: [], error: { message: 'Npcap missing' } }))
    if (String(url).includes('/api/live/status')) return new Response(JSON.stringify({ ...replayFixture, mode: null, flows: [], counts: {}, state: 'stopped' }))
    return offline(url, options)
  }))
  render(<App />)
  await screen.findByText('Alert raised')
  await userEvent.click(screen.getByRole('link', { name: 'Live Traffic' }))
  expect(await screen.findByRole('heading', { name: 'Live Traffic' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Start monitoring' })).toBeDisabled()
  expect(await screen.findByText(/Npcap missing/)).toBeVisible()
})

describe('actual-response UI integration', () => {
  it('loads a real example, its actual score and Python membership curves', async () => {
    installAPI(); render(<App />)
    const expected = fixture.analyses['policy-contrast'].Balanced
    await screen.findByText('Alert raised')
    expect(screen.getByRole('heading', { name: 'Risk Analysis' })).toBeVisible()
    expect(screen.getByRole('img', { name: /Risk score/ })).toHaveAccessibleName(`Risk score ${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(expected.risk_score!)} / 100`)
    expect(screen.getAllByRole('img', { name: /membership functions from the server/ })).toHaveLength(5)
    expect(screen.getByText('A risk score is not an attack probability.')).toHaveTextContent('not an attack probability')
  })
  it('switches policy through HTTP without changing the fuzzy score', async () => {
    const server = installAPI(); render(<App />); await screen.findByText('Alert raised')
    const before = screen.getByRole('img', { name: /Risk score/ }).getAttribute('aria-label')
    await userEvent.click(screen.getByRole('button', { name: 'Conservative' }))
    await screen.findByText('No alert raised')
    expect(screen.getByRole('img', { name: /Risk score/ })).toHaveAttribute('aria-label', before)
    const posts = server.mock.calls.filter(call => call[0] === '/api/analyze')
    expect(JSON.parse(String(posts.at(-1)?.[1]?.body)).policy).toBe('Conservative')
  })
  it('shows the actual activated rules and activation strength', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    await userEvent.click(screen.getByRole('tab', { name: /Active rules/ }))
    const first = fixture.analyses['policy-contrast'].Balanced.activated_rules[0]
    expect(screen.getByText(first.text)).toBeVisible()
    expect(screen.getByText(first.id)).toBeVisible()
  })
  it('resets and rejects missing/negative input without sending a prediction', async () => {
    const server = installAPI(); render(<App />); await screen.findByText('Alert raised')
    await userEvent.click(screen.getByRole('button', { name: 'Reset form' }))
    const before = server.mock.calls.filter(call => call[0] === '/api/analyze').length
    await userEvent.click(screen.getByRole('button', { name: 'Analyze flow' }))
    expect(screen.getByRole('alert')).toHaveTextContent('No risk score was produced')
    expect(server.mock.calls.filter(call => call[0] === '/api/analyze')).toHaveLength(before)
    expect(screen.getByRole('img', { name: 'No risk score yet' })).toBeVisible()
  })
  it('filters real error examples and keeps historical labels separate', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    await userEvent.click(screen.getByRole('link', { name: 'Recorded Traffic' }))
    await userEvent.click(screen.getByRole('button', { name: 'Incorrect decisions' }))
    expect(screen.getByRole('heading', { name: 'False-alarm record' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Missed-attack record' })).toBeVisible()
    expect(screen.getAllByRole('button', { name: 'Open in analysis' })).toHaveLength(2)
  })
  it('distinguishes historical tests from group-weighted internal validation', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    await userEvent.click(screen.getByRole('link', { name: 'Model Performance' }))
    await userEvent.click(screen.getByRole('button', { name: 'Internal validation' }))
    expect(screen.getByText('INTERNAL VALIDATION · NOT INDEPENDENT TESTING')).toBeVisible()
    expect(screen.getByText('Group-weighted and flow-weighted rates are different.')).toBeVisible()
    expect(screen.getByText('15.708%')).toBeVisible()
  })
  it('handles backend disconnection with a retry state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline'))); render(<App />)
    await screen.findByRole('heading', { name: 'Cannot connect to the local server' })
    expect(screen.getByRole('button', { name: 'Try again' })).toBeVisible()
  })
  it('keeps recorded model metrics accessible without development framing', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    await userEvent.click(screen.getByRole('link', { name: 'Model Performance' }))
    expect(screen.getByText('Recorded evaluations; not verified live-deployment performance.')).toBeVisible()
    await userEvent.click(screen.getByRole('link', { name: 'Dataset Information' }))
    await userEvent.click(screen.getByText('Recorded model comparison'))
    expect(screen.getByText('Group-weighted rates · balanced policy · recorded results')).toBeVisible()
    expect(screen.getByText('D_combined')).toBeVisible()
  })
  it('rejects malformed API prediction data rather than drawing a fake score', async () => {
    const original = installAPI()
    vi.stubGlobal('fetch', vi.fn(async (url: string | URL | Request, options?: RequestInit) => String(url) === '/api/analyze' ? new Response(JSON.stringify({ status: 'ok', risk_score: 900 }), { status: 200 }) : original(url, options)))
    render(<App />)
    await screen.findByRole('alert')
    expect(screen.getByRole('alert')).toHaveTextContent('invalid analysis response')
    expect(screen.getByRole('img', { name: 'No risk score yet' })).toBeVisible()
  })
  it('clears a previous result when measurements are edited', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    fireEvent.change(screen.getByRole('spinbutton', { name: /Packet rate/ }), { target: { value: '5' } })
    expect(screen.getByRole('img', { name: 'No risk score yet' })).toBeVisible()
  })
  it('supports keyboard switching of explanation tabs', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    screen.getByRole('tab', { name: 'Membership degrees' }).focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: /Active rules/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'panel-rules')
  })
  it('explains all six inference steps through the risk score', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    await userEvent.click(screen.getByRole('tab', { name: 'Processing stages' }))
    expect(screen.getByText('06')).toBeVisible()
    expect(screen.getByText('0–100 · linguistic level')).toBeVisible()
  })
  it('renders every route in English only, without a language switcher', async () => {
    installAPI(); render(<App />); await screen.findByText('Alert raised')
    expect(screen.queryByRole('button', { name: /Switch to|Türkçe|English/ })).not.toBeInTheDocument()
    const turkish = /[çğıöşüÇĞİÖŞÜ]/
    for (const name of ['Security Overview', 'Risk Analysis', 'Recorded Traffic', 'Model Performance', 'System Information', 'Dataset Information']) {
      await userEvent.click(screen.getByRole('link', { name }))
      expect(await screen.findByRole('heading', { name, level: 1 })).toBeVisible()
      expect(document.body.textContent).not.toMatch(turkish)
      for (const element of document.querySelectorAll('[aria-label],[title],[placeholder],[alt]'))
        for (const attribute of ['aria-label', 'title', 'placeholder', 'alt']) expect(element.getAttribute(attribute) ?? '').not.toMatch(turkish)
    }
  })
})
