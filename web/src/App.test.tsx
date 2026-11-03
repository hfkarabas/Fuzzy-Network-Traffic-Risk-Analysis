import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import fixture from './test-fixture.json'
import replayFixture from './live-test-fixture.json'
import outputs from './visualization-test-fixture.json'

function installAPI() {
  const server = vi.fn(async (url: string | URL | Request, options?: RequestInit) => {
    const path = String(url)
    if (path === '/api/visualization/output') return new Response(JSON.stringify(outputs.historical))
    if (path === '/api/analyze') {
      const body = JSON.parse(String(options?.body))
      const example = fixture.examples.examples.find(e => JSON.stringify(e.features) === JSON.stringify(body.features))
      if (!example) throw new Error('Test requires a captured real example')
      const analyses = fixture.analyses as Record<string, Record<string, unknown>>
      return new Response(JSON.stringify(analyses[example.id][body.policy]), { status: 200 })
    }
    const key = path.replace('/api/', '') as 'health' | 'model' | 'policies' | 'examples' | 'evaluation'
    return new Response(JSON.stringify(fixture[key]), { status: 200 })
  })
  vi.stubGlobal('fetch', server)
  return server
}
beforeEach(() => { window.location.hash = '#analysis' })

it('opens opt-in live monitoring from existing application navigation', async () => {
  const offline = installAPI()
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL | Request, options?: RequestInit) => {
    if (String(url).includes('/api/live/interfaces')) return new Response(JSON.stringify({ interfaces: [], error: { message: 'Npcap eksik' } }))
    if (String(url).includes('/api/live/status')) return new Response(JSON.stringify({ ...replayFixture, mode: null, flows: [], counts: {}, state: 'stopped' }))
    return offline(url, options)
  }))
  render(<App />)
  await screen.findByText('Alarm üretildi')
  await userEvent.click(screen.getByRole('link', { name: 'Canlı Trafik' }))
  expect(await screen.findByRole('heading', { name: 'Canlı Trafik' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'İzlemeyi başlat' })).toBeDisabled()
  expect(await screen.findByText(/Npcap eksik/)).toBeVisible()
})

