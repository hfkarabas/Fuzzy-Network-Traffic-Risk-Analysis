import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import { useI18n } from './i18n'

function FatalError() {
  const { localize } = useI18n()
  return localize(<main className="fatal"><h1>Görünüm yüklenemedi</h1><p>Beklenmeyen bir veri veya görünüm hatası oluştu. Sayfayı yeniden yükleyebilirsiniz.</p><button onClick={() => location.reload()}>Yeniden yükle</button></main>)
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <FatalError /> : this.props.children }
}
createRoot(document.getElementById('root')!).render(<ErrorBoundary><App /></ErrorBoundary>)
