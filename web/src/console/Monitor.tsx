import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Pause, Play, Search, Square, X } from 'lucide-react'
import { getJSON } from '../api'
import type { AppData, PolicyID } from '../types'
import { useLabels, useRuleText, useWord } from './language'
import { control, inspect, status } from './transport'
import type { Discovery, FlowRow, Snapshot } from './transport'
import { Decision, Evidence, PolicyGrid } from './Evidence'

function reason(code: string, t: (en: string, tr: string) => string) {
  const labels: Record<string, [string, string]> = {
    tcp_reset: ['TCP RST', 'TCP RST'], tcp_fin_both_directions: ['TCP FIN in both directions', 'İki yönde TCP FIN'],
    idle_timeout: ['Idle timeout', 'Boşta kalma süresi'], maximum_duration: ['Maximum duration', 'Azami süre'],
    capacity_eviction: ['Flow capacity limit', 'Akış kapasitesi sınırı'], monitoring_stopped: ['Monitoring stopped', 'İzleme durduruldu'],
    new_syn: ['New TCP connection', 'Yeni TCP bağlantısı'], replay_completed: ['Replay completed', 'Sentetik kayıt tamamlandı'],
  }
  return labels[code] ? t(...labels[code]) : code
}

function FlowInspector({ row, data, policy, close, full, expand }: {
  row: FlowRow; data: AppData; policy: PolicyID; close: () => void; full: boolean; expand: () => void
}) {
  const { t, n, locale } = useLabels()
  const ruleText = useRuleText()
  const w = useWord()
  const result = inspect(row, data.model.model_id)
  const decision = row.policy_comparison[policy]
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [row.id, full])
  return <section className={full ? 'inspector full-inspector' : 'surface inspector'} aria-label={t('Flow inspector', 'Akış inceleme')} onKeyDown={e => { if (e.key === 'Escape') close() }}>
    <header className="section-head"><h2 ref={heading} tabIndex={-1}>{row.protocol} {t('flow', 'akışı')}</h2><button className="plain-icon" onClick={close} aria-label={t('Close flow', 'Akışı kapat')}><X size={19}/></button></header>
    <div className="endpoints"><code>{row.source}:{row.source_port}</code><span>→</span><code>{row.destination}:{row.destination_port}</code></div>
    {row.observation_mode === 'replay' && <p className="notice">{t('Synthetic replay', 'Sentetik kayıt')}</p>}
    {row.provisional && <p className="notice">{t('Partial flow · score covers the observed segment', 'Kısmi akış · puan gözlenen bölüme ait')}</p>}
    {result ? <>
      <Decision result={result} policy={decision && { name: policy, ...decision }}/>
      <p className="quiet">{t('The score describes behavior. It is not an attack probability.', 'Puan akış davranışını ifade eder. Saldırı olasılığı değildir.')}</p>
    </> : <div className="notice"><strong>{t('No valid score', 'Geçerli puan yok')}</strong><p>{row.status === 'inference_failed' ? t('Inference failed.', 'Çıkarım başarısız.') : t('This flow has insufficient measurements or mismatched model data.', 'Ölçümler yetersiz veya model bilgileri uyuşmuyor.')}</p>
      {!!row.quality_errors.length && <ul>{row.quality_errors.map(error => <li key={error}><code>{error}</code></li>)}</ul>}</div>}
    <dl className="flow-facts">
      <div><dt>{t('Started', 'Başlangıç')}</dt><dd>{new Date(row.started_us / 1000).toLocaleString(locale)}</dd></div>
      <div><dt>{t('Ended', 'Bitiş')}</dt><dd>{new Date(row.ended_us / 1000).toLocaleString(locale)}</dd></div>
      <div><dt>{t('Duration', 'Süre')}</dt><dd>{n(row.duration_us / 1e6, 6)} s</dd></div>
      <div><dt>{t('Finalization', 'Tamamlanma')}</dt><dd title={row.finalization}>{reason(row.finalization, t)}</dd></div>
    </dl>
    {result && <><h3>{t('Strongest rules', 'En etkin kurallar')}</h3>
      <ul className="quick-rules">{result.activated_rules.slice(0, 3).map(rule =>
        <li key={rule.id}><code>{rule.id}</code><span>{ruleText(rule.text)}</span><b>{n(rule.strength, 3)}</b></li>)}</ul>
    </>}
    <details open={full || undefined}><summary>{t('Observed measurements', 'Gözlenen ölçümler')}</summary><dl className="flow-facts">{data.model.features.map(feature => {
      const value = row.features[feature.column]
      return <div key={feature.key}><dt>{w(feature.title)}</dt><dd title={value == null ? undefined : String(value)}>{value == null ? '—' : `${n(value)} ${w(feature.unit)}`}</dd></div>
    })}</dl></details>
    {result && <><h3>{t('Policy thresholds', 'Politika eşikleri')}</h3><PolicyGrid data={data} result={result} decisions={row.policy_comparison} />
      <button className="button" onClick={expand}>{full ? t('Return to flow list', 'Akış listesine dön') : t('Open full fuzzy analysis', 'Tam bulanık analizi aç')} <ArrowUpRight size={16}/></button>
      {full && <Evidence data={data} result={result}/>}</>}
  </section>
}

