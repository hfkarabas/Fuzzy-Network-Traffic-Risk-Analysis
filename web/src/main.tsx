import { Component } from 'react'
import type { ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import Workspace from './console/Workspace'
import './console/console.css'

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed
      ? <main className="offline"><h1>Workspace unavailable</h1><button className="button" onClick={() => location.reload()}>Reload</button></main>
      : this.props.children
  }
}

createRoot(document.getElementById('root')!).render(<Boundary><Workspace/></Boundary>)
