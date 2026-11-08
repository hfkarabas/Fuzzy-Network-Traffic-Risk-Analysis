import { useEffect, useRef, useState } from 'react'
import type { Analysis, AppData, Level, PolicyID } from './types'
import LiveFlowDetail from './components/LiveFlowDetail'
import { LOCALE } from './format'

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
  stopped: 'Monitoring stopped', starting: 'Starting capture', waiting_for_flows: 'Monitoring active · waiting for flows',
  analyzing: 'Monitoring active · analyzing finalized flows', capture_unavailable: 'Capture unavailable',
  permission_denied: 'Capture permission denied', capture_failed: 'Capture failed', cleanup_failed: 'Resource cleanup failed',
}
const riskLabels: Record<Level, string> = { Low: 'Low', Medium: 'Medium', High: 'High', Critical: 'Critical' }
async function request<T>(path: string, signal?: AbortSignal, body?: unknown, token?: string): Promise<T> {
  const boundedSignal = signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000)
  const response = await fetch(`/api/live/${path}`, { signal: boundedSignal, ...(body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Monitor-Token': token ?? '' }, body: JSON.stringify(body),
  }) })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error?.message ?? (typeof data.detail === 'string' ? data.detail : 'The monitoring request could not be completed.'))
  if (path.startsWith('status') && (!data || typeof data.state !== 'string' || typeof data.running !== 'boolean' ||
    typeof data.control_token !== 'string' || !data.counts || !data.risk_distribution || !Array.isArray(data.flows) || !Array.isArray(data.errors))) {
    throw new Error('The server returned invalid monitoring status; observations were not displayed.')
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
    }).catch(e => { if (!controller.signal.aborted) setDiscoveryError(`Interfaces could not be read: ${(e as Error).message}`) })
    return () => controller.abort()
  }, [refresh])
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const value = await request<LiveSnapshot>(`status?policy=${policy}`, controller.signal)
        if (!controller.signal.aborted) { token.current = value.control_token; setSnapshot(value) }
      } catch (e) { if (!controller.signal.aborted) setError(`Monitoring status could not be read: ${(e as Error).message}`) }
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
  return (<>
    <div className="page-title"><div><h1>Live Traffic</h1><p>Monitor IPv4 TCP/UDP flows.</p></div></div>
    <section className="card live-controls">
      <h2>Capture controls</h2>
      <p>Select an authorized interface. Capture starts only when you select Start.</p>
      <div className="live-form">
        <label>Data source<select aria-label="Data source" value={mode} disabled={active || busy} onChange={e => setMode(e.target.value as typeof mode)}><option value="capture">Actual network capture</option><option value="replay">Synthetic packet replay · not real traffic</option></select></label>
        <label>Network interface<select aria-label="Network interface" value={device} disabled={mode === 'replay' || active || busy} onChange={e => setDevice(e.target.value)}><option value="">Select an interface</option>{devices.map(i => <option key={i.id} value={i.id}>{i.name} · {i.description || i.id}</option>)}</select></label>
        <label>Live alert policy<select aria-label="Live alert policy" value={policy} onChange={e => setPolicy(e.target.value as PolicyID)}>{(['Sensitive', 'Balanced', 'Conservative'] as PolicyID[]).map(p => <option key={p} value={p}>{p}</option>)}</select></label>
      </div>
      <label className="live-consent"><input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} disabled={active || busy} />I am authorized to monitor the selected source.</label>
      <div className="live-buttons"><button className="primary-button" disabled={busy || active || !authorized || !snapshot || (mode === 'capture' && (!device || !!discoveryError))} onClick={() => { void command('start') }}>Start monitoring</button><button className="secondary-button" disabled={busy || !active} onClick={() => { void command('stop') }}>Stop monitoring</button><button className="secondary-button" disabled={busy} onClick={() => { setError(''); setRefresh(v => v + 1) }}>Refresh status</button></div>
      {discoveryError && <p className="form-error" role="status">Capture unavailable: {discoveryError}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <p role="status" aria-live="polite">{snapshot ? labels[snapshot.state] ?? snapshot.state : 'Loading monitoring status…'}{snapshot?.mode === 'replay' && ' · SYNTHETIC REPLAY (not live observations)'}{snapshot?.interface && ` · ${snapshot.interface}`}</p>
      <p className="source-note">Results update when flows finalize. Monitoring continues across pages; use Stop to end it.</p>
    </section>
    <section className="card live-summary"><h2>Session statistics</h2><div className="live-metrics"><span>Processed packets: <b>{snapshot?.counts.packets ?? 0}</b></span><span>Active flows: <b>{snapshot?.active_flows ?? 0}</b></span><span>Finalized: <b>{snapshot?.counts.finalized_flows ?? 0}</b></span><span>Analyzed: <b>{snapshot?.counts.ok ?? 0}</b></span><span>Insufficient data: <b>{snapshot?.counts.insufficient_data ?? 0}</b></span><span>Inference failed: <b>{snapshot?.counts.inference_failed ?? 0}</b></span><span>Queue drops: <b>{snapshot?.counts.queue_dropped_packets ?? 0}</b></span><span>Rejected packets: <b>{snapshot?.counts.rejected_packets ?? 0}</b></span><span>Flows affected by packet loss: <b>{snapshot?.counts.impaired_flows ?? 0}</b></span>{(Object.keys(riskLabels) as Level[]).map(level => <span key={level}>{riskLabels[level]}: <b>{snapshot?.risk_distribution[level] ?? 0}</b></span>)}</div></section>
    <section className="card live-results"><h2 ref={tableTitle} tabIndex={-1}>Recent flows · up to 50 shown</h2>{!snapshot?.flows.length ? <p>{active ? 'Waiting for flows; TCP termination or the 15-second idle timeout may be required.' : 'No flows have been observed in this session yet.'}</p> : <div className="live-table-wrap"><table><thead><tr><th>Time</th><th>Source → Destination</th><th>Protocol / duration</th><th>Risk</th><th>Finalization</th><th>Explanation</th></tr></thead><tbody>{snapshot.flows.map(flow => <tr key={flow.id}><td>{new Date(flow.ended_us / 1000).toLocaleTimeString(LOCALE)}</td><td>{flow.source}:{flow.source_port}<br />→ {flow.destination}:{flow.destination_port}</td><td>{flow.protocol} · {(flow.duration_us / 1e6).toFixed(3)} s</td><td>{flow.status === 'ok' && flow.analysis?.risk_score != null ? <><b>{flow.analysis.risk_score.toFixed(2)}</b> · {riskLabels[flow.analysis.risk_level!]}<br />{flow.analysis.alert ? 'Alert' : 'No alert'}</> : flow.status === 'insufficient_data' ? 'Insufficient data · no score' : 'Inference failed · no score'}</td><td>{flow.finalization}{flow.provisional && <b> · Partial-flow estimate</b>}</td><td><button className="text-button" onClick={event => { detailTrigger.current = event.currentTarget; setSelected(flow) }}>Inspect flow</button></td></tr>)}</tbody></table></div>}</section>
    {focused && <LiveFlowDetail flow={focused} data={data} policy={policy} onClose={() => { setSelected(null); if (detailTrigger.current?.isConnected) detailTrigger.current.focus(); else tableTitle.current?.focus() }} />}
    {!!snapshot?.errors.length && <section className="card"><h2>Capture / inference events</h2><ul>{snapshot.errors.map((e, index) => <li key={index}>{e.code}{e.message ? ` · ${e.message}` : ''}</li>)}</ul></section>}
  </>)
}