const states: Record<string, [string, string]> = {
  stopped: ['Stopped', 'Durduruldu'], starting: ['Starting', 'Başlatılıyor'],
  waiting_for_flows: ['Waiting for flows', 'Akış bekleniyor'], analyzing: ['Monitoring', 'İzleniyor'],
  capture_unavailable: ['Capture unavailable', 'Yakalama kullanılamıyor'], permission_denied: ['Permission denied', 'İzin reddedildi'],
  capture_failed: ['Capture failed', 'Yakalama başarısız'], cleanup_failed: ['Cleanup failed', 'Kaynaklar serbest bırakılamadı'],
}
const emptyRows: FlowRow[] = []
export default function Monitor({ data }: { data: AppData }) {
  const { t, n, locale } = useLabels()
  const w = useWord()
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [discovery, setDiscovery] = useState<Discovery | null>(null)
  const [policy, setPolicy] = useState<PolicyID>('Balanced')
  const [mode, setMode] = useState<'capture' | 'replay'>('capture')
  const [device, setDevice] = useState('')
  const [authorized, setAuthorized] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [pollError, setPollError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [query, setQuery] = useState('')
  const [protocol, setProtocol] = useState('')
  const [filter, setFilter] = useState('')
  const [sort, setSort] = useState('time')
  const [interval, setIntervalFilter] = useState<number | null>(null)
  const [frozen, setFrozen] = useState<Snapshot | null>(null)
  const [selected, setSelected] = useState<{ session: string | null; row: FlowRow } | null>(null)
  const [full, setFull] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const tableTitle = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    const c = new AbortController()
    void getJSON<Discovery>('/api/live/interfaces', AbortSignal.any([c.signal, AbortSignal.timeout(6500)])).then(value => {
      if (!c.signal.aborted) setDiscovery(value)
    }).catch(e => { if (!c.signal.aborted) setDiscovery({ interfaces: [], error: { message: e.message } }) })
    return () => c.abort()
  }, [refresh])
  useEffect(() => {
    const c = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const value = await status(policy, AbortSignal.any([c.signal, AbortSignal.timeout(6500)]))
        if (!c.signal.aborted) { setSnapshot(value); setPollError('') }
      } catch (e) {
        if (!c.signal.aborted) setPollError((e as Error).message)
      }
      if (!c.signal.aborted) timer = setTimeout(() => void poll(), 1800)
    }
    void poll()
    return () => { c.abort(); clearTimeout(timer) }
  }, [policy, refresh])

  async function command(action: 'start' | 'stop') {
    if (!snapshot || busy) return
    setBusy(true); setError('')
    try {
      await control(action, snapshot.control_token, action === 'start' ? { mode, interface: mode === 'capture' ? device : null, authorized } : {})
      if (action === 'start') { setFrozen(null); setSelected(null); setFull(false); setIntervalFilter(null); setAuthorized(false) }
    } catch (e) { setError((e as Error).message) }
    finally { setRefresh(r => r + 1); setBusy(false) }
  }
  const active = snapshot?.running ?? false
  const aligned = snapshot?.policy === policy
  const paused = frozen !== null && snapshot?.session_id === frozen.session_id
  const retained = paused ? frozen.flows : aligned ? snapshot.flows : emptyRows
  const chosen = selected && snapshot && selected.session === snapshot.session_id
    ? snapshot.flows.find(row => row.id === selected.row.id) ?? selected.row : null
  const bucket = (row: FlowRow) => Math.floor(row.ended_us / 10_000_000) * 10_000
  const groups = new Map<number, number>()
  for (const row of retained) groups.set(bucket(row), (groups.get(bucket(row)) ?? 0) + 1)
  const bins = [...groups].sort(([a], [b]) => a - b)
  const intervalActive = interval !== null && groups.has(interval)
  const matching = retained.filter(row => {
    const q = query.trim()
    const matches = !q || `${row.source}:${row.source_port} ${row.destination}:${row.destination_port}`.includes(q)
    return matches && (!protocol || protocol === row.protocol) && (!intervalActive || bucket(row) === interval)
      && (!filter || filter === 'alert' && inspect(row, data.model.model_id)?.alert === true
        || filter === 'partial' && row.provisional || filter === 'unscored' && !inspect(row, data.model.model_id))
  }).sort((a, b) => (sort === 'risk' ? (inspect(b, data.model.model_id)?.risk_score ?? -1) - (inspect(a, data.model.model_id)?.risk_score ?? -1) : 0) || b.ended_us - a.ended_us)
  const pending = paused ? Math.max(0, (snapshot.counts.finalized_flows ?? 0) - (frozen.counts.finalized_flows ?? 0)) : 0
  const close = () => {
    setSelected(null); setFull(false)
    requestAnimationFrame(() => (trigger.current?.isConnected ? trigger.current : tableTitle.current)?.focus())
  }
  const [stateEn, stateTr] = states[snapshot?.state ?? ''] ?? ['Loading status', 'Durum yükleniyor']
  const configuredDevice = discovery?.interfaces.some(item => item.id === device)
  return <div className="monitor">
    <div className="page-heading"><div><h1>{t('Traffic monitor', 'Trafik izleme')}</h1><p>{t('Inspect completed IPv4 TCP and UDP flows.', 'Tamamlanan IPv4 TCP ve UDP akışlarını inceleyin.')}</p></div>
      <span className="state" data-active={active} role="status"><i />{t(stateEn, stateTr)}{snapshot?.interface && <code>{snapshot.interface}</code>}</span>
    </div>
    <section className="surface capture-line" aria-label={t('Capture settings', 'Yakalama ayarları')}>
      <div className="capture-options">
        <label>{t('Source', 'Kaynak')}<select value={mode} disabled={active || busy} onChange={e => { setMode(e.target.value as typeof mode); setAuthorized(false) }}><option value="capture">{t('Network interface', 'Ağ arayüzü')}</option><option value="replay">{t('Synthetic replay', 'Sentetik kayıt')}</option></select></label>
        {mode === 'capture' && <label>{t('Interface', 'Arayüz')}<select disabled={active || busy} value={device} onChange={e => { setDevice(e.target.value); setAuthorized(false) }}><option value="">{t('Choose an interface', 'Arayüz seçin')}</option>{discovery?.interfaces.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        <label>{t('Alert policy', 'Alarm politikası')}<select value={policy} disabled={busy} onChange={e => { setPolicy(e.target.value as PolicyID); setFrozen(null) }}>{data.policies.map(p => <option key={p.id} value={p.id}>{w(p.title)} · {n(p.threshold)}</option>)}</select></label>
      </div>
      <div className="capture-actions-new">
        <label className="permission"><input type="checkbox" disabled={active || busy} checked={authorized} onChange={e => setAuthorized(e.target.checked)} />{t('I am authorized to monitor this source.', 'Bu kaynağı izlemeye yetkim var.')}</label>
        <div className="actions"><button className="button" onClick={() => setRefresh(v => v + 1)} disabled={busy}>{t('Refresh', 'Yenile')}</button>
          <button className="button primary" disabled={busy || !snapshot || (active ? false : !authorized || !!pollError || (mode === 'capture' && (!configuredDevice || !!discovery?.error)))} onClick={() => void command(active ? 'stop' : 'start')}>
            {active ? <Square size={15}/> : <Play size={15}/>} {active ? t('Stop monitoring', 'İzlemeyi durdur') : t('Start monitoring', 'İzlemeyi başlat')}
          </button></div>
      </div>
      {mode === 'capture' && discovery?.error && <p role="status" className="notice">{t('Capture unavailable:', 'Yakalama kullanılamıyor:')} {discovery.error.message}</p>}
      {(error || pollError) && <p role="alert" className="notice">{error || pollError}</p>}
      {snapshot?.mode === 'replay' && <p className="notice">{t('Synthetic replay · recorded packets for testing', 'Sentetik kayıt · doğrulama paketleri')}</p>}
    </section>
    <section className="session-strip" aria-label={t('Session totals', 'Oturum toplamları')}>
      {[[t('Active', 'Etkin'), snapshot?.active_flows], [t('Finalized', 'Tamamlanan'), snapshot?.counts.finalized_flows], [t('Scored', 'Puanlanan'), snapshot?.counts.ok], [t('Alerts', 'Alarmlar'), aligned ? snapshot.risk_distribution.alerts : undefined]].map(([label, value]) =>
        <div key={label}><span>{label}</span><strong>{snapshot && (label !== t('Alerts', 'Alarmlar') || aligned) ? n(Number(value ?? 0)) : '—'}</strong></div>)}
      <div className="severity"><span>{t('Risk distribution', 'Risk dağılımı')}</span><div>{(['Low', 'Medium', 'High', 'Critical'] as const).map(level => <small key={level} data-risk={level}>{w(level)} <b>{aligned ? n(snapshot.risk_distribution[level] ?? 0) : '—'}</b></small>)}</div></div>
    </section>
    <div hidden={full && !!chosen} className="workbench">
      <section className="surface ledger">
        <header className="section-head"><div><h2 ref={tableTitle} tabIndex={-1}>{t('Flow log', 'Akış günlüğü')}</h2><p>{n(matching.length)} / {n(retained.length)} · {t('latest 50 finalized flows', 'son 50 tamamlanan akış')}</p></div>
          <button className="button" aria-pressed={paused} disabled={!snapshot || !retained.length && !paused} onClick={() => setFrozen(paused ? null : snapshot)}>
            {paused ? <Play size={15}/> : <Pause size={15}/>} {paused ? t('Resume list', 'Listeyi güncelle') : t('Freeze list', 'Listeyi sabitle')}{pending > 0 && ` · +${n(pending)}`}
          </button></header>
        {!!bins.length && <div className="time-filter">
          <div><span>{t('Activity · 10 s intervals with flows', 'Etkinlik · akış içeren 10 sn aralıklar')}</span>{intervalActive && <button className="link-button" onClick={() => setIntervalFilter(null)}>{t('Clear time filter', 'Zaman filtresini temizle')}</button>}</div>
          <div className="histogram">{bins.map(([time, count]) => <button key={time} aria-pressed={interval === time}
            aria-label={`${new Date(time).toLocaleTimeString(locale)} · ${count} ${t('flows', 'akış')}`} title={new Date(time).toLocaleString(locale)}
            onClick={() => setIntervalFilter(interval === time ? null : time)}><span style={{ height: `${Math.max(10, 100 * count / Math.max(...groups.values()))}%` }} /></button>)}</div>
        </div>}
        <div className="filters">
          <label className="search"><Search size={16}/><input type="search" value={query} onChange={e => setQuery(e.target.value)} aria-label={t('IP or port', 'IP veya port')} placeholder={t('IP or port', 'IP veya port')} /></label>
          <select aria-label={t('Protocol', 'Protokol')} value={protocol} onChange={e => setProtocol(e.target.value)}><option value="">{t('All protocols', 'Tüm protokoller')}</option><option>TCP</option><option>UDP</option></select>
          <select aria-label={t('Outcome', 'Sonuç')} value={filter} onChange={e => setFilter(e.target.value)}><option value="">{t('All outcomes', 'Tüm sonuçlar')}</option><option value="alert">{t('Alerts', 'Alarmlar')}</option><option value="partial">{t('Partial flows', 'Kısmi akışlar')}</option><option value="unscored">{t('Unscored', 'Puanlanamayan')}</option></select>
          <select aria-label={t('Sort', 'Sıralama')} value={sort} onChange={e => setSort(e.target.value)}><option value="time">{t('Recent first', 'En yeni önce')}</option><option value="risk">{t('Highest risk first', 'En yüksek risk önce')}</option></select>
        </div>
        <div className="table-scroll"><table><thead><tr><th>{t('Time', 'Zaman')}</th><th>{t('Source → Destination', 'Kaynak → Hedef')}</th><th>{t('Protocol', 'Protokol')}</th><th>{t('Risk', 'Risk')}</th><th>{t('End reason', 'Bitiş nedeni')}</th><th><span className="sr">{t('Inspect', 'İncele')}</span></th></tr></thead>
          <tbody>{matching.map(row => {
            const result = inspect(row, data.model.model_id)
            return <tr key={row.id} data-selected={chosen?.id === row.id}>
              <td><time>{new Date(row.ended_us / 1000).toLocaleTimeString(locale)}</time></td>
              <td className="address"><code>{row.source}:{row.source_port}</code><code>→ {row.destination}:{row.destination_port}</code></td>
              <td><b>{row.protocol}</b><small>{n(row.duration_us / 1e6, 3)} s</small></td>
              <td>{result ? <><b data-risk={result.risk_level}>{n(result.risk_score!)} · {w(result.risk_level!)}</b><small className={result.alert ? 'alarm' : ''}>{result.alert ? t('Alert', 'Alarm') : t('No alert', 'Alarm yok')}</small></> : t('Unscored', 'Puanlanamayan')}</td>
              <td title={row.finalization}>{reason(row.finalization, t)}{row.provisional && <small>{t('Partial flow', 'Kısmi akış')}</small>}</td>
              <td><button className="plain-icon" onClick={e => { trigger.current = e.currentTarget; setSelected({ session: snapshot?.session_id ?? null, row }) }} aria-label={`${t('Inspect', 'İncele')} ${row.protocol} ${row.source}:${row.source_port}`}><ArrowUpRight size={18}/></button></td>
            </tr>
          })}</tbody>
        </table></div>
        {!matching.length && <p className="empty">{!snapshot || !aligned ? t('Loading flow log…', 'Akış günlüğü yükleniyor…') : retained.length ? t('No flows match the current filters.', 'Filtrelere uygun akış yok.') : active ? t('Waiting for TCP termination or the idle timeout.', 'TCP kapanışı veya boşta kalma süresi bekleniyor.') : t('No completed flows in this session.', 'Bu oturumda tamamlanan akış yok.')}</p>}
      </section>
      {chosen && !full && <FlowInspector row={chosen} data={data} policy={policy} close={close} full={false} expand={() => setFull(true)}/>}
    </div>
    {chosen && full && <FlowInspector row={chosen} data={data} policy={policy} close={close} full expand={() => setFull(false)}/>}
    <details className="surface quality"><summary>{t('Capture quality', 'Yakalama kalitesi')}{!!snapshot?.errors.length && ` · ${snapshot.errors.length}`}</summary>
      <dl className="flow-facts">{[['packets', t('Processed packets', 'İşlenen paketler')], ['queue_dropped_packets', t('Queue drops', 'Kuyruk kaybı')], ['rejected_packets', t('Rejected packets', 'Reddedilen paketler')], ['impaired_flows', t('Impaired flows', 'Etkilenen akışlar')], ['insufficient_data', t('Insufficient data', 'Yetersiz veri')], ['inference_failed', t('Inference errors', 'Çıkarım hataları')]].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{snapshot ? n(snapshot.counts[key] ?? 0) : '—'}</dd></div>)}</dl>
      {snapshot?.errors.map((e, i) => <p className="notice" key={i}>{e.message ?? e.code}</p>)}
    </details>
  </div>
}
