import { useEffect, useRef, useState } from 'react'
import type { Analysis, AppData, Level, PolicyID } from './types'
import LiveFlowDetail from './components/LiveFlowDetail'

type Device = { id: string; name: string; description: string }
export type LiveFlow = {
  observation_mode?: string
  id: string; source: string; destination: string; source_port: number; destination_port: number
  protocol: string; started_us: number; ended_us: number; duration_us: number; finalization: string
  status: string; provisional: boolean; features: Record<string, number | null>; quality_errors: string[]; analysis: Analysis | null
  policy_comparison: Record<string, { risk_score: number; risk_level: string; alert: boolean; threshold: number }>
}
export type LiveSnapshot = {
  state: string; running: boolean; mode: 'capture' | 'replay' | null; interface: string | null; session_id: string | null
  active_flows: number; counts: Record<string, number>; risk_distribution: Record<string, number>
  flows: LiveFlow[]; errors: { code: string; message?: string; fatal: boolean }[]; control_token: string
  notice: string; policy: PolicyID
}
const labels: Record<string, string> = {
  stopped: 'İzleme durduruldu', starting: 'Yakalama başlatılıyor', waiting_for_flows: 'İzleme açık · akış bekleniyor',
  analyzing: 'İzleme açık · tamamlanan akışlar analiz ediliyor', capture_unavailable: 'Yakalama kullanılamıyor',
  permission_denied: 'Yakalama izni reddedildi', capture_failed: 'Yakalama başarısız', cleanup_failed: 'Kaynaklar kapatılamadı',
}
const riskLabels: Record<Level, string> = { Low: 'Düşük', Medium: 'Orta', High: 'Yüksek', Critical: 'Kritik' }
async function request<T>(path: string, signal?: AbortSignal, body?: unknown, token?: string): Promise<T> {
  const boundedSignal = signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000)
  const response = await fetch(`/api/live/${path}`, { signal: boundedSignal, ...(body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Monitor-Token': token ?? '' }, body: JSON.stringify(body),
  }) })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error?.message ?? (typeof data.detail === 'string' ? data.detail : 'İzleme isteği tamamlanamadı.'))
  if (path.startsWith('status') && (!data || typeof data.state !== 'string' || typeof data.running !== 'boolean' ||
    typeof data.control_token !== 'string' || !data.counts || !data.risk_distribution || !Array.isArray(data.flows) || !Array.isArray(data.errors))) {
    throw new Error('Sunucu geçersiz izleme durumu döndürdü; gözlem gösterilmedi.')
  }
  return data as T
}

