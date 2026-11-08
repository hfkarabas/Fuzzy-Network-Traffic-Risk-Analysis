import { useEffect, useState } from 'react'
import { getJSON } from '../api'
import { formatNumber } from '../format'
import type { Analysis, Level } from '../types'
import { Card } from './FuzzyAnalysis'

export type OutputData = {
  status: string; model_id: string; centroid: number | null; grid: number[]
  curves: { level: Level; degrees: number[] }[]; aggregate: number[]
}
const labels: Record<Level, string> = { Low: 'Low', Medium: 'Medium', High: 'High', Critical: 'Critical' }
const colors: Record<Level, string> = { Low: '#4ed8cf', Medium: '#7da4ff', High: '#e0ad67', Critical: '#ef879e' }

export function validateOutput(value: OutputData, model: string, score: number): OutputData {
  if (!value || value.status !== 'ok' || value.model_id !== model || value.centroid !== score ||
    !Array.isArray(value.grid) || value.grid.length < 2 || value.grid[0] !== 0 || value.grid.at(-1) !== 100 ||
    value.grid.some((v, i, grid) => !Number.isFinite(v) || (i > 0 && v <= grid[i - 1])) ||
    !Array.isArray(value.curves) || value.curves.length !== 4 || new Set(value.curves.map(c => c.level)).size !== 4 ||
    !Array.isArray(value.aggregate)) throw new Error('The output plot does not match the current model and score.')
  const valid = (degrees: number[]) => Array.isArray(degrees) && degrees.length === value.grid.length && degrees.every(d => Number.isFinite(d) && d >= 0 && d <= 1)
  if (!valid(value.aggregate) || !value.curves.every(c => Object.hasOwn(labels, c.level) && valid(c.degrees))) throw new Error('Output curves could not be validated.')
  return value
}

export function OutputChart({ output }: { output: OutputData }) {
  const points = (degrees: number[]) => degrees.map((d, i) => `${28 + output.grid[i] * 3.14},${135 - d * 105}`).join(' ')
  const x = 28 + output.centroid! * 3.14
  return (<>
    <svg className="output-chart" viewBox="0 0 360 185" role="img" aria-label={`Output memberships, aggregate and centroid: ${formatNumber(output.centroid!)} / 100`}>
      <title>The server's actual Mamdani output set and centroid</title>
      {[0, .5, 1].map(d => <g key={d}><line x1="28" x2="342" y1={135 - d * 105} y2={135 - d * 105} stroke="#33435a" /><text x="18" y={139 - d * 105} textAnchor="end" fill="#9eafc5" fontSize="11">{d}</text></g>)}
      <polygon data-testid="output-aggregate" points={`28,135 ${points(output.aggregate)} 342,135`} fill="#4ed8cf" fillOpacity=".2" />
      {output.curves.map(c => <polyline data-level={c.level} key={c.level} points={points(c.degrees)} fill="none" stroke={colors[c.level]} strokeWidth="1.6" strokeDasharray="5 3" />)}
      <polyline points={points(output.aggregate)} fill="none" stroke="#80f0df" strokeWidth="2.5" />
      <line data-testid="output-centroid" x1={x} x2={x} y1="20" y2="140" stroke="#f5f8fc" strokeWidth="2" />
      <text x={Math.min(Math.max(x, 95), 265)} y="14" textAnchor="middle" fill="#f5f8fc" fontSize="11">Centroid: {formatNumber(output.centroid!)}</text>
      {[0, 25, 50, 75, 100].map(v => <text key={v} x={28 + v * 3.14} y="154" textAnchor="middle" fill="#9eafc5" fontSize="10">{v}</text>)}
      <text x="185" y="178" textAnchor="middle" fill="#b7cbe1" fontSize="11">Risk score (0–100)</text><text x="5" y="20" fill="#b7cbe1" fontSize="11">µ</text>
    </svg>
    <div className="output-legend">{output.curves.map(c => <span key={c.level}><i style={{ background: colors[c.level] }} />{labels[c.level]}</span>)}<span><i className="aggregate-key" />Aggregated output</span><span>│ Centroid</span></div>
  </>)
}

export default function OutputVisualization({ result }: { result: Analysis | null }) {
  const valid = result?.status === 'ok' && result.risk_score !== null
  const key = valid ? JSON.stringify({ model: result.model_id, score: result.risk_score, features: result.input_values }) : ''
  const [state, setState] = useState<{ key: string; output?: OutputData; error?: string }>({ key: '' })
  useEffect(() => {
    if (!key) return
    const identity = JSON.parse(key) as { model: string; score: number; features: Analysis['input_values'] }
    const controller = new AbortController()
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(5000)])
    void getJSON<OutputData>('/api/visualization/output', signal, { features: identity.features }).then(response => {
      const output = validateOutput(response, identity.model, identity.score)
      if (!controller.signal.aborted) setState({ key, output })
    }).catch(error => { if (!controller.signal.aborted) setState({ key, error: (error as Error).message }) })
    return () => controller.abort()
  }, [key])
  if (!key) return null
  return (<Card className="output-visualization"><div className="card-heading"><h2>Fuzzy output and defuzzification</h2><span className="tiny-label">CENTROID</span></div><div className="output-body">
    {state.key === key && state.output ? <OutputChart output={state.output} /> : state.key === key && state.error ? <p role="status">Output plot unavailable: {state.error} The existing risk result was not changed.</p> : <p role="status">Loading the output set from the server…</p>}
    <p className="footnote">Dashed: output memberships · Fill: aggregate · White: centroid.</p>
  </div></Card>)
}
