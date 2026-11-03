import { useI18n } from '../i18n'
import { useEffect, useRef, useState } from 'react'
import { analyze } from '../api'
import { formatNumber } from '../format'
import type { Analysis, AppData, PolicyID } from '../types'
import type { LiveFlow } from '../LiveTraffic'
import { Card, Evidence, ResultPanel } from './FuzzyAnalysis'
import OutputVisualization from './OutputVisualization'

const reasons: Record<string, string> = {
  tcp_reset: 'TCP RST', tcp_fin_both_directions: 'Her iki yönde TCP FIN', idle_timeout: 'Boşta kalma zaman aşımı',
  maximum_duration: 'Azami akış süresi', capacity_eviction: 'Akış kapasitesi sınırı', monitoring_stopped: 'İzleme durduruldu',
  new_syn: 'Yeni TCP bağlantı başlangıcı', replay_completed: 'Sentetik replay tamamlandı',
}
const quality: Record<string, string> = {
  zero_duration_rate_unavailable: 'Süre sıfır; paket/saniye hesaplanamıyor.', out_of_order_timestamp: 'Paket zamanları sıralı değil.',
  session_capture_queue_loss: 'Yakalama kuyruğunda paket kaybı var.', session_unusable_packet_or_capture_error: 'Oturumda bozuk paket veya yakalama hatası var.',
}

