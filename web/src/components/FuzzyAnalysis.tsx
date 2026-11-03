import { useI18n } from '../i18n'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Check, ChevronRight, Gauge, GitBranch, LoaderCircle, ScanLine, Shield, ShieldAlert, TriangleAlert, Zap } from 'lucide-react'
import type { Analysis, AppData, Feature, Level, PolicyID } from '../types'
import { formatNumber, formatFixed, locale } from '../format'
const nf = { format: formatNumber }
const levels: Record<Level, string> = { Low: 'Düşük', Medium: 'Orta', High: 'Yüksek', Critical: 'Kritik' }
const degreeText = (v: number) => v > 0 && v < .001 ? '<0,001' : formatFixed(v, 3)
export function Badge({ level }: { level: Level }) {
  const { localize } = useI18n()
 return localize(<span className={`badge ${level.toLowerCase()}`}><span />{levels[level]} risk</span>)
}
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  const { localize } = useI18n()
 return localize(<section className={`card ${className}`}>{children}</section>)
}
export function StepPipeline() {
  const { localize } = useI18n()

  const steps = [['01', 'Girdiler', 'Beş akış ölçümü'], ['02', 'Bulanıklaştırma', 'Dilsel kümelere üyelik'], ['03', 'Kurallar', 'Minimum ile etkinlik'], ['04', 'Birleştirme', 'Maksimum çıktı kümesi'], ['05', 'Durulaştırma', 'Ağırlık merkezi'], ['06', 'Risk puanı', '0–100 · dilsel seviye']]
  return localize(<div className="pipeline" aria-label="Bulanık çıkarım adımları">{steps.map(([n, title, body]) => <div className="step" key={n}><span className="step-no">{n}</span><div><b>{title}</b><small>{body}</small></div>{n !== '06' && <ChevronRight size={15} className="step-arrow" />}</div>)}</div>)
}
export function MembershipChart({ feature, position }: { feature: Feature; position?: number }) {
  const { localize } = useI18n()

  const colors = ['#4ed8cf', '#7da4ff', '#e0ad67']
  return localize(<svg className="membership-chart" viewBox="0 0 360 130" role="img" aria-label={`${feature.title}: sunucudan alınan üyelik fonksiyonları${position !== undefined ? ' ve mevcut değer' : ''}`}>
    {[0, .5, 1].map(v => <g key={v}><line x1="28" y1={100 - v * 78} x2="342" y2={100 - v * 78} stroke="#273345" strokeDasharray={v === .5 ? '3 4' : undefined} /><text x="18" y={104 - v * 78} textAnchor="end" fill="#8191a7" fontSize="9">{v}</text></g>)}
    {feature.chart.curves.map((curve, i) => <polyline key={curve.term} fill="none" stroke={colors[i]} strokeWidth="2" points={curve.degrees.map((degree, j) => `${28 + feature.chart.positions[j] * 314},${100 - degree * 78}`).join(' ')} />)}
    {position !== undefined && <g><line x1={28 + position * 314} x2={28 + position * 314} y1="14" y2="103" stroke="#f4f8fd" strokeDasharray="4 3" /><circle cx={28 + position * 314} cy="104" r="3" fill="#f4f8fd" /></g>}
    <text x="28" y="121" fill="#8191a7" fontSize="9">0</text><text x="342" y="121" fill="#8191a7" textAnchor="end" fontSize="9">{nf.format(feature.chart.values.at(-1) ?? 0)} {feature.unit}</text>
  </svg>)
}
export function ScoreGauge({ result }: { result: Analysis | null }) {
  const { localize } = useI18n()

  const score = result?.risk_score ?? null
  return localize(<div className={`gauge-wrap ${result?.risk_level?.toLowerCase() ?? ''}`}>
    <svg viewBox="0 0 300 178" className="risk-gauge" role="img" aria-label={score === null ? 'Henüz risk puanı yok' : `Risk puanı ${nf.format(score)} / 100`}>
      <path d="M35 145 A115 115 0 0 1 265 145" fill="none" stroke="#243142" strokeWidth="14" strokeLinecap="round" />
      <path d="M35 145 A115 115 0 0 1 265 145" fill="none" stroke="currentColor" strokeWidth="14" strokeLinecap="round" pathLength="100" strokeDasharray={`${score ?? 0} 100`} />
      <text x="150" y="115" textAnchor="middle" className="gauge-number">{score === null ? '—' : formatFixed(score, 2)}</text><text x="150" y="137" textAnchor="middle" className="gauge-caption">RİSK PUANI / 100</text>
      <text x="29" y="170" className="gauge-tick">0</text><text x="253" y="170" className="gauge-tick">100</text>
    </svg>
    <div className="gauge-status">{result?.risk_level ? <Badge level={result.risk_level} /> : <span className="muted">Analiz sonucu bekleniyor</span>}</div>
  </div>)
}
export function ResultPanel({ result, busy, selectedPolicy, data, invalid }: { result: Analysis | null; busy: boolean; selectedPolicy: PolicyID; data: AppData; invalid: boolean }) {
  const { localize } = useI18n()

  const policy = data.policies.find(p => p.id === selectedPolicy)!
  return localize(<Card className="result-card"><div className="card-heading"><div className="heading-icon"><Gauge size={18} /></div><h2>Risk değerlendirmesi</h2><span className="tiny-label">MAMDANI</span></div>
    <div className={busy ? 'result-content pending' : 'result-content'} aria-busy={busy} aria-live="polite">
      <ScoreGauge result={busy ? null : result} />
      <div className="risk-bands" aria-label="Risk kategorisi aralıkları">{(['Low', 'Medium', 'High', 'Critical'] as Level[]).map((level, i) => <div className={level.toLowerCase()} key={level}><b>{levels[level]}</b><span>[{i === 0 ? 0 : data.model.risk_category_cuts[i - 1]}, {i === 3 ? 100 : data.model.risk_category_cuts[i]}{i === 3 ? ']' : ')'}</span></div>)}</div>
      {busy && <div className="computing"><LoaderCircle size={16} className="spin" /> Analiz ediliyor…</div>}
      {result?.status === 'ok' && !busy ? <>
        <div className={`alert-decision ${result.alert ? 'raised' : 'quiet'}`}><div>{result.alert ? <ShieldAlert size={21} /> : <Shield size={21} />}<span><b>{result.alert ? 'Alarm üretildi' : 'Alarm üretilmedi'}</b><small>{policy.title} politika · eşik {nf.format(result.alert_policy.threshold)}</small></span></div><span className="decision-symbol">{result.alert ? '!' : <Check size={17} />}</span></div>
        <p className="score-note">Risk puanı saldırı olasılığı değildir.</p>
        <div className="result-stats"><div><strong>{result.activated_rules.length}<small> / {data.model.rule_count}</small></strong><span>etkin kural</span></div><div><strong>5<span className="cyan-dot" /></strong><span>değerlendirilen girdi</span></div></div>
        <div className="compact-explanation"><GitBranch size={16} /><p>Baskın kurallar: {result.activated_rules.slice(0, 3).map(rule => rule.id).join(' · ')}</p></div>
        {result.explanation_data.outside_training_range.length > 0 && <p className="range-warning"><TriangleAlert size={14} />{result.explanation_data.outside_training_range.length} girdi eğitim aralığı dışında. Omuz üyelikleri doyuruldu; bu tek başına hata veya saldırı değildir.</p>}
      </> : !busy && <div className="empty-result"><ScanLine size={28} /><h3>{invalid || result?.status === 'invalid_input' ? 'Yeterli geçerli veri yok' : 'Akışın davranışını görün'}</h3><p>{invalid || result ? 'Sistem puan ve alarm üretmekten kaçındı. Girdileri kontrol edin.' : 'Ölçümleri girin veya bir trafik kaydı seçin.'}</p></div>}
    </div><div className="result-footer"><span className="status-dot" />Model<span className="mono">{data.model.model_id.slice(0, 8)}</span></div>
  </Card>)
}
export function Evidence({ result, data, idPrefix = "" }: { result: Analysis | null; data: AppData; idPrefix?: string }) {
  const { localize } = useI18n()

  const [tab, setTab] = useState('memberships')
  function tabKeys(event: React.KeyboardEvent) {
    const ids = ['memberships', 'rules', 'pipeline']; const current = ids.indexOf(tab)
    const next = event.key === 'ArrowRight' ? ids[(current + 1) % 3] : event.key === 'ArrowLeft' ? ids[(current + 2) % 3] : event.key === 'Home' ? ids[0] : event.key === 'End' ? ids[2] : null
    if (next) { event.preventDefault(); setTab(next); document.getElementById(`${idPrefix}tab-${next}`)?.focus() }
  }
  return localize(<Card className="evidence"><div className="card-heading"><div className="heading-icon"><GitBranch size={18} /></div><h2>Kural ve üyelik analizi</h2><span className="tiny-label">AÇIKLANABİLİR ÇIKARIM</span></div>
    <div className="tabs" role="tablist" aria-label="Çıkarım ayrıntıları">{[['memberships', 'Üyelik dereceleri'], ['rules', `Etkin kurallar${result?.status === 'ok' ? ` (${result.activated_rules.length})` : ''}`], ['pipeline', 'İşlem akışı']].map(([id, title]) => <button key={id} role="tab" id={`${idPrefix}tab-${id}`} tabIndex={tab === id ? 0 : -1} onKeyDown={tabKeys} aria-selected={tab === id} aria-controls={`${idPrefix}panel-${id}`} onClick={() => setTab(id)}>{title}</button>)}</div>
    <div role="tabpanel" id={`${idPrefix}panel-${tab}`} aria-labelledby={`${idPrefix}tab-${tab}`} className="evidence-body">
      {tab === 'memberships' && <><div className="membership-grid">{data.model.features.map(feature => <div className="membership-box" key={feature.key}>
        <div className="membership-heading"><h3>{feature.title}</h3><span className="mono">{result?.status === 'ok' ? nf.format(result.input_values[feature.column] as number) : '—'} <small>{feature.unit}</small></span></div>
        <MembershipChart feature={feature} position={result?.input_positions?.[feature.column]} />
        <div className="degree-list">{feature.chart.curves.map((curve, i) => { const degree = result?.membership_degrees?.[feature.column]?.[curve.term]; return <div className={`degree degree-${i}`} key={curve.term}><span>{curve.title}</span><div className="degree-track"><i style={{ width: `${(degree ?? 0) * 100}%` }} /></div><b title={degree?.toPrecision(15)}>{degree === undefined ? '—' : degreeText(degree)}</b></div> })}</div>
        <small className="axis-note">{feature.chart.axis_label} · beyaz çizgi: mevcut değer</small></div>)}</div></>}
      {tab === 'rules' && <>{result?.status === 'ok' ? <><div className="rule-summary"><span><Zap size={15} />{result.activated_rules.length} kural etkin</span><span>Etkinlik gücüne göre sıralı</span></div><div className="rule-list">{[...result.activated_rules].sort((a, b) => b.strength - a.strength || a.id.localeCompare(b.id)).map(rule => <div className="rule-row" key={rule.id}><span className="rule-id">{rule.id}</span><div className="rule-description"><p>{rule.text_tr}</p><small>{rule.strength >= .5 ? 'Güçlü etkinlik' : rule.strength < .1 ? 'Zayıf etkinlik' : 'Kısmi etkinlik'}</small></div><div className="rule-strength"><b>{degreeText(rule.strength)}</b><div><i style={{ width: `${rule.strength * 100}%` }} /></div></div><Badge level={rule.consequent} /></div>)}</div></> : <div className="inline-empty">Kuralları incelemek için önce bir akış analiz edin.</div>}</>}
      {tab === 'pipeline' && <><StepPipeline /><div className="learning-copy"><p>AND: minimum · OR: maksimum · Birleştirme: maksimum · Durulaştırma: ağırlık merkezi</p></div></>}
    </div></Card>)
}