describe('actual-response UI integration', () => {
  it('loads a real example, its actual score and Python membership curves', async () => {
    installAPI(); render(<App />)
    const expected = fixture.analyses['policy-contrast'].Balanced
    await screen.findByText('Alarm üretildi')
    expect(screen.getByRole('heading', { name: 'Risk Analizi' })).toBeVisible()
    expect(screen.getByRole('img', { name: /Risk puanı/ })).toHaveAccessibleName(`Risk puanı ${new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 }).format(expected.risk_score!)} / 100`)
    expect(screen.getAllByRole('img', { name: /sunucudan alınan üyelik/ })).toHaveLength(5)
    expect(screen.getByText('Risk puanı saldırı olasılığı değildir.')).toHaveTextContent('saldırı olasılığı değildir')
  })
  it('switches policy through HTTP without changing the fuzzy score', async () => {
    const server = installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    const before = screen.getByRole('img', { name: /Risk puanı/ }).getAttribute('aria-label')
    await userEvent.click(screen.getByRole('button', { name: 'Temkinli' }))
    await screen.findByText('Alarm üretilmedi')
    expect(screen.getByRole('img', { name: /Risk puanı/ })).toHaveAttribute('aria-label', before)
    const posts = server.mock.calls.filter(call => call[0] === '/api/analyze')
    expect(JSON.parse(String(posts.at(-1)?.[1]?.body)).policy).toBe('Conservative')
  })
  it('shows the actual activated rules and activation strength', async () => {
    installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    await userEvent.click(screen.getByRole('tab', { name: /Etkin kurallar/ }))
    const first = fixture.analyses['policy-contrast'].Balanced.activated_rules[0]
    expect(screen.getByText(first.text_tr)).toBeVisible()
    expect(screen.getByText(first.id)).toBeVisible()
  })
  it('resets and rejects missing/negative input without sending a prediction', async () => {
    const server = installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    await userEvent.click(screen.getByRole('button', { name: 'Formu sıfırla' }))
    const before = server.mock.calls.filter(call => call[0] === '/api/analyze').length
    await userEvent.click(screen.getByRole('button', { name: 'Akışı analiz et' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Risk puanı üretilmedi')
    expect(server.mock.calls.filter(call => call[0] === '/api/analyze')).toHaveLength(before)
    expect(screen.getByRole('img', { name: 'Henüz risk puanı yok' })).toBeVisible()
  })
  it('filters real error examples and keeps historical labels separate', async () => {
    installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    await userEvent.click(screen.getByRole('link', { name: 'Kayıtlı Trafik' }))
    await userEvent.click(screen.getByRole('button', { name: 'Hatalı kararlar' }))
    expect(screen.getByRole('heading', { name: 'Yanlış alarm kaydı' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Kaçırılan saldırı kaydı' })).toBeVisible()
    expect(screen.getAllByRole('button', { name: 'Analizde aç' })).toHaveLength(2)
  })
  it('distinguishes historical tests from group-weighted internal validation', async () => {
    installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    await userEvent.click(screen.getByRole('link', { name: 'Model Performansı' }))
    await userEvent.click(screen.getByRole('button', { name: 'İç doğrulama' }))
    expect(screen.getByText('İÇ DOĞRULAMA · BAĞIMSIZ TEST DEĞİL')).toBeVisible()
    expect(screen.getByText('Grup ağırlıklı oran ile akış bazındaki oran aynı değildir.')).toBeVisible()
    expect(screen.getByText('15,708%')).toBeVisible()
  })
  it('handles backend disconnection with a retry state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline'))); render(<App />)
    await screen.findByRole('heading', { name: 'Yerel sunucuya bağlanılamadı' })
    expect(screen.getByRole('button', { name: 'Yeniden dene' })).toBeVisible()
  })
  it('keeps recorded model metrics accessible without development framing', async () => {
    installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    await userEvent.click(screen.getByRole('link', { name: 'Model Performansı' }))
    expect(screen.getByText('Kayıtlı değerlendirmeler; canlı ortam başarısını göstermez.')).toBeVisible()
    await userEvent.click(screen.getByText('Kayıtlı model karşılaştırması'))
    expect(screen.getByText('Grup ağırlıklı oranlar · dengeli politika · kaydedilmiş sonuçlar')).toBeVisible()
    expect(screen.getByText('D_combined')).toBeVisible()
  })
  it('rejects malformed API prediction data rather than drawing a fake score', async () => {
    const original = installAPI()
    vi.stubGlobal('fetch', vi.fn(async (url: string | URL | Request, options?: RequestInit) => String(url) === '/api/analyze' ? new Response(JSON.stringify({ status: 'ok', risk_score: 900 }), { status: 200 }) : original(url, options)))
    render(<App />)
    await screen.findByRole('alert')
    expect(screen.getByRole('alert')).toHaveTextContent('geçersiz analiz yanıtı')
    expect(screen.getByRole('img', { name: 'Henüz risk puanı yok' })).toBeVisible()
  })
  it('clears a previous result when measurements are edited', async () => {
    installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    fireEvent.change(screen.getByRole('spinbutton', { name: /Paket yoğunluğu/ }), { target: { value: '5' } })
    expect(screen.getByRole('img', { name: 'Henüz risk puanı yok' })).toBeVisible()
  })
  it('supports keyboard switching of explanation tabs', async () => {
    installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    screen.getByRole('tab', { name: 'Üyelik dereceleri' }).focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: /Etkin kurallar/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'panel-rules')
  })
  it('explains all six inference steps through the risk score', async () => {
    installAPI(); render(<App />); await screen.findByText('Alarm üretildi')
    await userEvent.click(screen.getByRole('tab', { name: 'İşlem akışı' }))
    expect(screen.getByText('06')).toBeVisible()
    expect(screen.getByText('0–100 · dilsel seviye')).toBeVisible()
  })
})
