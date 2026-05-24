import { useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { REPO_HOME, logoMarkUrl } from './lib/assets'
import CdiscExplorer from './cdisc/CdiscExplorer'
import PrescreenExplorer from './prescreen/PrescreenExplorer'

export type DatasetFamily = 'cdisc' | 'prescreen'

export default function App() {
  const [family, setFamily] = useState<DatasetFamily>('cdisc')

  return (
    <div className="relative min-h-screen">
      <div className="observatory-bg" aria-hidden="true" />

      <div className="explorer-container">
        <header className="explorer-header family-header">
          <div className="header-title-section">
            <a href="#main-content" className="skip-link">
              Skip to main content
            </a>
            <a
              href={REPO_HOME}
              className="back-home-link"
              target="_blank"
              rel="noopener noreferrer"
            >
              <ArrowLeft size={16} aria-hidden="true" />
              <span>Back to Clinique Suite</span>
            </a>
            <div className="header-title-row">
              <img
                src={logoMarkUrl()}
                alt="Clinique"
                className="header-logo"
                width={32}
                height={32}
              />
              <h1>Clinique Dataset Explorer</h1>
            </div>
            <p>
              {family === 'cdisc'
                ? 'FDA-pilot CDISC ADaM datasets & metadata validation dashboard'
                : 'Prescreen L0 public data — schema, distributions, drill-down & conformance'}
            </p>
          </div>

          <div
            className="family-switch"
            role="group"
            aria-label="Dataset family"
          >
            <button
              type="button"
              className={`family-switch-btn ${family === 'cdisc' ? 'active' : ''}`}
              aria-pressed={family === 'cdisc'}
              onClick={() => setFamily('cdisc')}
            >
              Regulatory CDISC
            </button>
            <button
              type="button"
              className={`family-switch-btn ${family === 'prescreen' ? 'active' : ''}`}
              aria-pressed={family === 'prescreen'}
              onClick={() => setFamily('prescreen')}
            >
              Prescreen L0
            </button>
          </div>
        </header>

        <div id="main-content">
          {family === 'cdisc' ? <CdiscExplorer /> : <PrescreenExplorer />}
        </div>
      </div>
    </div>
  )
}
