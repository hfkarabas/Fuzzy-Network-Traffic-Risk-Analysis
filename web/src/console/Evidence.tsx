import { useEffect, useId, useState } from 'react'
import type { Analysis, AppData, Feature, Level, PolicyID } from '../types'
import { useLabels, useRuleText, useWord } from './language'
import { output } from './transport'
import type { Output } from './transport'

const colors = ['#75d9ff', '#cbadff', '#f3b874', '#ff8caa']
const levels: Level[] = ['Low', 'Medium', 'High', 'Critical']

function Plot({ label, x, series, marker, aggregate, ticks }: {
  label: string; x: number[]; series: { label: string; points: number[]; color: string }[]
  marker?: number; aggregate?: number[]; ticks: [string, string]
}) {
  const { n, t } = useLabels()
  const title = useId()
  const px = (v: number) => 36 + v * 342
  const py = (v: number) => 133 - v * 104
  const coordinates = (values: number[]) => values.map((y, i) => `${px(x[i])},${py(y)}`).join(' ')
  return <svg viewBox="0 0 400 165" role="img" aria-labelledby={title} className="plot">
    <title id={title}>{label}</title>
    {[0, .25, .5, .75, 1].map(i => <line key={i} x1={px(i)} x2={px(i)} y1={29} y2={133} className="plot-grid" />)}
    {[0, .5, 1].map(i => <g key={i}><line x1="36" x2="378" y1={py(i)} y2={py(i)} className="plot-grid" /><text x="28" y={py(i) + 4} textAnchor="end">{n(i)}</text></g>)}
    {aggregate && <><polygon points={`36,133 ${coordinates(aggregate)} 378,133`} fill="#75d9ff25" /><polyline points={coordinates(aggregate)} stroke="#75d9ff" fill="none" strokeWidth="2.5" /></>}
    {series.map((s, i) => <polyline key={s.label} points={coordinates(s.points)} fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={i === 1 ? '6 3' : i === 2 ? '2 3' : i === 3 ? '7 3 2 3' : undefined} />)}
    {marker !== undefined && Number.isFinite(marker) && <line data-testid={aggregate ? 'new-centroid' : undefined} x1={px(marker)} x2={px(marker)} y1="20" y2="139" stroke="white" strokeDasharray="4 3" />}
    <text x="36" y="154">{ticks[0]}</text><text x="378" y="154" textAnchor="end">{ticks[1]}</text>
    <text x="36" y="16">{t('Membership μ', 'Üyelik μ')}</text>
  </svg>
}

export function Membership({ feature, result }: { feature: Feature; result?: Analysis }) {
  const { t, n } = useLabels()
  const w = useWord()
  const value = result?.input_values[feature.column]
  return <article className="signal">
    <header><div><h3>{w(feature.title)}</h3><code>{feature.column}</code></div>
      {value != null && <strong title={String(value)}>{n(value)} <small>{w(feature.unit)}</small></strong>}</header>
    <Plot label={`${w(feature.title)} · ${t('membership curves', 'üyelik eğrileri')}`} x={feature.chart.positions}
      ticks={['0', `${n(feature.chart.values.at(-1) ?? 0)} ${w(feature.unit)}`]} marker={result?.input_positions[feature.column]}
      series={feature.chart.curves.map((curve, i) => ({ label: curve.term, points: curve.degrees, color: colors[i] }))} />
    <div className="keys">{feature.chart.curves.map((curve, i) => {
      const degree = result?.membership_degrees[feature.column]?.[curve.term]
      return <span key={curve.term}><i style={{ background: colors[i] }} />{w(curve.title)} {degree != null && <b title={String(degree)}>{degree > 0 && degree < .001 ? '<0.001' : n(degree, 3)}</b>}</span>
    })}</div>
    <p className="quiet">{feature.chart.axis_label.includes('log') ? t('Log display axis', 'Logaritmik gösterim ekseni') : t('Linear display axis', 'Doğrusal gösterim ekseni')}{result && t(' · White line: observed value', ' · Beyaz çizgi: gözlenen değer')}</p>
  </article>
}

