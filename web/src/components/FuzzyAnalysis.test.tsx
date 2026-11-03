import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { Analysis, AppData } from '../types'
import fixture from '../test-fixture.json'
import outputs from '../visualization-test-fixture.json'
import { Evidence, MembershipChart, ResultPanel } from './FuzzyAnalysis'
import OutputVisualization, { OutputChart, validateOutput } from './OutputVisualization'
import type { OutputData } from './OutputVisualization'

const data = { model: fixture.model, policies: fixture.policies.policies, examples: fixture.examples.examples, evaluation: fixture.evaluation } as unknown as AppData
const analysis = fixture.analyses['policy-contrast'].Balanced as Analysis
const output = outputs.historical as OutputData
afterEach(() => vi.unstubAllGlobals())

it('draws server-sampled membership points and the server-scaled observed marker', () => {
  const feature = data.model.features[0]
  const position = analysis.input_positions[feature.column]
  const { container } = render(<MembershipChart feature={feature} position={position} />)
  expect(screen.getByRole('img', { name: /sunucudan alınan üyelik fonksiyonları ve mevcut değer/ })).toBeVisible()
  expect(container.querySelector('polyline')).toHaveAttribute('points', feature.chart.curves[0].degrees.map((v, i) => `${28 + feature.chart.positions[i] * 314},${100 - v * 78}`).join(' '))
  expect(container.querySelector('line[stroke="#f4f8fd"]')).toHaveAttribute('x1', String(28 + position * 314))
})

it('shares the existing five feature graphs, numerical memberships and accessible keyboard tabs', () => {
  render(<Evidence result={analysis} data={data} idPrefix="shared-" />)
  expect(screen.getAllByRole('img', { name: /sunucudan alınan üyelik/ })).toHaveLength(5)
  for (const feature of data.model.features) expect(screen.getAllByText(feature.chart.axis_label + ' · beyaz çizgi: mevcut değer').length).toBeGreaterThan(0)
  const tab = screen.getByRole('tab', { name: 'Üyelik dereceleri' })
  fireEvent.keyDown(tab, { key: 'ArrowRight' })
  expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'shared-panel-rules')
  expect(screen.getByText(analysis.activated_rules[0].text_tr)).toBeVisible()
})

it('sorts all backend rule activations without mutating their strengths or order', () => {
  const reversed = { ...analysis, activated_rules: [...analysis.activated_rules].reverse() }
  const original = JSON.stringify(reversed)
  const { container } = render(<Evidence result={reversed} data={data} />)
  fireEvent.click(screen.getByRole('tab', { name: /Etkin kurallar/ }))
  expect([...container.querySelectorAll('.rule-row>.rule-id')].map(e => e.textContent)).toEqual(analysis.activated_rules.map(r => r.id))
  expect(container.querySelectorAll('.rule-row')).toHaveLength(analysis.activated_rules.length)
  expect(container.querySelector('.rule-strength i')).toHaveStyle({ width: `${analysis.activated_rules[0].strength * 100}%` })
  expect(JSON.stringify(reversed)).toBe(original)
})

it('preserves historical score, category and exact selected policy threshold', () => {
  render(<ResultPanel result={analysis} data={data} selectedPolicy="Balanced" busy={false} invalid={false} />)
  expect(screen.getByRole('img', { name: /Risk puanı/ })).toBeVisible()
  expect(screen.getByText('Alarm üretildi')).toBeVisible()
  expect(screen.getByText('Yüksek risk')).toBeVisible()
  expect(screen.getByText(analysis.explanation_tr)).toBeVisible()
})

it('draws the actual aggregate, four output curves and exact backend centroid marker', () => {
  const { container } = render(<OutputChart output={output} />)
  expect(screen.getByRole('img', { name: /Çıktı üyelikleri, birleşik küme ve ağırlık merkezi/ })).toBeVisible()
  expect(container.querySelectorAll('polyline[data-level]')).toHaveLength(4)
  expect(screen.getByTestId('output-aggregate')).toHaveAttribute('points', `28,135 ${output.aggregate.map((d, i) => `${28 + output.grid[i] * 3.14},${135 - d * 105}`).join(' ')} 342,135`)
  expect(screen.getByTestId('output-centroid')).toHaveAttribute('x1', String(28 + output.centroid! * 3.14))
})

it('fetches visualization only with full-precision features and reuses it across policies', async () => {
  const fetch = vi.fn(async (_path: string, _init?: RequestInit) => new Response(JSON.stringify(output)))
  vi.stubGlobal('fetch', fetch)
  const { rerender } = render(<OutputVisualization result={analysis} />)
  await screen.findByTestId('output-centroid')
  expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({ features: analysis.input_values })
  rerender(<OutputVisualization result={fixture.analyses['policy-contrast'].Conservative as Analysis} />)
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
})

it('does not fetch or render output curves for abstention', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  render(<OutputVisualization result={{ ...analysis, status: 'invalid_input', risk_score: null, risk_level: null }} />)
  expect(fetch).not.toHaveBeenCalled()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})

it('rejects mismatched model, centroid and invalid degree data instead of drawing a fake output', async () => {
  expect(() => validateOutput({ ...output, model_id: 'other' }, analysis.model_id, analysis.risk_score!)).toThrow()
  expect(() => validateOutput({ ...output, centroid: 10 }, analysis.model_id, analysis.risk_score!)).toThrow()
  expect(() => validateOutput({ ...output, aggregate: [2] }, analysis.model_id, analysis.risk_score!)).toThrow()
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ...output, centroid: 10 }))))
  render(<OutputVisualization result={analysis} />)
  expect(await screen.findByText(/Mevcut risk sonucu değiştirilmedi/)).toBeVisible()
  expect(screen.queryByTestId('output-centroid')).not.toBeInTheDocument()
})
