import { useEffect, useRef, useState } from 'react'
import { Activity, BookOpen, Database, FlaskConical, Languages, List, Network, Radio } from 'lucide-react'
import { analyze, loadData } from '../api'
import type { Analysis, AppData, Example, Flow, PolicyID } from '../types'
import { LanguageContext, initialLanguage, languageKey, useLabels, useWord } from './language'
import type { Language } from './language'
import Monitor from './Monitor'
import { Decision, Evidence, PolicyGrid } from './Evidence'
import { Performance, Records, Reference } from './Research'

const routes = [
  { id: 'live', en: 'Monitor', tr: 'İzleme', Icon: Radio },
  { id: 'analysis', en: 'Flow analysis', tr: 'Akış analizi', Icon: FlaskConical },
  { id: 'examples', en: 'Recorded flows', tr: 'Kayıtlı akışlar', Icon: List },
  { id: 'evaluation', en: 'Evaluation', tr: 'Değerlendirme', Icon: Activity },
  { id: 'about', en: 'Model', tr: 'Model', Icon: BookOpen },
  { id: 'dataset', en: 'Dataset', tr: 'Veri seti', Icon: Database },
]
const route = () => {
  const id = window.location.hash.slice(1)
  return routes.some(item => item.id === id) ? id : 'live'
}

function Laboratory({ data, initial }: { data: AppData; initial: Example | null }) {
  const { t } = useLabels()
  const w = useWord()
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(
    data.model.features.map(feature => [feature.column, initial ? String(initial.features[feature.column] ?? '') : '']),
  ))
  const [loaded, setLoaded] = useState(initial)
  const [policy, setPolicy] = useState<PolicyID>('Balanced')
  const [result, setResult] = useState<Analysis | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef<AbortController | null>(null)
  useEffect(() => () => pending.current?.abort(), [])
  async function run(selectedPolicy: PolicyID) {
    pending.current?.abort()
    setError(''); setResult(null)
    const flow: Flow = {}
    for (const feature of data.model.features) {
      const value = values[feature.column]?.trim()
      const parsed = value ? Number(value) : NaN
      if (!Number.isFinite(parsed) || parsed < 0) {
        setBusy(false)
        setError(`${w(feature.title)} · ${t('Enter a finite, nonnegative value.', 'Sonlu ve negatif olmayan bir değer girin.')}`)
        return
      }
      flow[feature.column] = parsed
    }
    const controller = new AbortController()
    pending.current = controller
    setBusy(true)
    try {
      const response = await analyze(flow, selectedPolicy, AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]))
      if (response.model_id !== data.model.model_id) throw new Error(t('Model identity changed. Reload the workspace.', 'Model kimliği değişti. Çalışma alanını yenileyin.'))
      if (!controller.signal.aborted) setResult(response)
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message)
    } finally {
      if (!controller.signal.aborted) setBusy(false)
    }
  }
  function load(example: Example | null) {
    pending.current?.abort()
    setLoaded(example)
    setValues(Object.fromEntries(data.model.features.map(f => [f.column, example ? String(example.features[f.column] ?? '') : ''])))
    setResult(null); setError(''); setBusy(false)
  }
  return <>
    <div className="page-heading"><div><h1>{t('Flow analysis', 'Akış analizi')}</h1><p>{t('Run the five-input Mamdani model on a single flow.', 'Beş girdili Mamdani modelini tek bir akış üzerinde çalıştırın.')}</p></div></div>
    <div className="lab-grid">
      <form className="surface form-panel" onSubmit={e => { e.preventDefault(); void run(policy) }} noValidate>
        <h2>{t('Measurements', 'Ölçümler')}</h2>
        <label>{t('Load a recorded flow', 'Kayıtlı akış yükle')}<select value={loaded?.id ?? ''} onChange={e => load(data.examples.find(item => item.id === e.target.value) ?? null)}>
          <option value="">{t('Manual entry', 'Elle giriş')}</option>{data.examples.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        {loaded && <p className="notice">{t('Recorded label', 'Kayıtlı etiket')} · <b>{loaded.dataset_label}</b></p>}
        {data.model.features.map(feature => <label key={feature.key}>{w(feature.title)} <small>{w(feature.unit)}</small>
          <input type="number" min="0" step="any" inputMode="decimal" value={values[feature.column] ?? ''} onChange={e => {
            pending.current?.abort(); setBusy(false); setLoaded(null); setResult(null); setError('')
            setValues(prev => ({ ...prev, [feature.column]: e.target.value }))
          }} /></label>)}
        <label>{t('Alert policy', 'Alarm politikası')}<select value={policy} disabled={busy} onChange={e => {
          const next = e.target.value as PolicyID; setPolicy(next); if (result) void run(next)
        }}>{data.policies.map(item => <option key={item.id} value={item.id}>{w(item.title)}</option>)}</select></label>
        <div className="actions"><button type="submit" className="button primary" disabled={busy}>{busy ? t('Analyzing…', 'Analiz ediliyor…') : t('Analyze flow', 'Akışı analiz et')}</button>
          <button type="button" className="button" onClick={() => load(null)}>{t('Clear', 'Temizle')}</button></div>
        {error && <p role="alert" className="notice">{error}</p>}
      </form>
      <section className="surface study-panel"><h2>{t('Decision', 'Karar')}</h2>
        {result?.status === 'ok' ? <><Decision result={result}/><PolicyGrid result={result} data={data}/><p className="quiet">{t('Changing policy changes the alert threshold. The risk score describes the observed flow.', 'Politika değiştiğinde alarm eşiği değişir. Risk puanı gözlenen akışın davranışını ifade eder.')}</p></> :
          <p className="empty">{result ? t('The model abstained from scoring.', 'Model risk puanı üretmedi.') : t('Run an analysis to see the risk score and rule evidence.', 'Puan ve kural ayrıntılarını görmek için analiz çalıştırın.')}</p>}
      </section>
    </div>
    {result?.status === 'ok' && <Evidence key={JSON.stringify(result.input_values)} data={data} result={result}/>}
  </>
}

