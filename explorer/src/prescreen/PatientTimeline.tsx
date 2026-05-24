import FieldTooltip from './FieldTooltip'
import type { PatientCorpusRecord, SchemaPayload } from './types'

interface PatientTimelineProps {
  patient: PatientCorpusRecord
  schema: SchemaPayload
}

const SOURCE_TYPE_COLORS: Record<string, string> = {
  condition: 'var(--color-danger)',
  medication: 'var(--color-secondary)',
  observation: 'var(--color-info)',
  procedure: 'var(--color-warning)',
  note: 'var(--color-success)',
}

function isAfterSnapshot(
  docDate: string | null,
  snapshotDate: string | null,
): boolean {
  if (!docDate || !snapshotDate) return false
  return docDate > snapshotDate
}

export default function PatientTimeline({
  patient,
  schema,
}: PatientTimelineProps) {
  const sortedDocs = [...patient.documents].sort((a, b) => {
    if (!a.date && !b.date) return a.doc_id.localeCompare(b.doc_id)
    if (!a.date) return 1
    if (!b.date) return -1
    return a.date.localeCompare(b.date)
  })

  return (
    <article className="patient-timeline-card">
      <header className="patient-timeline-header">
        <h3>{patient.patient_id}</h3>
        <span className="meta-type-tag">{patient.source}</span>
      </header>

      <div className="patient-demographics">
        <div>
          <FieldTooltip
            recordType="PatientCorpus"
            fieldName="snapshot_date"
            schema={schema}
          >
            Snapshot date
          </FieldTooltip>
          <strong>{patient.snapshot_date ?? 'None (case report)'}</strong>
        </div>
        <div>
          <FieldTooltip
            recordType="PatientCorpus"
            fieldName="demographics"
            schema={schema}
          >
            Demographics
          </FieldTooltip>
          <span>
            age={String(patient.demographics.age ?? '—')}, sex=
            {String(patient.demographics.sex ?? '—')}
          </span>
        </div>
      </div>

      {patient.snapshot_date && (
        <div className="snapshot-marker" role="note">
          <span className="snapshot-marker-line" aria-hidden="true" />
          <span>
            As-of boundary: {patient.snapshot_date} — documents after this date
            would leak future evidence
          </span>
        </div>
      )}

      <ol className="timeline-list">
        {sortedDocs.map((doc) => {
          const leaked = isAfterSnapshot(doc.date, patient.snapshot_date)
          const dotColor =
            SOURCE_TYPE_COLORS[doc.source_type] ?? 'var(--color-primary)'
          return (
            <li
              key={doc.doc_id}
              className={`timeline-item ${leaked ? 'timeline-item-leakage' : ''}`}
            >
              <span
                className="timeline-dot"
                style={{ backgroundColor: dotColor }}
                aria-hidden="true"
              />
              <div className="timeline-content">
                <div className="timeline-meta">
                  <FieldTooltip
                    recordType="PatientDocument"
                    fieldName="source_type"
                    schema={schema}
                  >
                    <span className="meta-type-tag">{doc.source_type}</span>
                  </FieldTooltip>
                  <span className="timeline-date">{doc.date ?? 'undated'}</span>
                  {leaked && (
                    <span className="leakage-badge" role="alert">
                      leakage
                    </span>
                  )}
                </div>
                <p className="timeline-text">{doc.text}</p>
                {Object.keys(doc.structured).length > 0 && (
                  <pre className="timeline-structured">
                    {JSON.stringify(doc.structured, null, 2)}
                  </pre>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </article>
  )
}
