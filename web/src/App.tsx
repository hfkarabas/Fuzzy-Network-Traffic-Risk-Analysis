import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Activity, ArrowDownUp, ArrowRight, BookOpen, Check, ChevronDown, ChevronRight, CircleHelp, Database, FlaskConical, Gauge, GitBranch, LayoutDashboard, ListFilter, LoaderCircle, Network, Play, RotateCcw, ScanLine, Shield, ShieldAlert, SlidersHorizontal, Terminal, TrendingUp, TriangleAlert, X, Zap } from 'lucide-react'
import { analyze, ApiError, loadData } from './api'
import { formatNumber, formatFixed, LOCALE } from './format'
import LiveTraffic from './LiveTraffic'
import DatasetInformation from './DatasetInformation'
import { Badge, Card, StepPipeline, MembershipChart, ResultPanel, Evidence } from './components/FuzzyAnalysis'
import OutputVisualization from './components/OutputVisualization'
import type { Analysis, AppData, Confusion, Evaluation, Example, Feature, Flow, Level, Metrics, PolicyID } from './types'

const levels: Record<Level, string> = { Low: 'Low', Medium: 'Medium', High: 'High', Critical: 'Critical' }
const days: Record<string, string> = { Monday: 'Monday', Tuesday: 'Tuesday', Wednesday: 'Wednesday', Thursday: 'Thursday', Friday: 'Friday' }
const pages = [
  { id: 'live', title: 'Live Traffic', icon: Network },
  { id: 'overview', title: 'Security Overview', icon: LayoutDashboard }, { id: 'analysis', title: 'Risk Analysis', icon: Activity },
  { id: 'examples', title: 'Recorded Traffic', icon: Database }, { id: 'evaluation', title: 'Model Performance', icon: TrendingUp }, { id: 'about', title: 'System Information', icon: BookOpen }, { id: 'dataset', title: 'Dataset Information', icon: Database },
]
const nf = { format: formatNumber }
const percent = (v: number) => `${new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 3 }).format(v * 100)}%`
function EvaluationPage({ evaluation }: { evaluation: Evaluation }) {
  const [scenario, setScenario] = useState('grouped'); const [policy, setPolicy] = useState<PolicyID>('Balanced')
  const historic = evaluation.historical.find(h => h.id === scenario)
  const internal = evaluation.internal.find(i => i.id === policy)!
  const metrics: Metrics = historic?.metrics ?? internal.metrics
  const confusion: Confusion = historic?.confusion ?? internal.confusion
  const names: Record<string, string> = { grouped: 'Grouped evaluation', day: 'Day-based evaluation', internal: 'Internal validation' }
  const metricNames: [keyof Metrics, string][] = [['precision', 'Precision'], ['recall', 'Recall'], ['false_positive_rate', 'False-positive rate (FPR)'], ['false_negative_rate', 'False-negative rate (FNR)'], ['balanced_accuracy', 'Balanced accuracy'], ['roc_auc', 'ROC-AUC'], ['f1', 'F1 skoru'], ['pr_auc_average_precision', 'PR-AUC (AP)']]
  return (<><div className="page-title"><h1>Model Performance</h1><p>Recorded evaluations; not verified live-deployment performance.</p></div>
    <div className="scenario-selector" aria-label="Evaluation scenario">{[...evaluation.historical.map(h => h.id), 'internal'].map(id => <button key={id} aria-pressed={scenario === id} className={scenario === id ? 'selected' : ''} onClick={() => setScenario(id)}>{names[id] ?? id}</button>)}</div>
    <Card className="evaluation-context"><div><span className="scope-tag">{historic ? 'RECORDED TEST' : 'INTERNAL VALIDATION · NOT INDEPENDENT TESTING'}</span><h2>{names[scenario] ?? scenario}</h2><small>{historic ? 'Flow-weighted results' : 'Group-weighted results · three-fold mean'}</small></div>{historic ? <div className="eval-threshold"><small>Recorded alert threshold</small><b>{historic.metrics.threshold}</b><span>{nf.format(historic.metrics.rows ?? 0)} flows</span></div> : <label className="select-label">Recorded policy<select value={policy} onChange={e => setPolicy(e.target.value as PolicyID)}><option value="Sensitive">Sensitive</option><option value="Balanced">Balanced</option><option value="Conservative">Conservative</option></select></label>}</Card>
    <div className="metric-grid">{metricNames.map(([key, title]) => <Card key={key}><small>{title}</small><strong className={key === 'false_positive_rate' || key === 'false_negative_rate' ? 'amber-text' : ''}>{key === 'roc_auc' || key === 'f1' || key === 'pr_auc_average_precision' ? formatFixed(metrics[key] ?? 0, 4) : percent(metrics[key] ?? 0)}</strong></Card>)}</div>
    {!historic && <div className="important-note"><TriangleAlert size={20} /><div><b>Group-weighted and flow-weighted rates are different.</b><p>Flow-weighted FPR: <strong>{percent(internal.pooled_row_fpr)}</strong> · Recall: <strong>{percent(internal.pooled_row_recall)}</strong>. Separate thresholds were applied per fold.</p></div></div>}
    <div className="evaluation-bottom"><Card><div className="card-heading"><h2>Confusion matrix</h2><span className="tiny-label">RAW FLOW COUNTS</span></div><div className="matrix"><span /><span>No alert</span><span>Alert</span><span>BENIGN</span><div className="tn"><small>True negative</small><b>{nf.format(confusion.tn)}</b></div><div className="fp"><small>False positive</small><b>{nf.format(confusion.fp)}</b></div><span>Attack</span><div className="fn"><small>False negative</small><b>{nf.format(confusion.fn)}</b></div><div className="tp"><small>True positive</small><b>{nf.format(confusion.tp)}</b></div></div><p className="footnote">{historic ? 'Flow-weighted results' : 'Pooled raw flow counts using fold-specific thresholds'}</p></Card><Card className="limitations"><div className="card-heading"><h2>Evaluation scope</h2></div><div className="limitation"><p>Recorded results do not establish live capture performance.</p></div><div className="limitation"><p>Traffic distribution, scenario shifts and record dependencies affect these results.</p></div><div className="limitation"><p>Group-weighted rates should not be directly compared with the raw flow matrix.</p></div></Card></div>
    <a className="text-button evaluation-method-link" href="#dataset">Dataset and methodology <ArrowRight size={15} /></a>
  </>)
}
export default function App() {
  const [page, setPage] = useState(() => location.hash.slice(1) || 'analysis')
  const [data, setData] = useState<AppData | null>(null); const [startupError, setStartupError] = useState(''); const [reload, setReload] = useState(0)
  const [fields, setFields] = useState<Record<string, string>>({}); const [policy, setPolicy] = useState<PolicyID>('Balanced')
  const [result, setResult] = useState<Analysis | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [errors, setErrors] = useState<Record<string, string>>({})
  const [source, setSource] = useState<Example | null>(null); const [exampleFilter, setExampleFilter] = useState('all'); const [mobileMenu, setMobileMenu] = useState(false)
  const request = useRef<AbortController | null>(null); const sequence = useRef(0)
  useEffect(() => { const listener = () => setPage(location.hash.slice(1) || 'analysis'); window.addEventListener('hashchange', listener); return () => window.removeEventListener('hashchange', listener) }, [])
  useEffect(() => {
    if (!mobileMenu) return
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setMobileMenu(false); document.getElementById('mobile-menu-toggle')?.focus() } }
    window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close)
  }, [mobileMenu])
  function navigate(id: string) { location.hash = id; setPage(id); setMobileMenu(false); window.scrollTo({ top: 0, behavior: 'instant' }) }
  async function run(values: Record<string, string>, selected: PolicyID) {
    if (!data) return
    const nextErrors: Record<string, string> = {}; const flow: Flow = {}
    for (const f of data.model.features) { const raw = values[f.column]?.trim() ?? ''; const value = raw === '' ? NaN : Number(raw); if (!Number.isFinite(value) || value < 0) nextErrors[f.column] = 'Enter a finite, nonnegative number.'; flow[f.column] = value }
    setErrors(nextErrors); setError(''); setResult(null)
    if (Object.keys(nextErrors).length) { setError('Check the inputs. No risk score was produced.'); return }
    request.current?.abort(); request.current = new AbortController(); const id = ++sequence.current; setBusy(true)
    try { const response = await analyze(flow, selected, request.current.signal); if (id === sequence.current) setResult(response) }
    catch (e) { if ((e as Error).name !== 'AbortError' && id === sequence.current) setError(e instanceof ApiError ? [e.message, ...e.details].join(' ') : 'Analysis failed. Try again.') }
    finally { if (id === sequence.current) setBusy(false) }
  }
  useEffect(() => {
    const controller = new AbortController(); setStartupError('')
    loadData(controller.signal).then(async loaded => {
      if (controller.signal.aborted) return
      setData(loaded); const first = loaded.examples.find(e => e.id === 'policy-contrast') ?? loaded.examples.find(e => e.id === 'high') ?? loaded.examples[0]
      if (first) {
        const values = Object.fromEntries(Object.entries(first.features).map(([key, value]) => [key, String(value ?? '')])); setFields(values); setSource(first)
        setBusy(true)
        try { const response = await analyze(first.features, 'Balanced', controller.signal); if (!controller.signal.aborted) setResult(response) }
        catch (e) { if (!controller.signal.aborted) setError((e as Error).message) }
        finally { if (!controller.signal.aborted) setBusy(false) }
      }
    }).catch(e => { if (!controller.signal.aborted) setStartupError((e as Error).message) })
    return () => { controller.abort(); request.current?.abort() }
  }, [reload])
  function loadExample(example: Example) { const values = Object.fromEntries(Object.entries(example.features).map(([key, v]) => [key, String(v ?? '')])); setFields(values); setSource(example); setErrors({}); navigate('analysis'); void run(values, policy) }
  function reset() { request.current?.abort(); sequence.current++; setBusy(false); setFields({}); setSource(null); setResult(null); setError(''); setErrors({}) }
  function switchPolicy(next: PolicyID) { setPolicy(next); if (result?.status === 'ok') void run(fields, next) }
  const activePage = pages.find(p => p.id === page) ?? pages.find(p => p.id === 'analysis')!
  return (<div className="app-shell"><a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus() }}>Skip to content</a>
    <aside id="primary-sidebar" className={`sidebar ${mobileMenu ? 'open' : ''}`}><a className="brand" href="#overview" onClick={() => navigate('overview')}><div className="brand-mark"><Network size={25} /></div><div>FUZZY<span>NETWORK SECURITY</span></div></a>
      <div className="nav-label">WORKSPACE</div><nav aria-label="Main navigation">{pages.map(p => { const Icon = p.icon; return <a key={p.id} href={`#${p.id}`} aria-current={activePage.id === p.id ? 'page' : undefined} className={activePage.id === p.id ? 'active' : ''} onClick={() => navigate(p.id)}><Icon size={18} /><span>{p.title}</span>{activePage.id === p.id && <ChevronRight size={14} />}</a> })}</nav>
      <div className="sidebar-model"><span>RISK ENGINE</span><b>Mamdani FIS</b><p>5 inputs <i /> 22 rules <i /> 1 output</p><div className="model-loaded"><span className={`status-dot ${startupError ? 'offline' : ''}`} />{data ? 'Analysis engine ready' : startupError ? 'Connection failed' : 'Loading model'}</div></div>
          </aside>{mobileMenu && <button className="menu-backdrop" aria-label="Close menu" onClick={() => setMobileMenu(false)} />}
    <div className="main-shell"><header className="topbar"><button id="mobile-menu-toggle" className="mobile-toggle icon-button" aria-label={mobileMenu ? 'Close navigation menu' : 'Open menu'} aria-expanded={mobileMenu} aria-controls="primary-sidebar" onClick={() => setMobileMenu(!mobileMenu)}>{mobileMenu ? <X size={20} /> : <ListFilter size={20} />}</button><div className="breadcrumb">Network Security <ChevronRight size={13} /><b>{activePage.title}</b></div><div className="topbar-right"><span className="service-status"><span className={`status-dot ${startupError ? 'offline' : ''}`} />{data ? 'Analysis engine ready' : startupError ? 'Service unavailable' : 'Loading service'}</span></div></header>
      <main id="main-content" tabIndex={-1}>
        {startupError ? <div className="startup-error" role="alert"><TriangleAlert size={35} /><h1>Cannot connect to the local server</h1><p>{startupError}</p><button className="primary-button" onClick={() => setReload(r => r + 1)}>Try again</button><small>Start FastAPI at 127.0.0.1:8000.</small></div> : !data ? <div className="startup-loading" role="status"><LoaderCircle className="spin" size={28} /><p>Loading the model and local workspace…</p></div> : <>
          {activePage.id === 'live' && <LiveTraffic data={data} />}
          {activePage.id === 'dataset' && <DatasetInformation data={data} />}
          {activePage.id === 'analysis' && <>
            <div className="page-title analysis-title"><h1>Risk Analysis</h1></div>
            <div className="analysis-grid"><Card className="input-card"><div className="card-heading"><div className="heading-icon"><SlidersHorizontal size={18} /></div><h2>Flow parameters</h2><span className="tiny-label">FLOW INPUTS</span></div>
              <form noValidate onSubmit={(e: FormEvent) => { e.preventDefault(); void run(fields, policy) }}>
                <div className="example-loader"><span><Database size={15} />Select a traffic record</span><select aria-label="Select an example flow" disabled={busy} value={source?.id ?? ''} onChange={e => { const chosen = data.examples.find(x => x.id === e.target.value); if (chosen) loadExample(chosen) }}><option value="">Select an example</option>{data.examples.map(example => <option value={example.id} key={example.id}>{example.title}</option>)}</select><ChevronDown size={13} /></div>
                <div className="input-grid">{data.model.features.map((f, i) => <div className={`field field-${i}`} key={f.key}><label htmlFor={`input-${f.key}`}>{f.title}<details><summary aria-label={`${f.title} information`}><CircleHelp size={13} /></summary><div><b>{f.unit}</b><p>{f.description}</p></div></details></label><div className={`input-wrap ${errors[f.column] ? 'invalid' : ''}`}><input id={`input-${f.key}`} type="number" inputMode="decimal" min="0" step="any" disabled={busy} value={fields[f.column] ?? ''} placeholder="Enter a value" aria-invalid={!!errors[f.column]} aria-describedby={`help-${f.key}`} onChange={e => { setFields(old => ({ ...old, [f.column]: e.target.value })); setSource(null); setResult(null); setErrors({}); setError('') }} /><span>{f.symbol}</span></div><small id={`help-${f.key}`} className={errors[f.column] ? 'field-error' : ''}>{errors[f.column] ?? f.description}</small></div>)}</div>
                <div className="policy-header"><label>Alert policy</label><span>The score stays the same; the threshold changes.</span></div><div className="policy-options" role="group" aria-label="Alert policy">{data.policies.map(p => <button key={p.id} type="button" disabled={busy} aria-pressed={policy === p.id} className={policy === p.id ? 'selected' : ''} onClick={() => switchPolicy(p.id)}>{p.id === 'Sensitive' ? <Zap size={14} /> : p.id === 'Balanced' ? <SlidersHorizontal size={14} /> : <Shield size={14} />}{p.title}</button>)}</div><p className="policy-description">{data.policies.find(p => p.id === policy)?.description} Threshold: <b>{nf.format(data.policies.find(p => p.id === policy)!.threshold)}</b>.</p>
                {source && <div className="loaded-source"><span className="status-dot" /><span>Record ID <span className="mono">{source.source_row_id}</span></span><span>Label: <b>{source.dataset_label}</b></span></div>}
                {error && <div className="form-error" role="alert"><TriangleAlert size={16} /><span>{error}</span></div>}
                <div className="form-actions"><button type="submit" className="primary-button" disabled={busy}>{busy ? <LoaderCircle size={17} className="spin" /> : <Play size={16} fill="currentColor" />}{busy ? 'Evaluating…' : 'Analyze flow'}<ArrowRight size={17} /></button><button type="button" className="reset-button" onClick={reset} disabled={busy} aria-label="Reset form"><RotateCcw size={17} />Reset</button></div>
                <p className="local-note"><Shield size={12} />Measurements are processed only by the local Python server.</p>
              </form></Card><ResultPanel result={result} busy={busy} selectedPolicy={policy} data={data} invalid={Object.keys(errors).length > 0} /></div>
            <Evidence result={busy ? null : result} data={data} /><OutputVisualization result={busy ? null : result} />
          </>}
          {activePage.id === 'overview' && <><div className="page-title"><h1>Security Overview</h1><p>Analysis engine and traffic records</p></div><div className="overview-stats">{[[String(data.model.features.length), 'Input measurements', SlidersHorizontal], [String(data.model.rule_count), 'Risk rules', GitBranch], [String(data.policies.length), 'Alert policy', Shield], [String(data.examples.length), 'Traffic records', Database]].map(([number, label, Icon]) => { const I = Icon as typeof Database; return <Card key={String(label)}><I size={21} /><strong>{String(number)}</strong><span>{String(label)}</span></Card> })}</div><div className="overview-links"><Card><Network size={24} /><h2>Live Traffic</h2><p>Select an interface and start authorized monitoring.</p><button className="primary-button" onClick={() => navigate('live')}>Open monitoring <ArrowRight size={16} /></button></Card><Card><Database size={24} /><h2>Recorded Traffic</h2><p>Inspect recorded flows, risk scores, measurements and rules.</p><button className="text-button" onClick={() => navigate('examples')}>Open traffic records <ArrowRight size={16} /></button></Card></div></>}
          {activePage.id === 'examples' && <><div className="page-title"><h1>Recorded Traffic</h1><p>Analyses selected from recorded traffic samples.</p></div><div className="example-filters" role="group" aria-label="Example filter">{[['all', 'All examples'], ['benign', 'BENIGN'], ['attack', 'Attack-labeled'], ['error', 'Incorrect decisions']].map(([id, title]) => <button aria-pressed={exampleFilter === id} className={exampleFilter === id ? 'selected' : ''} key={id} onClick={() => setExampleFilter(id)}>{title}</button>)}</div><div className="example-grid">{data.examples.filter(e => exampleFilter === 'all' || (exampleFilter === 'benign' ? e.dataset_label === 'BENIGN' : exampleFilter === 'attack' ? e.dataset_label !== 'BENIGN' : e.id.startsWith('false-'))).map(example => <Card className="example-card" key={example.id}><div className="example-card-top"><span className="mono">RECORD #{example.source_row_id}</span><Badge level={example.risk_level} /></div><h2>{example.title}</h2><div className="example-score">{nf.format(example.risk_score)}<span>/100</span></div><div className="example-label"><span>Recorded label</span><b>{example.dataset_label}</b></div><dl>{data.model.features.map(f => <div key={f.key}><dt>{f.title}</dt><dd>{nf.format(example.features[f.column] as number)} <small>{f.unit}</small></dd></div>)}</dl><div className="example-card-footer"><small>{days[example.source_day] ?? example.source_day} · {example.alert ? 'Alert' : 'No alert'}</small><button className="text-button" onClick={() => loadExample(example)}>Open in analysis <ArrowRight size={15} /></button></div></Card>)}</div></>}
          {activePage.id === 'evaluation' && <EvaluationPage evaluation={data.evaluation} />}
          {activePage.id === 'about' && <><div className="page-title"><h1>System Information</h1></div><div className="about-grid"><Card><div className="card-heading"><h2>Analysis configuration</h2></div><dl className="info-list"><div><dt>Inference</dt><dd>{data.model.method}</dd></div><div><dt>Inputs / rules</dt><dd>{data.model.features.length} / {data.model.rule_count}</dd></div><div><dt>Memberships</dt><dd>Triangular and trapezoidal</dd></div><div><dt>Defuzzification</dt><dd>{data.model.defuzzification}</dd></div><div><dt>Application version</dt><dd className="mono">{data.model.app_version}</dd></div><div><dt>Model version</dt><dd>{data.model.model_version}</dd></div><div><dt>Model identity</dt><dd className="mono truncate">{data.model.model_id}</dd></div></dl></Card><Card><div className="card-heading"><h2>Alert policies</h2></div><dl className="info-list">{data.policies.map(p => <div key={p.id}><dt>{p.title}</dt><dd>Threshold: {nf.format(p.threshold)}</dd></div>)}</dl><a className="text-button system-api-link" href="/docs" target="_blank" rel="noreferrer">Local API reference <ArrowRight size={16} /></a></Card></div><Card className="about-fuzzy"><div className="card-heading"><h2>Membership functions</h2></div><div className="about-chart"><MembershipChart feature={data.model.features[0]} /></div></Card><Card className="rule-inventory"><div className="card-heading"><h2>Rule inventory</h2><span className="tiny-label">{data.model.rule_count} rules</span></div>{data.model.rules.map(rule => <details key={rule.id}><summary><span className="rule-id">{rule.id}</span><span>{rule.conditions}</span><Badge level={rule.consequent} /></summary><p>{rule.text}</p></details>)}</Card></>}
        </>}
        <footer className="page-footer"><span><Network size={13} />FUZZY NETWORK SECURITY</span><span>Risk score · 0–100</span></footer>
      </main></div>
  </div>)
}
