import { getJSON, validateAnalysis } from '../api'
import type { Analysis, Level, PolicyID } from '../types'

export type FlowRow = {
  id: string
  observation_mode?: 'capture' | 'replay'
  source: string
  source_port: number
  destination: string
  destination_port: number
  protocol: string
  started_us: number
  ended_us: number
  duration_us: number
  finalization: string
  provisional: boolean
  status: string
  quality_errors: string[]
  features: Record<string, number | null>
  analysis: Analysis | null
  policy_comparison: Partial<Record<PolicyID, { risk_score: number; threshold: number; alert: boolean }>>
}
export type Snapshot = {
  state: string
  running: boolean
  session_id: string | null
  interface: string | null
  mode: 'capture' | 'replay' | null
  policy: PolicyID
  control_token: string
  active_flows: number
  counts: Record<string, number>
  risk_distribution: Record<string, number>
  flows: FlowRow[]
  errors: { code: string; message?: string }[]
}
export type Output = {
  status: string
  model_id: string
  centroid: number
  grid: number[]
  curves: { level: Level; degrees: number[] }[]
  aggregate: number[]
}
export type Discovery = { interfaces: { id: string; name: string; description?: string }[]; error: { message: string } | null }

export async function status(policy: PolicyID, signal?: AbortSignal) {
  const value = await getJSON<Snapshot>(`/api/live/status?policy=${policy}`, signal)
  if (!value || !Array.isArray(value.flows) || !Array.isArray(value.errors) || !value.counts ||
      !value.risk_distribution || typeof value.running !== 'boolean' || typeof value.control_token !== 'string') {
    throw new Error('Invalid monitoring response.')
  }
  return value
}

export async function control(action: 'start' | 'stop', token: string, body: object) {
  const response = await fetch(`/api/live/${action}`, {
    method: 'POST', signal: AbortSignal.timeout(8000),
    headers: { 'Content-Type': 'application/json', 'X-Monitor-Token': token },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.error?.message ?? error.detail ?? 'Monitoring action failed.')
  }
}

export function inspect(row: FlowRow, modelId: string) {
  if (row.status !== 'ok' || row.quality_errors.length || !row.analysis || row.analysis.model_id !== modelId) return null
  try { return validateAnalysis(row.analysis) } catch { return null }
}

export async function output(result: Pick<Analysis, 'model_id' | 'risk_score' | 'input_values'>, signal: AbortSignal) {
  const value = await getJSON<Output>('/api/visualization/output', signal, { features: result.input_values })
  if (value.status !== 'ok' || value.model_id !== result.model_id || value.centroid !== result.risk_score ||
      !Array.isArray(value.grid) || value.grid[0] !== 0 || value.grid.at(-1) !== 100 ||
      value.grid.some((x, i, grid) => !Number.isFinite(x) || (i > 0 && x <= grid[i - 1])) ||
      !Array.isArray(value.curves) || value.curves.length !== 4 ||
      new Set(value.curves.map(curve => curve.level)).size !== 4) throw new Error('Output differs from the scored flow.')
  const valid = (series: number[]) => Array.isArray(series) && series.length === value.grid.length &&
    series.every(x => Number.isFinite(x) && x >= 0 && x <= 1)
  if (!valid(value.aggregate) || value.curves.some(curve => !valid(curve.degrees))) throw new Error('Invalid output curves.')
  return value
}
