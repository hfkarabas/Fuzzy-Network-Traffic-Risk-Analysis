import { useEffect, useRef, useState } from 'react'
import { analyze } from '../api'
import { formatNumber } from '../format'
import type { Analysis, AppData, PolicyID } from '../types'
import type { LiveFlow } from '../LiveTraffic'
import { Card, Evidence, ResultPanel } from './FuzzyAnalysis'
import OutputVisualization from './OutputVisualization'

const reasons: Record<string, string> = {
  tcp_reset: 'TCP RST', tcp_fin_both_directions: 'TCP FIN in both directions', idle_timeout: 'Idle timeout',
  maximum_duration: 'Maximum flow duration', capacity_eviction: 'Flow capacity limit', monitoring_stopped: 'Monitoring stopped',
  new_syn: 'New TCP connection start', replay_completed: 'Synthetic replay completed',
}
const quality: Record<string, string> = {
  zero_duration_rate_unavailable: 'Zero duration; packets per second cannot be calculated.', out_of_order_timestamp: 'Packet timestamps are out of order.',
  capture_queue_loss: 'A packet of this flow was lost in the capture queue.', endpoint_packet_rejected: 'A packet between the same endpoints was unusable.',
  concurrent_capture_error: 'An unattributable capture error occurred while this flow was active.',
}

export default function LiveFlowDetail({ flow, data, policy, onClose }: { flow: LiveFlow; data: AppData; policy: PolicyID; onClose: () => void }) {
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
      if (response.model_id !== data.model.model_id || response.risk_score !== flow.analysis!.risk_score) throw new Error('The model or score does not match the selected flow.')
      if (!controller.signal.aborted) setFetched({ key, result: response })
    }).catch(error => { if (!controller.signal.aborted) setFetched({ key, error: (error as Error).message }) })
    return () => controller.abort()
  }, [key, eligible, compatible, base, flow.features, flow.analysis, policy, data.model.model_id])
  return (<section className="live-flow-detail" aria-labelledby="live-detail-title">
    <div className="live-detail-heading"><div><span className="eyebrow">FLOW DETAILS</span><h2 id="live-detail-title" ref={title} tabIndex={-1}>Flow details · {flow.protocol}</h2></div><button className="secondary-button" onClick={onClose}>Close flow details</button></div>
    {flow.observation_mode === 'replay' && <p className="scope-tag">SYNTHETIC REPLAY · NOT REAL TRAFFIC</p>}
    {flow.provisional && <div className="important-note"><div><b>Partial-flow estimate</b><p>Only the observed segment was scored; full connection data may be unavailable.</p></div></div>}
    <Card className="live-flow-metadata"><h3>Flow information</h3><dl>
      <div><dt>Source / port</dt><dd>{flow.source} : {flow.source_port}</dd></div><div><dt>Destination / port</dt><dd>{flow.destination} : {flow.destination_port}</dd></div>
      <div><dt>Protocol</dt><dd>{flow.protocol}</dd></div><div><dt>Duration</dt><dd title={`${flow.duration_us} µs`}>{formatNumber(flow.duration_us / 1e6)} seconds · {formatNumber(flow.duration_us)} µs</dd></div>
      <div><dt>Finalization reason</dt><dd>{reasons[flow.finalization] ?? flow.finalization}</dd></div><div><dt>Observation status</dt><dd>{flow.provisional ? 'Partial-flow estimate' : 'Finalized observed flow'}</dd></div>
      <div><dt>Inference eligibility</dt><dd>{eligible && compatible ? 'Eligible for inference' : compatible ? 'Insufficient valid measurements' : flow.analysis ? 'Model identity mismatch' : 'Could not be evaluated'}</dd></div>
    </dl></Card>
    <div className="analysis-grid live-detail-grid"><Card className="live-input-values"><div className="card-heading"><h2>Five observed inputs</h2><span className="tiny-label">MEASUREMENTS</span></div><dl>{data.model.features.map(feature => {
      const value = flow.features[feature.column]
      return <div key={feature.key}><dt>{feature.title}<small>{feature.column}</small></dt><dd title={value === null || value === undefined ? 'Measurement unavailable' : String(value)}>{value === null || value === undefined ? 'Unavailable' : formatNumber(value)} <small>{feature.unit}</small></dd></div>
    })}</dl><p className="footnote">Hover over a measurement for its full value.</p></Card>
    {eligible && compatible ? <ResultPanel result={result} busy={!result && !(fetched.key === key && fetched.error)} selectedPolicy={policy} data={data} invalid={false} /> : <Card className="live-abstention"><h3>No risk score produced</h3><p>{flow.status === 'inference_failed' ? 'Fuzzy inference could not be completed.' : flow.analysis && !compatible ? 'This flow belongs to a different model. Incorrect membership curves were not displayed.' : 'This flow does not provide enough valid measurements for inference.'}</p>{flow.quality_errors.length > 0 && <ul>{flow.quality_errors.map(error => <li key={error}>{quality[error] ?? `Measurement issue: ${error}`}</li>)}</ul>}<p>Missing measurements were not replaced with zero; membership and defuzzification plots were not drawn.</p></Card>}</div>
    {fetched.key === key && fetched.error && <p role="alert">Policy result unavailable: {fetched.error}</p>}
    {eligible && compatible && flow.analysis?.status === 'ok' && <><Evidence result={result ?? flow.analysis} data={data} idPrefix="live-" /><OutputVisualization result={flow.analysis} /></>}
    {eligible && compatible && <Card className="live-policy-comparison"><div className="card-heading"><h2>Policy comparison</h2><span className="tiny-label">SAME SCORE · DIFFERENT ALERT THRESHOLD</span></div><div className="policy-comparison-grid">{data.policies.map(p => {
      const decision = flow.policy_comparison[p.id]
      return <div key={p.id} className={p.id === policy ? 'selected' : ''}><h3>{p.title}</h3>{decision ? <><p>Score: <b title={String(decision.risk_score)}>{formatNumber(decision.risk_score)}</b></p><p>Threshold: {formatNumber(decision.threshold)}</p><strong>{decision.alert ? 'Alert' : 'No alert'}</strong></> : <p>This policy result is unavailable.</p>}</div>
    })}</div></Card>}
  </section>)
}
