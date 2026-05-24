import { Database } from 'lucide-react'
import type { IndexEntry } from './types'

interface ProvenancePanelProps {
  index: IndexEntry[]
}

export default function ProvenancePanel({ index }: ProvenancePanelProps) {
  return (
    <section className="provenance-panel" aria-label="Dataset provenance">
      <h3>Provenance & reproducibility</h3>
      <div className="provenance-grid">
        {index.map((entry) => (
          <article key={entry.key} className="provenance-card">
            <div className="provenance-card-header">
              <Database size={16} aria-hidden="true" />
              <h4>{entry.label}</h4>
              <span className="meta-type-tag">{entry.count} records</span>
            </div>
            <dl className="provenance-details">
              <div>
                <dt>License</dt>
                <dd>{entry.provenance.license}</dd>
              </div>
              <div>
                <dt>Fixture path</dt>
                <dd>
                  <code>{entry.provenance.fixture_path}</code>
                </dd>
              </div>
              <div>
                <dt>Record command</dt>
                <dd>
                  <code>{entry.provenance.record_command}</code>
                </dd>
              </div>
              <div>
                <dt>Snapshot semantics</dt>
                <dd>{entry.provenance.snapshot_semantics}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  )
}
