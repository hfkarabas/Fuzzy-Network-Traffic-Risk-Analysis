import { LanguageSwitcher, useI18n } from './i18n'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Activity, ArrowDownUp, ArrowRight, BookOpen, Check, ChevronDown, ChevronRight, CircleHelp, Database, FlaskConical, Gauge, GitBranch, LayoutDashboard, ListFilter, LoaderCircle, Network, Play, RotateCcw, ScanLine, Shield, ShieldAlert, SlidersHorizontal, Terminal, TrendingUp, TriangleAlert, X, Zap } from 'lucide-react'
import { analyze, ApiError, loadData } from './api'
import { formatNumber, formatFixed, locale } from './format'
import LiveTraffic from './LiveTraffic'
import { Badge, Card, StepPipeline, MembershipChart, ResultPanel, Evidence } from './components/FuzzyAnalysis'
import OutputVisualization from './components/OutputVisualization'
import type { Analysis, AppData, Confusion, Evaluation, Example, Feature, Flow, Level, Metrics, PolicyID } from './types'

const levels: Record<Level, string> = { Low: 'Düşük', Medium: 'Orta', High: 'Yüksek', Critical: 'Kritik' }
const days: Record<string, string> = { Monday: 'Pazartesi', Tuesday: 'Salı', Wednesday: 'Çarşamba', Thursday: 'Perşembe', Friday: 'Cuma' }
const pages = [
  { id: 'live', title: 'Canlı Trafik', icon: Network },
  { id: 'overview', title: 'Güvenlik Özeti', icon: LayoutDashboard }, { id: 'analysis', title: 'Risk Analizi', icon: Activity },
  { id: 'examples', title: 'Kayıtlı Trafik', icon: Database }, { id: 'evaluation', title: 'Model Performansı', icon: TrendingUp }, { id: 'about', title: 'Sistem Bilgileri', icon: BookOpen },
]
const nf = { format: formatNumber }
const percent = (v: number) => `${new Intl.NumberFormat(locale(), { maximumFractionDigits: 3 }).format(v * 100)}%`
function EvaluationPage({ evaluation }: { evaluation: Evaluation }) {
  const { localize } = useI18n()
  const [scenario, setScenario] = useState('grouped'); const [policy, setPolicy] = useState<PolicyID>('Balanced')
  const historic = evaluation.historical.find(h => h.id === scenario)
  const internal = evaluation.internal.find(i => i.id === policy)!
  const metrics: Metrics = historic?.metrics ?? internal.metrics
  const confusion: Confusion = historic?.confusion ?? internal.confusion
  const names: Record<string, string> = { grouped: 'Gruplu değerlendirme', day: 'Gün bazlı değerlendirme', internal: 'İç doğrulama' }
  const metricNames: [keyof Metrics, string][] = [['precision', 'Kesinlik'], ['recall', 'Duyarlılık'], ['false_positive_rate', 'Yanlış alarm (FPR)'], ['false_negative_rate', 'Kaçırma (FNR)'], ['balanced_accuracy', 'Dengeli doğruluk'], ['roc_auc', 'ROC-AUC'], ['f1', 'F1 skoru'], ['pr_auc_average_precision', 'PR-AUC (AP)']]
  return localize(<><div className="page-title"><h1>Model Performansı</h1><p>Kayıtlı değerlendirmeler; canlı ortam başarısını göstermez.</p></div>
    <div className="scenario-selector" aria-label="Değerlendirme senaryosu">{[...evaluation.historical.map(h => h.id), 'internal'].map(id => <button key={id} aria-pressed={scenario === id} className={scenario === id ? 'selected' : ''} onClick={() => setScenario(id)}>{names[id] ?? id}</button>)}</div>
    <Card className="evaluation-context"><div><span className="scope-tag">{historic ? 'KAYITLI TEST' : 'İÇ DOĞRULAMA · BAĞIMSIZ TEST DEĞİL'}</span><h2>{names[scenario] ?? scenario}</h2><small>{historic ? 'Akış ağırlıklı sonuçlar' : 'Grup ağırlıklı sonuçlar · üç kat ortalaması'}</small></div>{historic ? <div className="eval-threshold"><small>Kaydedilmiş alarm eşiği</small><b>{historic.metrics.threshold}</b><span>{nf.format(historic.metrics.rows ?? 0)} akış</span></div> : <label className="select-label">Kayıtlı politika<select value={policy} onChange={e => setPolicy(e.target.value as PolicyID)}><option value="Sensitive">Hassas</option><option value="Balanced">Dengeli</option><option value="Conservative">Temkinli</option></select></label>}</Card>
    <div className="metric-grid">{metricNames.map(([key, title]) => <Card key={key}><small>{title}</small><strong className={key === 'false_positive_rate' || key === 'false_negative_rate' ? 'amber-text' : ''}>{key === 'roc_auc' || key === 'f1' || key === 'pr_auc_average_precision' ? formatFixed(metrics[key] ?? 0, 4) : percent(metrics[key] ?? 0)}</strong></Card>)}</div>
    {!historic && <div className="important-note"><TriangleAlert size={20} /><div><b>Grup ağırlıklı oran ile akış bazındaki oran aynı değildir.</b><p>Akış bazlı FPR: <strong>{percent(internal.pooled_row_fpr)}</strong> · Duyarlılık: <strong>{percent(internal.pooled_row_recall)}</strong>. Katlara ayrı eşikler uygulanmıştır.</p></div></div>}
    <div className="evaluation-bottom"><Card><div className="card-heading"><h2>Karışıklık matrisi</h2><span className="tiny-label">HAM AKIŞ SAYILARI</span></div><div className="matrix"><span /><span>Alarm yok</span><span>Alarm var</span><span>BENIGN</span><div className="tn"><small>Doğru negatif</small><b>{nf.format(confusion.tn)}</b></div><div className="fp"><small>Yanlış pozitif</small><b>{nf.format(confusion.fp)}</b></div><span>Saldırı</span><div className="fn"><small>Yanlış negatif</small><b>{nf.format(confusion.fn)}</b></div><div className="tp"><small>Doğru pozitif</small><b>{nf.format(confusion.tp)}</b></div></div><p className="footnote">{historic ? 'Akış ağırlıklı sonuçlar' : 'Kat eşikleriyle birleştirilmiş ham akış sayıları'}</p></Card><Card className="limitations"><div className="card-heading"><h2>Değerlendirme kapsamı</h2></div><div className="limitation"><p>Kayıtlı sonuçlar canlı yakalama performansını doğrulamaz.</p></div><div className="limitation"><p>Trafik dağılımı, senaryo değişimi ve kayıt bağımlılıkları sonuçları etkiler.</p></div><div className="limitation"><p>Grup ağırlıklı oranlar ham akış matrisiyle doğrudan karşılaştırılmamalıdır.</p></div></Card></div>
    {evaluation.optimization && <details className="card model-comparison"><summary>Kayıtlı model karşılaştırması</summary><p className="footnote">Grup ağırlıklı oranlar · dengeli politika · kaydedilmiş sonuçlar</p><div className="rule-list">{evaluation.optimization.candidates.map(c => <div className="rule-row" key={c.id}><span className="rule-id">{c.id.split('_')[0]}</span><div className="rule-description"><p>{c.id}</p><small>Duyarlılık {percent(c.recall)} · FPR {percent(c.fpr)} · ROC-AUC {formatFixed(c.roc_auc, 4)}</small></div><div className="rule-strength"><b>{percent(c.balanced_accuracy)}</b><small>BA ± {percent(c.balanced_accuracy_fold_sd)} kat SS</small></div></div>)}</div></details>}
  </>)
}
export default function App() {
  const { localize } = useI18n()

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
    for (const f of data.model.features) { const raw = values[f.column]?.trim() ?? ''; const value = raw === '' ? NaN : Number(raw); if (!Number.isFinite(value) || value < 0) nextErrors[f.column] = 'Sonlu, sıfır veya pozitif bir sayı girin.'; flow[f.column] = value }
    setErrors(nextErrors); setError(''); setResult(null)
    if (Object.keys(nextErrors).length) { setError('Girdileri kontrol edin. Risk puanı üretilmedi.'); return }
    request.current?.abort(); request.current = new AbortController(); const id = ++sequence.current; setBusy(true)
    try { const response = await analyze(flow, selected, request.current.signal); if (id === sequence.current) setResult(response) }
    catch (e) { if ((e as Error).name !== 'AbortError' && id === sequence.current) setError(e instanceof ApiError ? [e.message, ...e.details].join(' ') : 'Analiz tamamlanamadı. Yeniden deneyin.') }
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
  return localize(<div className="app-shell"><a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus() }}>İçeriğe geç</a>
    <aside id="primary-sidebar" className={`sidebar ${mobileMenu ? 'open' : ''}`}><a className="brand" href="#overview" onClick={() => navigate('overview')}><div className="brand-mark"><Network size={25} /></div><div>FUZZY<span>NETWORK SECURITY</span></div></a>
      <div className="nav-label">ÇALIŞMA ALANI</div><nav aria-label="Ana gezinme">{pages.map(p => { const Icon = p.icon; return <a key={p.id} href={`#${p.id}`} aria-current={activePage.id === p.id ? 'page' : undefined} className={activePage.id === p.id ? 'active' : ''} onClick={() => navigate(p.id)}><Icon size={18} /><span>{p.title}</span>{activePage.id === p.id && <ChevronRight size={14} />}</a> })}</nav>
      <div className="sidebar-model"><span>RİSK MOTORU</span><b>Mamdani FIS</b><p>5 girdi <i /> 22 kural <i /> 1 çıktı</p><div className="model-loaded"><span className={`status-dot ${startupError ? 'offline' : ''}`} />{data ? 'Analiz motoru hazır' : startupError ? 'Bağlantı kurulamadı' : 'Model yükleniyor'}</div></div>
      <div className="sidebar-tail"><LanguageSwitcher /></div>
    </aside>{mobileMenu && <button className="menu-backdrop" aria-label="Menüyü kapat" onClick={() => setMobileMenu(false)} />}
    <div className="main-shell"><header className="topbar"><button id="mobile-menu-toggle" className="mobile-toggle icon-button" aria-label={mobileMenu ? 'Gezinme menüsünü kapat' : 'Menüyü aç'} aria-expanded={mobileMenu} aria-controls="primary-sidebar" onClick={() => setMobileMenu(!mobileMenu)}>{mobileMenu ? <X size={20} /> : <ListFilter size={20} />}</button><div className="breadcrumb">Ağ Güvenliği <ChevronRight size={13} /><b>{activePage.title}</b></div><div className="topbar-right"><span className="service-status"><span className={`status-dot ${startupError ? 'offline' : ''}`} />{data ? 'Analiz motoru hazır' : startupError ? 'Servis bağlantısı yok' : 'Servis yükleniyor'}</span></div></header>
      <main id="main-content" tabIndex={-1}>
        {startupError ? <div className="startup-error" role="alert"><TriangleAlert size={35} /><h1>Yerel sunucuya bağlanılamadı</h1><p>{startupError}</p><button className="primary-button" onClick={() => setReload(r => r + 1)}>Yeniden dene</button><small>FastAPI sunucusunu 127.0.0.1:8000 adresinde başlatın.</small></div> : !data ? <div className="startup-loading" role="status"><LoaderCircle className="spin" size={28} /><p>Model ve yerel çalışma alanı yükleniyor…</p></div> : <>
          {activePage.id === 'live' && <LiveTraffic data={data} />}
          {activePage.id === 'analysis' && <>
            <div className="page-title analysis-title"><h1>Risk Analizi</h1></div>
            <div className="analysis-grid"><Card className="input-card"><div className="card-heading"><div className="heading-icon"><SlidersHorizontal size={18} /></div><h2>Akış parametreleri</h2><span className="tiny-label">AKIŞ GİRDİLERİ</span></div>
              <form noValidate onSubmit={(e: FormEvent) => { e.preventDefault(); void run(fields, policy) }}>
                <div className="example-loader"><span><Database size={15} />Trafik kaydı seçin</span><select aria-label="Örnek akış seç" disabled={busy} value={source?.id ?? ''} onChange={e => { const chosen = data.examples.find(x => x.id === e.target.value); if (chosen) loadExample(chosen) }}><option value="">Örnek seçin</option>{data.examples.map(example => <option value={example.id} key={example.id}>{example.title}</option>)}</select><ChevronDown size={13} /></div>
                <div className="input-grid">{data.model.features.map((f, i) => <div className={`field field-${i}`} key={f.key}><label htmlFor={`input-${f.key}`}>{f.title}<details><summary aria-label={`${f.title} hakkında bilgi`}><CircleHelp size={13} /></summary><div><b>{f.unit}</b><p>{f.description}</p></div></details></label><div className={`input-wrap ${errors[f.column] ? 'invalid' : ''}`}><input id={`input-${f.key}`} type="number" inputMode="decimal" min="0" step="any" disabled={busy} value={fields[f.column] ?? ''} placeholder="Değer girin" aria-invalid={!!errors[f.column]} aria-describedby={`help-${f.key}`} onChange={e => { setFields(old => ({ ...old, [f.column]: e.target.value })); setSource(null); setResult(null); setErrors({}); setError('') }} /><span>{f.symbol}</span></div><small id={`help-${f.key}`} className={errors[f.column] ? 'field-error' : ''}>{errors[f.column] ?? f.description}</small></div>)}</div>
                <div className="policy-header"><label>Alarm politikası</label><span>Puan aynı kalır, eşik değişir.</span></div><div className="policy-options" role="group" aria-label="Alarm politikası">{data.policies.map(p => <button key={p.id} type="button" disabled={busy} aria-pressed={policy === p.id} className={policy === p.id ? 'selected' : ''} onClick={() => switchPolicy(p.id)}>{p.id === 'Sensitive' ? <Zap size={14} /> : p.id === 'Balanced' ? <SlidersHorizontal size={14} /> : <Shield size={14} />}{p.title}</button>)}</div><p className="policy-description">{data.policies.find(p => p.id === policy)?.description} Eşik: <b>{nf.format(data.policies.find(p => p.id === policy)!.threshold)}</b>.</p>
                {source && <div className="loaded-source"><span className="status-dot" /><span>Kayıt No. <span className="mono">{source.source_row_id}</span></span><span>Etiket: <b>{source.dataset_label}</b></span></div>}
                {error && <div className="form-error" role="alert"><TriangleAlert size={16} /><span>{error}</span></div>}
                <div className="form-actions"><button type="submit" className="primary-button" disabled={busy}>{busy ? <LoaderCircle size={17} className="spin" /> : <Play size={16} fill="currentColor" />}{busy ? 'Değerlendiriliyor…' : 'Akışı analiz et'}<ArrowRight size={17} /></button><button type="button" className="reset-button" onClick={reset} disabled={busy} aria-label="Formu sıfırla"><RotateCcw size={17} />Sıfırla</button></div>
                <p className="local-note"><Shield size={12} />Ölçümler yalnızca yerel Python sunucusunda işlenir.</p>
              </form></Card><ResultPanel result={result} busy={busy} selectedPolicy={policy} data={data} invalid={Object.keys(errors).length > 0} /></div>
            <Evidence result={busy ? null : result} data={data} /><OutputVisualization result={busy ? null : result} />
          </>}
          {activePage.id === 'overview' && <><div className="page-title"><h1>Güvenlik Özeti</h1><p>Analiz motoru ve trafik kayıtları</p></div><div className="overview-stats">{[[String(data.model.features.length), 'Girdi ölçümü', SlidersHorizontal], [String(data.model.rule_count), 'Risk kuralı', GitBranch], [String(data.policies.length), 'Alarm politikası', Shield], [String(data.examples.length), 'Trafik kaydı', Database]].map(([number, label, Icon]) => { const I = Icon as typeof Database; return <Card key={String(label)}><I size={21} /><strong>{String(number)}</strong><span>{String(label)}</span></Card> })}</div><div className="overview-links"><Card><Network size={24} /><h2>Canlı Trafik</h2><p>Arayüz seçin ve yetkili izlemeyi başlatın.</p><button className="primary-button" onClick={() => navigate('live')}>İzleme panelini aç <ArrowRight size={16} /></button></Card><Card><Database size={24} /><h2>Kayıtlı Trafik</h2><p>Kayıtlı akışları risk, ölçüm ve kurallarıyla inceleyin.</p><button className="text-button" onClick={() => navigate('examples')}>Trafik kayıtlarını aç <ArrowRight size={16} /></button></Card></div></>}
          {activePage.id === 'examples' && <><div className="page-title"><h1>Kayıtlı Trafik</h1><p>Kayıtlı trafik örneklerinden seçilmiş analizler.</p></div><div className="example-filters" role="group" aria-label="Örnek filtresi">{[['all', 'Tüm örnekler'], ['benign', 'BENIGN'], ['attack', 'Saldırı etiketli'], ['error', 'Hatalı kararlar']].map(([id, title]) => <button aria-pressed={exampleFilter === id} className={exampleFilter === id ? 'selected' : ''} key={id} onClick={() => setExampleFilter(id)}>{title}</button>)}</div><div className="example-grid">{data.examples.filter(e => exampleFilter === 'all' || (exampleFilter === 'benign' ? e.dataset_label === 'BENIGN' : exampleFilter === 'attack' ? e.dataset_label !== 'BENIGN' : e.id.startsWith('false-'))).map(example => <Card className="example-card" key={example.id}><div className="example-card-top"><span className="mono">KAYIT #{example.source_row_id}</span><Badge level={example.risk_level} /></div><h2>{example.title}</h2><div className="example-score">{nf.format(example.risk_score)}<span>/100</span></div><div className="example-label"><span>Kayıt etiketi</span><b>{example.dataset_label}</b></div><dl>{data.model.features.map(f => <div key={f.key}><dt>{f.title}</dt><dd>{nf.format(example.features[f.column] as number)} <small>{f.unit}</small></dd></div>)}</dl><div className="example-card-footer"><small>{days[example.source_day] ?? example.source_day} · {example.alert ? 'Alarm var' : 'Alarm yok'}</small><button className="text-button" onClick={() => loadExample(example)}>Analizde aç <ArrowRight size={15} /></button></div></Card>)}</div></>}
          {activePage.id === 'evaluation' && <EvaluationPage evaluation={data.evaluation} />}
          {activePage.id === 'about' && <><div className="page-title"><h1>Sistem Bilgileri</h1></div><div className="about-grid"><Card><div className="card-heading"><h2>Analiz yapılandırması</h2></div><dl className="info-list"><div><dt>Çıkarım</dt><dd>{data.model.method}</dd></div><div><dt>Girdiler / kurallar</dt><dd>{data.model.features.length} / {data.model.rule_count}</dd></div><div><dt>Üyelikler</dt><dd>Üçgen ve yamuk</dd></div><div><dt>Durulaştırma</dt><dd>{data.model.defuzzification}</dd></div><div><dt>Model sürümü</dt><dd>{data.model.model_version}</dd></div><div><dt>Model kimliği</dt><dd className="mono truncate">{data.model.model_id}</dd></div></dl></Card><Card><div className="card-heading"><h2>Alarm politikaları</h2></div><dl className="info-list">{data.policies.map(p => <div key={p.id}><dt>{p.title}</dt><dd>Eşik: {nf.format(p.threshold)}</dd></div>)}</dl><a className="text-button system-api-link" href="/docs" target="_blank" rel="noreferrer">Yerel API referansı <ArrowRight size={16} /></a></Card></div><Card className="about-fuzzy"><div className="card-heading"><h2>Üyelik fonksiyonları</h2></div><div className="about-chart"><MembershipChart feature={data.model.features[0]} /></div></Card><Card className="rule-inventory"><div className="card-heading"><h2>Kural envanteri</h2><span className="tiny-label">{data.model.rule_count} kural</span></div>{data.model.rules.map(rule => <details key={rule.id}><summary><span className="rule-id">{rule.id}</span><span>{rule.conditions}</span><Badge level={rule.consequent} /></summary><p>{rule.text}</p></details>)}</Card></>}
        </>}
        <footer className="page-footer"><span><Network size={13} />FUZZY NETWORK SECURITY</span><span>Risk puanı · 0–100</span></footer>
      </main></div>
  </div>)
}
