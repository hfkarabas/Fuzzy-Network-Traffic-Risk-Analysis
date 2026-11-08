import { useState } from 'react'
import type { ReactNode } from 'react'
import { Check, ChevronRight, Gauge, GitBranch, LoaderCircle, ScanLine, Shield, ShieldAlert, TriangleAlert, Zap } from 'lucide-react'
import type { Analysis, AppData, Feature, Level, PolicyID } from '../types'
import { formatNumber, formatFixed, LOCALE } from '../format'
const nf = { format: formatNumber }
const levels: Record<Level, string> = { Low: 'Low', Medium: 'Medium', High: 'High', Critical: 'Critical' }
const degreeText = (v: number) => v > 0 && v < .001 ? '<0.001' : formatFixed(v, 3)
export function Badge({ level }: { level: Level }) {
 return (<span className={`badge ${level.toLowerCase()}`}><span />{levels[level]} risk</span>)
}
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
 return (<section className={`card ${className}`}>{children}</section>)
}
export function StepPipeline() {
  const steps = [['01', 'Inputs', 'Five flow measurements'], ['02', 'Fuzzification', 'Membership in linguistic sets'], ['03', 'Rules', 'Minimum activation'], ['04', 'Aggregation', 'Maximum output union'], ['05', 'Defuzzification', 'Centroid'], ['06', 'Risk score', '0–100 · linguistic level']]
  return (<div className="pipeline" aria-label="Fuzzy inference steps">{steps.map(([n, title, body]) => <div className="step" key={n}><span className="step-no">{n}</span><div><b>{title}</b><small>{body}</small></div>{n !== '06' && <ChevronRight size={15} className="step-arrow" />}</div>)}</div>)
}
export function MembershipChart({ feature, position }: { feature: Feature; position?: number }) {
  const colors = ['#4ed8cf', '#7da4ff', '#e0ad67']
  return (<svg className="membership-chart" viewBox="0 0 360 130" role="img" aria-label={`${feature.title}: membership functions from the server${position !== undefined ? ' and observed value' : ''}`}>
    {[0, .5, 1].map(v => <g key={v}><line x1="28" y1={100 - v * 78} x2="342" y2={100 - v * 78} stroke="#273345" strokeDasharray={v === .5 ? '3 4' : undefined} /><text x="18" y={104 - v * 78} textAnchor="end" fill="#8191a7" fontSize="9">{v}</text></g>)}
    {feature.chart.curves.map((curve, i) => <polyline key={curve.term} fill="none" stroke={colors[i]} strokeWidth="2" points={curve.degrees.map((degree, j) => `${28 + feature.chart.positions[j] * 314},${100 - degree * 78}`).join(' ')} />)}
    {position !== undefined && <g><line x1={28 + position * 314} x2={28 + position * 314} y1="14" y2="103" stroke="#f4f8fd" strokeDasharray="4 3" /><circle cx={28 + position * 314} cy="104" r="3" fill="#f4f8fd" /></g>}
    <text x="28" y="121" fill="#8191a7" fontSize="9">0</text><text x="342" y="121" fill="#8191a7" textAnchor="end" fontSize="9">{nf.format(feature.chart.values.at(-1) ?? 0)} {feature.unit}</text>
  </svg>)
}
export function ScoreGauge({ result }: { result: Analysis | null }) {
  const score = result?.risk_score ?? null
  return (<div className={`gauge-wrap ${result?.risk_level?.toLowerCase() ?? ''}`}>
    <svg viewBox="0 0 300 178" className="risk-gauge" role="img" aria-label={score === null ? 'No risk score yet' : `Risk score ${nf.format(score)} / 100`}>
      <path d="M35 145 A115 115 0 0 1 265 145" fill="none" stroke="#243142" strokeWidth="14" strokeLinecap="round" />
      <path d="M35 145 A115 115 0 0 1 265 145" fill="none" stroke="currentColor" strokeWidth="14" strokeLinecap="round" pathLength="100" strokeDasharray={`${score ?? 0} 100`} />
      <text x="150" y="115" textAnchor="middle" className="gauge-number">{score === null ? '—' : formatFixed(score, 2)}</text><text x="150" y="137" textAnchor="middle" className="gauge-caption">RISK SCORE / 100</text>
      <text x="29" y="170" className="gauge-tick">0</text><text x="253" y="170" className="gauge-tick">100</text>
    </svg>
    <div className="gauge-status">{result?.risk_level ? <Badge level={result.risk_level} /> : <span className="muted">Waiting for analysis</span>}</div>
  </div>)
}
export function ResultPanel({ result, busy, selectedPolicy, data, invalid }: { result: Analysis | null; busy: boolean; selectedPolicy: PolicyID; data: AppData; invalid: boolean }) {
  const policy = data.policies.find(p => p.id === selectedPolicy)!
  return (<Card className="result-card"><div className="card-heading"><div className="heading-icon"><Gauge size={18} /></div><h2>Risk assessment</h2><span className="tiny-label">MAMDANI</span></div>
    <div className={busy ? 'result-content pending' : 'result-content'} aria-busy={busy} aria-live="polite">
      <ScoreGauge result={busy ? null : result} />
      <div className="risk-bands" aria-label="Risk category intervals">{(['Low', 'Medium', 'High', 'Critical'] as Level[]).map((level, i) => <div className={level.toLowerCase()} key={level}><b>{levels[level]}</b><span>[{i === 0 ? 0 : data.model.risk_category_cuts[i - 1]}, {i === 3 ? 100 : data.model.risk_category_cuts[i]}{i === 3 ? ']' : ')'}</span></div>)}</div>
      {busy && <div className="computing"><LoaderCircle size={16} className="spin" /> Analyzing…</div>}
      {result?.status === 'ok' && !busy ? <>
        <div className={`alert-decision ${result.alert ? 'raised' : 'quiet'}`}><div>{result.alert ? <ShieldAlert size={21} /> : <Shield size={21} />}<span><b>{result.alert ? 'Alert raised' : 'No alert raised'}</b><small>{policy.title} policy · threshold {nf.format(result.alert_policy.threshold)}</small></span></div><span className="decision-symbol">{result.alert ? '!' : <Check size={17} />}</span></div>
        <p className="score-note">A risk score is not an attack probability.</p>
        <div className="result-stats"><div><strong>{result.activated_rules.length}<small> / {data.model.rule_count}</small></strong><span>active rules</span></div><div><strong>5<span className="cyan-dot" /></strong><span>evaluated inputs</span></div></div>
        <div className="compact-explanation"><GitBranch size={16} /><p>Dominant rules: {result.activated_rules.slice(0, 3).map(rule => rule.id).join(' · ')}</p></div>
        {result.explanation_data.outside_training_range.length > 0 && <p className="range-warning"><TriangleAlert size={14} />{result.explanation_data.outside_training_range.length} inputs are outside the training range. Shoulder memberships are saturated; this alone is not an error or proof of attack.</p>}
      </> : !busy && <div className="empty-result"><ScanLine size={28} /><h3>{invalid || result?.status === 'invalid_input' ? 'Insufficient valid data' : 'Explore the flow’s behavior'}</h3><p>{invalid || result ? 'The system abstained from scoring and alerting. Check the inputs.' : 'Enter measurements or select a traffic record.'}</p></div>}
    </div><div className="result-footer"><span className="status-dot" />Model<span className="mono">{data.model.model_id.slice(0, 8)}</span></div>
  </Card>)
}
export function Evidence({ result, data, idPrefix = "" }: { result: Analysis | null; data: AppData; idPrefix?: string }) {
  const [tab, setTab] = useState('memberships')
  function tabKeys(event: React.KeyboardEvent) {
    const ids = ['memberships', 'rules', 'pipeline']; const current = ids.indexOf(tab)
    const next = event.key === 'ArrowRight' ? ids[(current + 1) % 3] : event.key === 'ArrowLeft' ? ids[(current + 2) % 3] : event.key === 'Home' ? ids[0] : event.key === 'End' ? ids[2] : null
    if (next) { event.preventDefault(); setTab(next); document.getElementById(`${idPrefix}tab-${next}`)?.focus() }
  }
  return (<Card className="evidence"><div className="card-heading"><div className="heading-icon"><GitBranch size={18} /></div><h2>Rule and membership analysis</h2><span className="tiny-label">EXPLAINABLE INFERENCE</span></div>
    <div className="tabs" role="tablist" aria-label="Inference details">{[['memberships', 'Membership degrees'], ['rules', `Active rules${result?.status === 'ok' ? ` (${result.activated_rules.length})` : ''}`], ['pipeline', 'Processing stages']].map(([id, title]) => <button key={id} role="tab" id={`${idPrefix}tab-${id}`} tabIndex={tab === id ? 0 : -1} onKeyDown={tabKeys} aria-selected={tab === id} aria-controls={`${idPrefix}panel-${id}`} onClick={() => setTab(id)}>{title}</button>)}</div>
    <div role="tabpanel" id={`${idPrefix}panel-${tab}`} aria-labelledby={`${idPrefix}tab-${tab}`} className="evidence-body">
      {tab === 'memberships' && <><div className="membership-grid">{data.model.features.map(feature => <div className="membership-box" key={feature.key}>
        <div className="membership-heading"><h3>{feature.title}</h3><span className="mono">{result?.status === 'ok' ? nf.format(result.input_values[feature.column] as number) : '—'} <small>{feature.unit}</small></span></div>
        <MembershipChart feature={feature} position={result?.input_positions?.[feature.column]} />
        <div className="degree-list">{feature.chart.curves.map((curve, i) => { const degree = result?.membership_degrees?.[feature.column]?.[curve.term]; return <div className={`degree degree-${i}`} key={curve.term}><span>{curve.title}</span><div className="degree-track"><i style={{ width: `${(degree ?? 0) * 100}%` }} /></div><b title={degree?.toPrecision(15)}>{degree === undefined ? '—' : degreeText(degree)}</b></div> })}</div>
        <small className="axis-note">{feature.chart.axis_label} · white line: observed value</small></div>)}</div></>}
      {tab === 'rules' && <>{result?.status === 'ok' ? <><div className="rule-summary"><span><Zap size={15} />{result.activated_rules.length} rules activated</span><span>Sorted by activation strength</span></div><div className="rule-list">{[...result.activated_rules].sort((a, b) => b.strength - a.strength || a.id.localeCompare(b.id)).map(rule => <div className="rule-row" key={rule.id}><span className="rule-id">{rule.id}</span><div className="rule-description"><p>{rule.text}</p><small>{rule.strength >= .5 ? 'Strong activation' : rule.strength < .1 ? 'Weak activation' : 'Partial activation'}</small></div><div className="rule-strength"><b>{degreeText(rule.strength)}</b><div><i style={{ width: `${rule.strength * 100}%` }} /></div></div><Badge level={rule.consequent} /></div>)}</div></> : <div className="inline-empty">Analyze a flow first to inspect rules.</div>}</>}
      {tab === 'pipeline' && <><StepPipeline /><div className="learning-copy"><p>AND: minimum · OR: maximum · Aggregation: maximum · Defuzzification: centroid</p></div></>}
    </div></Card>)
}