function Shell({ onLanguage }: { onLanguage: (language: Language) => void }) {
  const { language, t } = useLabels()
  const [page, setPage] = useState(route)
  const [data, setData] = useState<AppData | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [item, setItem] = useState<Example | null>(null)
  useEffect(() => {
    const listener = () => { setPage(route()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', listener)
    return () => window.removeEventListener('hashchange', listener)
  }, [])
  useEffect(() => {
    const c = new AbortController()
    void loadData(AbortSignal.any([c.signal, AbortSignal.timeout(8000)])).then(value => {
      if (!c.signal.aborted) setData(value)
    }).catch(e => { if (!c.signal.aborted) setError(e.message) })
    return () => c.abort()
  }, [reload])
  return <>
    <a href="#content" className="skip" onClick={e => { e.preventDefault(); document.querySelector<HTMLElement>('#content')?.focus() }}>{t('Skip to content', 'İçeriğe geç')}</a>
    <header className="masthead">
      <a href="#live" className="wordmark"><Network size={23}/><span>Fuzzy Network Security</span></a>
      <div className="masthead-end"><span className="connection" data-ready={!!data}><i />{data ? t('Local engine connected', 'Yerel motor bağlı') : error ? t('Engine offline', 'Motor çevrimdışı') : t('Connecting', 'Bağlanıyor')}</span>
        <button className="button" onClick={() => onLanguage(language === 'en' ? 'tr' : 'en')} aria-label={t('Türkçeye geç', 'Switch to English')}><Languages size={17}/>{language === 'en' ? 'TR' : 'EN'}</button></div>
    </header>
    <nav className="navline" aria-label={t('Main navigation', 'Ana gezinme')}>
      {routes.map(({ id, en, tr, Icon }) => <a key={id} href={`#${id}`} aria-current={page === id ? 'page' : undefined}><Icon size={16}/>{t(en, tr)}</a>)}
    </nav>
    <main id="content" tabIndex={-1}>
      {error ? <section className="surface offline" role="alert"><h1>{t('Local engine unavailable', 'Yerel motor kullanılamıyor')}</h1><p>{error}</p><button className="button primary" onClick={() => { setError(''); setReload(v => v + 1) }}>{t('Try again', 'Yeniden dene')}</button></section>
        : !data ? <p className="empty" role="status">{t('Loading model and policies…', 'Model ve politikalar yükleniyor…')}</p>
        : page === 'live' ? <Monitor data={data}/>
        : page === 'analysis' ? <Laboratory key={item?.id ?? 'manual'} data={data} initial={item}/>
        : page === 'examples' ? <Records data={data} open={example => { setItem(example); window.location.hash = 'analysis' }}/>
        : page === 'evaluation' ? <Performance data={data}/>
        : <Reference data={data} dataset={page === 'dataset'}/>}
    </main>
  </>
}

export default function Workspace() {
  const [language, setLanguage] = useState<Language>(initialLanguage)
  useEffect(() => {
    document.documentElement.lang = language
    try { localStorage.setItem(languageKey, language) } catch { /* Keep in-memory setting when storage is disabled. */ }
  }, [language])
  return <LanguageContext.Provider value={language}><Shell onLanguage={setLanguage}/></LanguageContext.Provider>
}