export default function LiveFlowDetail({ flow, data, policy, onClose }: { flow: LiveFlow; data: AppData; policy: PolicyID; onClose: () => void }) {
  const { localize } = useI18n()

  const title = useRef<HTMLHeadingElement>(null)
  const eligible = flow.status === 'ok' && flow.analysis?.status === 'ok' && flow.quality_errors.length === 0
  const compatible = flow.analysis?.model_id === data.model.model_id
  const key = JSON.stringify({ id: flow.id, policy, features: flow.features, model: data.model.model_id })
  const [fetched, setFetched] = useState<{ key: string; result?: Analysis; error?: string }>({ key: '' })
  const base = eligible && compatible && flow.analysis?.alert_policy.name === policy ? flow.analysis : null
  const result = base ?? (fetched.key === key ? fetched.result ?? null : null)
  useEffect(() => { title.current?.focus(); title.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' }) }, [flow.id])
  useEffect(() => {
    if (!eligible || !compatible || base) return
    const controller = new AbortController()
    void analyze(flow.features, policy, AbortSignal.any([controller.signal, AbortSignal.timeout(5000)])).then(response => {
      if (response.model_id !== data.model.model_id || response.risk_score !== flow.analysis!.risk_score) throw new Error('Model veya puan seçilen akışla eşleşmiyor.')
      if (!controller.signal.aborted) setFetched({ key, result: response })
    }).catch(error => { if (!controller.signal.aborted) setFetched({ key, error: (error as Error).message }) })
    return () => controller.abort()
  }, [key, eligible, compatible, base, flow.features, flow.analysis, policy, data.model.model_id])
  return localize(<section className="live-flow-detail" aria-labelledby="live-detail-title">
    <div className="live-detail-heading"><div><span className="eyebrow">AKIŞ DETAYI</span><h2 id="live-detail-title" ref={title} tabIndex={-1}>Akış ayrıntısı · {flow.protocol}</h2></div><button className="secondary-button" onClick={onClose}>Akış ayrıntısını kapat</button></div>
    {flow.observation_mode === 'replay' && <p className="scope-tag">SENTETİK REPLAY · GERÇEK TRAFİK DEĞİL</p>}
    {flow.provisional && <div className="important-note"><div><b>Kısmi akış tahmini</b><p>Yalnızca gözlemlenen bölüm puanlandı; tam bağlantı verisi olmayabilir.</p></div></div>}
    <Card className="live-flow-metadata"><h3>Akış bilgileri</h3><dl>
      <div><dt>Kaynak / port</dt><dd>{flow.source} : {flow.source_port}</dd></div><div><dt>Hedef / port</dt><dd>{flow.destination} : {flow.destination_port}</dd></div>
      <div><dt>Protokol</dt><dd>{flow.protocol}</dd></div><div><dt>Süre</dt><dd title={`${flow.duration_us} µs`}>{formatNumber(flow.duration_us / 1e6)} saniye · {formatNumber(flow.duration_us)} µs</dd></div>
      <div><dt>Sonlandırma nedeni</dt><dd>{reasons[flow.finalization] ?? flow.finalization}</dd></div><div><dt>Gözlem durumu</dt><dd>{flow.provisional ? 'Kısmi akış tahmini' : 'Sonlandırılmış gözlemlenmiş akış'}</dd></div>
      <div><dt>Çıkarıma uygunluk</dt><dd>{eligible && compatible ? 'Değerlendirilebilir' : compatible ? 'Yeterli geçerli ölçüm yok' : flow.analysis ? 'Model kimliği eşleşmiyor' : 'Değerlendirilemedi'}</dd></div>
    </dl></Card>
    <div className="analysis-grid live-detail-grid"><Card className="live-input-values"><div className="card-heading"><h2>Gözlemlenen beş girdi</h2><span className="tiny-label">ÖLÇÜMLER</span></div><dl>{data.model.features.map(feature => {
      const value = flow.features[feature.column]
      return <div key={feature.key}><dt>{feature.title}<small>{feature.column}</small></dt><dd title={value === null || value === undefined ? 'Ölçüm kullanılamıyor' : String(value)}>{value === null || value === undefined ? 'Hesaplanamıyor' : formatNumber(value)} <small>{feature.unit}</small></dd></div>
    })}</dl><p className="footnote">Tam değer için ölçümün üzerine gelin.</p></Card>
    {eligible && compatible ? <ResultPanel result={result} busy={!result && !(fetched.key === key && fetched.error)} selectedPolicy={policy} data={data} invalid={false} /> : <Card className="live-abstention"><h3>Risk puanı üretilmedi</h3><p>{flow.status === 'inference_failed' ? 'Bulanık çıkarım tamamlanamadı.' : flow.analysis && !compatible ? 'Bu akış farklı bir modele ait. Yanlış üyelik eğrileri gösterilmedi.' : 'Bu akış çıkarım için yeterli geçerli ölçüm sağlamıyor.'}</p>{flow.quality_errors.length > 0 && <ul>{flow.quality_errors.map(error => <li key={error}>{quality[error] ?? `Ölçüm sorunu: ${error}`}</li>)}</ul>}<p>Eksik ölçümler sıfırla doldurulmadı; üyelik ve durulaştırma grafikleri çizilmedi.</p></Card>}</div>
    {fetched.key === key && fetched.error && <p role="alert">Politika sonucu alınamadı: {fetched.error}</p>}
    {eligible && compatible && flow.analysis?.status === 'ok' && <><Evidence result={result ?? flow.analysis} data={data} idPrefix="live-" /><OutputVisualization result={flow.analysis} /></>}
    {eligible && compatible && <Card className="live-policy-comparison"><div className="card-heading"><h2>Politika karşılaştırması</h2><span className="tiny-label">AYNI PUAN · FARKLI ALARM EŞİĞİ</span></div><div className="policy-comparison-grid">{data.policies.map(p => {
      const decision = flow.policy_comparison[p.id]
      return <div key={p.id} className={p.id === policy ? 'selected' : ''}><h3>{p.title} <small data-i18n-skip>{p.id}</small></h3>{decision ? <><p>Puan: <b title={String(decision.risk_score)}>{formatNumber(decision.risk_score)}</b></p><p>Eşik: {formatNumber(decision.threshold)}</p><strong>{decision.alert ? 'Alarm var' : 'Alarm yok'}</strong></> : <p>Bu politika sonucu kullanılamıyor.</p>}</div>
    })}</div></Card>}
  </section>)
}