export default function LiveTraffic({ data }: { data: AppData }) {
  const [devices, setDevices] = useState<Device[]>([])
  const [discoveryError, setDiscoveryError] = useState('')
  const [mode, setMode] = useState<'capture' | 'replay'>('capture')
  const [device, setDevice] = useState('')
  const [policy, setPolicy] = useState<PolicyID>('Balanced')
  const [authorized, setAuthorized] = useState(false)
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const [selected, setSelected] = useState<LiveFlow | null>(null)
  const detailTrigger = useRef<HTMLButtonElement | null>(null)
  const tableTitle = useRef<HTMLHeadingElement>(null)
  const token = useRef('')
  const mounted = useRef(false)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    const controller = new AbortController()
    void request<{ interfaces: Device[]; error: { message: string } | null }>('interfaces', controller.signal).then(data => {
      setDevices(data.interfaces); setDiscoveryError(data.error?.message ?? '')
    }).catch(e => { if (!controller.signal.aborted) setDiscoveryError(`Arayüzler okunamadı: ${(e as Error).message}`) })
    return () => controller.abort()
  }, [refresh])
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const value = await request<LiveSnapshot>(`status?policy=${policy}`, controller.signal)
        if (!controller.signal.aborted) { token.current = value.control_token; setSnapshot(value) }
      } catch (e) { if (!controller.signal.aborted) setError(`İzleme durumu okunamadı: ${(e as Error).message}`) }
      if (!controller.signal.aborted) timer = setTimeout(() => { void poll() }, 2000)
    }
    void poll()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [policy, refresh])
  async function command(action: 'start' | 'stop') {
    setBusy(true); setError('')
    try {
      await request<LiveSnapshot>(action, undefined, action === 'start' ? { mode, interface: mode === 'capture' ? device : null, authorized } : {}, token.current)
      const current = await request<LiveSnapshot>(`status?policy=${policy}`)
      if (mounted.current) { setSnapshot(current); setRefresh(v => v + 1) }
    } catch (e) { if (mounted.current) setError((e as Error).message) }
    finally { if (mounted.current) setBusy(false) }
  }
  const active = snapshot?.running ?? false
  const focused = selected ? snapshot?.flows.find(flow => flow.id === selected.id) ?? selected : null
  return <>
    <div className="page-title"><div><span className="eyebrow">YEREL · AÇIK İZİNLE · AKIŞ TABANLI</span><h1>Canlı Trafik</h1><p>IPv4 TCP/UDP akışlarını tamamlandıktan sonra mevcut bulanık modelle değerlendirin.</p></div></div>
    <section className="card live-controls">
      <h2>Yakalama denetimi</h2>
      <p>Yalnızca izleme yetkiniz olan arayüzü seçin. Paket içeriği kaydedilmez; promiscuous mod kullanılmaz. Başlangıç otomatik değildir.</p>
      <div className="live-form">
        <label>Veri kaynağı<select aria-label="Veri kaynağı" value={mode} disabled={active || busy} onChange={e => setMode(e.target.value as typeof mode)}><option value="capture">Gerçek ağ yakalama</option><option value="replay">Sentetik paket replay · gerçek trafik değil</option></select></label>
        <label>Ağ arayüzü<select aria-label="Ağ arayüzü" value={device} disabled={mode === 'replay' || active || busy} onChange={e => setDevice(e.target.value)}><option value="">Arayüz seçin</option>{devices.map(i => <option key={i.id} value={i.id}>{i.name} · {i.description || i.id}</option>)}</select></label>
        <label>Canlı alarm politikası<select aria-label="Canlı alarm politikası" value={policy} onChange={e => setPolicy(e.target.value as PolicyID)}>{(['Sensitive', 'Balanced', 'Conservative'] as PolicyID[]).map(p => <option key={p}>{p}</option>)}</select></label>
      </div>
      <label className="live-consent"><input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} disabled={active || busy} />Seçtiğim kaynağı izlemeye yetkiliyim; deneysel uyumluluk sınırlarını anlıyorum.</label>
      <div className="live-buttons"><button className="primary-button" disabled={busy || active || !authorized || !snapshot || (mode === 'capture' && (!device || !!discoveryError))} onClick={() => { void command('start') }}>İzlemeyi başlat</button><button className="secondary-button" disabled={busy || !active} onClick={() => { void command('stop') }}>İzlemeyi durdur</button><button className="secondary-button" disabled={busy} onClick={() => { setError(''); setRefresh(v => v + 1) }}>Durumu yenile</button></div>
      {discoveryError && <p className="form-error" role="status">Yakalama kullanılamıyor: {discoveryError}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <p role="status" aria-live="polite">{snapshot ? labels[snapshot.state] ?? snapshot.state : 'İzleme durumu yükleniyor…'}{snapshot?.mode === 'replay' && ' · SENTETİK REPLAY (canlı gözlem değil)'}{snapshot?.interface && ` · ${snapshot.interface}`}</p>
      <p className="source-note">Tamamlanan gözlemlenmiş akışlar; anlık paket saldırı tespiti değildir. CICFlowMeter sürüm eşdeğerliği doğrulanmamıştır. İzleme sayfalar arasında devam eder; durdur düğmesi veya sunucu kapanışı sonlandırır. Tek backend süreci kullanın.</p>
    </section>
    <section className="card live-summary"><h2>Oturum istatistikleri</h2><div className="live-metrics"><span>İşlenen paket: <b>{snapshot?.counts.packets ?? 0}</b></span><span>Etkin akış: <b>{snapshot?.active_flows ?? 0}</b></span><span>Sonlandırılan: <b>{snapshot?.counts.finalized_flows ?? 0}</b></span><span>Analiz edilen: <b>{snapshot?.counts.ok ?? 0}</b></span><span>Yetersiz veri: <b>{snapshot?.counts.insufficient_data ?? 0}</b></span><span>Çıkarım başarısız: <b>{snapshot?.counts.inference_failed ?? 0}</b></span><span>Kuyruk kaybı: <b>{snapshot?.counts.queue_dropped_packets ?? 0}</b></span><span>Reddedilen paket: <b>{snapshot?.counts.rejected_packets ?? 0}</b></span>{(Object.keys(riskLabels) as Level[]).map(level => <span key={level}>{riskLabels[level]}: <b>{snapshot?.risk_distribution[level] ?? 0}</b></span>)}</div><p>Puanlar politika değişiminde sabit kalır; yalnızca alarm eşiği değişir. Risk puanı saldırı olasılığı değildir.</p></section>
    <section className="card live-results"><h2 ref={tableTitle} tabIndex={-1}>Son akışlar · en fazla 50 gösterilir</h2>{!snapshot?.flows.length ? <p>{active ? 'Akış bekleniyor; TCP sonlanması veya 15 saniyelik boşta kalma süresi beklenebilir.' : 'Bu oturumda henüz akış gözlemi yok.'}</p> : <div className="live-table-wrap"><table><thead><tr><th>Zaman</th><th>Kaynak → Hedef</th><th>Protokol / süre</th><th>Risk</th><th>Sonlandırma</th><th>Açıklama</th></tr></thead><tbody>{snapshot.flows.map(flow => <tr key={flow.id}><td>{new Date(flow.ended_us / 1000).toLocaleTimeString('tr-TR')}</td><td>{flow.source}:{flow.source_port}<br />→ {flow.destination}:{flow.destination_port}</td><td>{flow.protocol} · {(flow.duration_us / 1e6).toFixed(3)} s</td><td>{flow.status === 'ok' && flow.analysis?.risk_score != null ? <><b>{flow.analysis.risk_score.toFixed(2)}</b> · {riskLabels[flow.analysis.risk_level!]}<br />{flow.analysis.alert ? 'Alarm var' : 'Alarm yok'}</> : flow.status === 'insufficient_data' ? 'Yetersiz veri · puan yok' : 'Çıkarım başarısız · puan yok'}</td><td>{flow.finalization}{flow.provisional && <b> · Kısmi akış tahmini</b>}</td><td><button className="text-button" onClick={event => { detailTrigger.current = event.currentTarget; setSelected(flow) }}>Akışı incele</button></td></tr>)}</tbody></table></div>}</section>
    {focused && <LiveFlowDetail flow={focused} data={data} policy={policy} onClose={() => { setSelected(null); if (detailTrigger.current?.isConnected) detailTrigger.current.focus(); else tableTitle.current?.focus() }} />}
    {!!snapshot?.errors.length && <section className="card"><h2>Yakalama / çıkarım bildirimleri</h2><ul>{snapshot.errors.map((e, index) => <li key={index}>{e.code}{e.message ? ` · ${e.message}` : ''}</li>)}</ul></section>}
  </>
}
