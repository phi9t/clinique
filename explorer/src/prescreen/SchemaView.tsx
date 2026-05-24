import { BookOpen } from 'lucide-react'
import FieldTooltip from './FieldTooltip'
import type { SchemaPayload } from './types'

interface SchemaViewProps {
  schema: SchemaPayload
}

const RECORD_ORDER = ['Trial', 'PatientCorpus', 'PatientDocument', 'AgeBound']

export default function SchemaView({ schema }: SchemaViewProps) {
  return (
    <div className="prescreen-schema">
      <section className="pipeline-strip" aria-label="Data pipeline">
        {schema.pipeline.map((step, index) => (
          <div key={step.step} className="pipeline-step">
            <span className="pipeline-step-num">{index + 1}</span>
            <div>
              <strong className="pipeline-step-name">{step.step}</strong>
              <p className="pipeline-step-desc">{step.description}</p>
            </div>
            {index < schema.pipeline.length - 1 && (
              <span className="pipeline-arrow" aria-hidden="true">
                →
              </span>
            )}
          </div>
        ))}
      </section>

      {Object.keys(schema.vocab_gloss).length > 0 && (
        <section className="vocab-gloss-panel" aria-label="Vocabulary glossary">
          <h3>Key vocabulary</h3>
          <dl className="vocab-gloss-list">
            {Object.entries(schema.vocab_gloss).map(([term, meaning]) => (
              <div key={term} className="vocab-gloss-item">
                <dt>{term}</dt>
                <dd>{meaning}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <div className="schema-record-grid">
        {RECORD_ORDER.filter((rt) => schema.records[rt]).map((recordType) => (
          <section key={recordType} className="schema-record-card">
            <div className="schema-record-header">
              <BookOpen size={18} aria-hidden="true" />
              <h3>{recordType}</h3>
            </div>
            <table className="schema-field-table">
              <caption className="visually-hidden">
                Fields for {recordType}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Type</th>
                  <th scope="col">Meaning</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(schema.records[recordType]).map(
                  ([fieldName, fieldDoc]) => (
                    <tr key={fieldName}>
                      <td>
                        <FieldTooltip
                          recordType={recordType}
                          fieldName={fieldName}
                          schema={schema}
                        >
                          {fieldName}
                        </FieldTooltip>
                      </td>
                      <td>
                        <code className="meta-type-tag">{fieldDoc.type}</code>
                      </td>
                      <td>
                        {fieldDoc.description}
                        {fieldDoc.vocab && fieldDoc.vocab.length > 0 && (
                          <span className="schema-vocab-hint">
                            {' '}
                            ({fieldDoc.vocab.length} allowed values)
                          </span>
                        )}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  )
}
