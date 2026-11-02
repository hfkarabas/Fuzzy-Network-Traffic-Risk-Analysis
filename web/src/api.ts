import type { Analysis, AppData, Evaluation, Example, Flow, Model, Policy, PolicyID } from './types'

export class ApiError extends Error { constructor(message: string, public details: string[] = []) { super(message) } }
export async function getJSON<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  let response: Response
  try { response = await fetch(path, { signal, ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) }) }
  catch (error) { if (error instanceof Error && error.name === 'AbortError') throw error; throw new ApiError('Yerel sunucuya ulaşılamadı. Sunucunun çalıştığını kontrol edip yeniden deneyin.') }
  let value: unknown
  try { value = await response.json() } catch { throw new ApiError('Sunucu beklenen JSON yanıtını vermedi. Yerel API adresini kontrol edin.') }
  if (!response.ok) {
    const errors = (value as { validation_errors?: { field: string; message: string }[] }).validation_errors
    throw new ApiError(response.status === 422 ? 'Girdi doğrulanamadı; risk puanı üretilmedi.' : 'Sunucu işlemi tamamlayamadı. Lütfen yeniden deneyin.', errors?.map(e => `${e.field}: ${e.message}`) ?? [])
  }
  return value as T
}
export function validateAnalysis(value: Analysis): Analysis {
  if (!value || !['ok', 'invalid_input', 'no_rule_activation'].includes(value.status) || !Array.isArray(value.activated_rules) || !value.membership_degrees || typeof value.explanation_tr !== 'string') throw new ApiError('Sunucudan geçersiz analiz yanıtı alındı. Sonuç gösterilmedi.')
  if (value.status === 'ok' && (typeof value.risk_score !== 'number' || !Number.isFinite(value.risk_score) || value.risk_score < 0 || value.risk_score > 100 || !['Low', 'Medium', 'High', 'Critical'].includes(value.risk_level ?? '') || typeof value.alert !== 'boolean' || !value.alert_policy || !value.input_positions || typeof value.model_id !== 'string' || Object.keys(value.membership_degrees).length !== 5)) throw new ApiError('Analiz yanıtının puan veya politika alanları geçersiz.')
  if (value.status !== 'ok' && (value.risk_score !== null || value.alert !== null)) throw new ApiError('Geçersiz girdi için sayısal sonuç döndürüldü; sonuç gösterilmedi.')
  for (const terms of Object.values(value.membership_degrees)) for (const degree of Object.values(terms)) if (!Number.isFinite(degree) || degree < 0 || degree > 1) throw new ApiError('Üyelik dereceleri geçersiz; sonuç gösterilmedi.')
  if (value.activated_rules.some(r => !Number.isFinite(r.strength) || r.strength <= 0 || r.strength > 1 || typeof r.text_tr !== 'string')) throw new ApiError('Kural etkinlikleri geçersiz; sonuç gösterilmedi.')
  return value
}
export async function analyze(features: Flow, policy: PolicyID, signal?: AbortSignal) { return validateAnalysis(await getJSON<Analysis>('/api/analyze', signal, { features, policy })) }
export async function loadData(signal?: AbortSignal): Promise<AppData> {
  const [health, model, policies, examples, evaluation] = await Promise.all([
    getJSON<{ status: string }>('/api/health', signal), getJSON<Model>('/api/model', signal),
    getJSON<{ policies: Policy[] }>('/api/policies', signal), getJSON<{ examples: Example[] }>('/api/examples', signal), getJSON<Evaluation>('/api/evaluation', signal),
  ])
  if (health.status !== 'ok' || model.features?.length !== 5 || !model.model_id || policies.policies?.length !== 3 || !Array.isArray(examples.examples) || !Array.isArray(evaluation.historical) || !Array.isArray(evaluation.internal)) throw new ApiError('Sunucu yapılandırması beklenen uygulama sözleşmesiyle uyuşmuyor.')
  return { model, policies: policies.policies, examples: examples.examples, evaluation }
}
