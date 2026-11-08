import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

function FatalError() {
  return (<main className="fatal"><h1>Unable to render this view</h1><p>An unexpected data or rendering error occurred. You can reload the page.</p><button onClick={() => location.reload()}>Reload</button></main>)
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <FatalError /> : this.props.children }
}
createRoot(document.getElementById('root')!).render(<ErrorBoundary><App /></ErrorBoundary>)