export function PolicyGrid({ data, result, decisions }: { data: AppData; result: Analysis; decisions?: Partial<Record<PolicyID, { alert: boolean; threshold: number }>> }) {
  const { n, t } = useLabels()
  const w = useWord()
  return <div className="policy-grid">{data.policies.map(p => {
    const decision = decisions?.[p.id]
    // Policy comparison is the documented threshold comparison on the returned score.
    const alert = decision?.alert ?? (result.risk_score !== null && result.risk_score >= p.threshold)
    return <div key={p.id} className={p.id === result.alert_policy.name ? 'chosen-policy' : ''}><span>{w(p.title)}</span>
      <b>{n(decision?.threshold ?? p.threshold)}</b><small className={alert ? 'alarm' : 'quiet'}>{alert ? t('Alert', 'Alarm') : t('No alert', 'Alarm yok')}</small>
    </div>
  })}</div>
}
export function Decision({ result, policy }: { result: Analysis; policy?: { name: PolicyID; threshold: number; alert: boolean } }) {
  const { n, t } = useLabels()
  const w = useWord()
  return <div className="decision">
    <div><small>{t('Risk score', 'Risk puanı')}</small><strong>{n(result.risk_score!)} <span>/ 100</span></strong></div>
    <div><small>{t('Risk level', 'Risk düzeyi')}</small><b data-risk={result.risk_level}>{w(result.risk_level!)}</b></div>
    <div><small>{w(policy?.name ?? result.alert_policy.name)} · {t('threshold', 'eşik')} {n(policy?.threshold ?? result.alert_policy.threshold)}</small>
      <b className={(policy?.alert ?? result.alert) ? 'alarm' : ''}>{(policy?.alert ?? result.alert) ? t('Alert', 'Alarm') : t('No alert', 'Alarm yok')}</b></div>
  </div>
}

function OutputPlot({ result }: { result: Analysis }) {
  const [plot, setPlot] = useState<Output | null>(null)
  const [error, setError] = useState('')
  const w = useWord()
  const { n, t } = useLabels()
  const identity = JSON.stringify({ model_id: result.model_id, risk_score: result.risk_score, input_values: result.input_values })
  useEffect(() => {
    const controller = new AbortController()
    const scoredFlow = JSON.parse(identity) as Pick<Analysis, 'model_id' | 'risk_score' | 'input_values'>
    void output(scoredFlow, AbortSignal.any([controller.signal, AbortSignal.timeout(8000)])).then(value => {
      if (!controller.signal.aborted) setPlot(value)
    }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [identity])
  if (!plot) return <p role="status">{error ? t('Output unavailable. ', 'Çıktı kullanılamıyor. ') + error : t('Loading output curve…', 'Çıktı eğrisi yükleniyor…')}</p>
  return <div className="output-plot"><Plot label={t('Aggregated fuzzy output and centroid', 'Birleşik bulanık çıktı ve ağırlık merkezi')}
    x={plot.grid.map(x => x / 100)} aggregate={plot.aggregate} marker={plot.centroid / 100} ticks={['0', '100']}
    series={plot.curves.map(curve => ({ label: curve.level, points: curve.degrees, color: colors[levels.indexOf(curve.level)] }))} />
    <div className="keys">{plot.curves.map(curve => <span key={curve.level}><i style={{ background: colors[levels.indexOf(curve.level)] }} />{w(curve.level)}</span>)}</div>
    <p>{t('Centroid', 'Ağırlık merkezi')} <b>{n(plot.centroid, 6)}</b> · {t('Blue fill: aggregated output', 'Mavi dolgu: birleşik çıktı')}</p>
  </div>
}

export function Evidence({ data, result }: { data: AppData; result: Analysis }) {
  const { n, t } = useLabels()
  const w = useWord()
  const ruleText = useRuleText()
  return <div className="evidence-stack">
    {!!result.explanation_data.outside_training_range.length && <p className="notice" role="status">{t('Some measurements exceed the training range. The model saturates their memberships.', 'Bazı ölçümler eğitim aralığının dışında. Model, üyeliklerini sınıra doyurur.')}</p>}
    <section className="surface"><h2>{t('Input memberships', 'Girdi üyelikleri')}</h2>
      <div className="signals">{data.model.features.map(feature => <Membership key={feature.key} feature={feature} result={result} />)}</div>
    </section>
    <section className="surface"><h2>{t('Activated rules', 'Etkin kurallar')}</h2>
      <ol className="rule-lines">{[...result.activated_rules].sort((a, b) => b.strength - a.strength).map(rule =>
        <li key={rule.id}><code>{rule.id}</code><span>{ruleText(rule.text)}</span><span data-risk={rule.consequent}>{w(rule.consequent)}</span>
          <meter min={0} max={1} value={rule.strength} aria-label={`${rule.id} ${t('activation', 'etkinlik')}`} /><b>{n(rule.strength, 3)}</b></li>)}</ol>
    </section>
    <section className="surface"><h2>{t('Output and defuzzification', 'Çıktı ve durulaştırma')}</h2>
      <OutputPlot key={JSON.stringify([result.model_id, result.risk_score, result.input_values])} result={result} />
    </section>
  </div>
}
