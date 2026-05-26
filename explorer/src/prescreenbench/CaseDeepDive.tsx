import { useMemo, useState } from 'react'
import type { CaseGrader, CriterionAnnotation, EvidenceCheck, ExplorerCase } from './types'

type CriterionStatus = 'unsafe' | 'fabricated' | 'unsupported' | 'incorrect' | 'ok'
type EvidenceStatus = 'quote-found' | 'quote-missing' | 'document-missing' | 'empty-quote' | 'no-evidence'

type HighlightRange = {
  start: number
  end: number
}

type ActiveEvidence = {
  docId: string
  range: HighlightRange | null
}

function asCaseGrader(value: unknown): CaseGrader | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  const candidate = value as Record<string, unknown>
  if (!Object.hasOwn(candidate, 'case_id') || !Object.hasOwn(candidate, 'criteria')) {
    return null
  }

  return value as CaseGrader
}

function getCriterionStatus(criterion: CriterionAnnotation): {
  status: CriterionStatus
  label: string
} {
  if (criterion.unsafe_clearance) {
    return { status: 'unsafe', label: 'Unsafe clearance' }
  }

  if (criterion.fabricated_quote_count > 0) {
    return { status: 'fabricated', label: 'Fabricated quote' }
  }

  if (criterion.unsupported_decision) {
    return { status: 'unsupported', label: 'Unsupported decision' }
  }

  if (!criterion.correct) {
    return { status: 'incorrect', label: 'Incorrect' }
  }

  return { status: 'ok', label: 'OK' }
}

function getEvidenceStatus(check: EvidenceCheck): {
  status: EvidenceStatus
  label: string
  className: string
} {
  if (!check.document_found) {
    return {
      status: 'document-missing',
      label: 'Document missing',
      className: 'pb-evidence-document-missing',
    }
  }

  if (check.empty_quote || !check.quote || check.quote.trim().length === 0) {
    return {
      status: 'empty-quote',
      label: 'Empty quote',
      className: 'pb-evidence-empty-quote',
    }
  }

  if (!check.quote_found) {
    return {
      status: 'quote-missing',
      label: 'Quote missing',
      className: 'pb-evidence-quote-missing',
    }
  }

  return { status: 'quote-found', label: 'Quote found', className: 'pb-evidence-quote-found' }
}

function normalizeRange(text: string, startChar: number | null, endChar: number | null): HighlightRange | null {
  if (typeof startChar !== 'number' || typeof endChar !== 'number') {
    return null
  }

  const start = Math.max(0, Math.min(startChar, text.length))
  const end = Math.max(start, Math.min(endChar, text.length))
  if (start === end) {
    return null
  }

  return { start, end }
}

function HighlightedDocument({
  text,
  range,
}: {
  text: string
  range: HighlightRange | null
}) {
  if (!range) {
    return <>{text}</>
  }

  const before = text.slice(0, range.start)
  const middle = text.slice(range.start, range.end)
  const after = text.slice(range.end)

  return (
    <>
      {before}
      <mark>{middle}</mark>
      {after}
    </>
  )
}

function formatJson(payload: unknown): string {
  if (payload === undefined || payload === null) {
    return 'No payload'
  }

  try {
    const rendered = JSON.stringify(payload, null, 2)
    return rendered ?? 'No payload'
  } catch {
    return String(payload)
  }
}

function EvidenceStatusButton({
  check,
  isActive,
  onActivate,
}: {
  check: EvidenceCheck
  isActive: boolean
  onActivate: () => void
}) {
  const status = getEvidenceStatus(check)
  const quotePreview = check.quote ? check.quote.trim() : ''
  const label =
    quotePreview.length > 72 ? `${quotePreview.slice(0, 72)}…` : quotePreview

  const title = `${check.doc_id} — ${status.label}${label ? `: ${label}` : ''}`

  return (
    <button
      type="button"
      className={`pb-evidence-button ${status.className} ${isActive ? 'is-active' : ''}`}
      onClick={onActivate}
      aria-pressed={isActive}
      title={title}
    >
      {`${status.label} (${check.doc_id})`}
    </button>
  )
}

type CaseDeepDiveProps = {
  caseRow: ExplorerCase | null
  selectedAgents: string[]
}

export default function CaseDeepDive({ caseRow, selectedAgents }: CaseDeepDiveProps) {
  const [activeEvidence, setActiveEvidence] = useState<ActiveEvidence | null>(null)

  const selectedGraderOutputs = useMemo(
    () =>
      selectedAgents.map((agent) => ({
        agent,
        output: caseRow ? asCaseGrader(caseRow.grader[agent]) : null,
      })),
    [caseRow, selectedAgents],
  )

  if (!caseRow) {
    return (
      <section className="pb-deep-dive" aria-label="Case deep dive empty state">
        <p className="pb-muted">Select a case to inspect trial, patient records, and graded criteria.</p>
      </section>
    )
  }

  const trial = caseRow.trial
  const patient = caseRow.patient
  const documents = patient?.documents ?? []
  const activeDocument = activeEvidence
    ? documents.find((doc) => doc.doc_id === activeEvidence.docId)
    : null

  const selectedDocumentHighlight = activeDocument ? normalizeRange(activeDocument.text, activeEvidence?.range?.start ?? null, activeEvidence?.range?.end ?? null) : null

  return (
    <section className="pb-deep-dive" aria-label="Case deep dive">
      <header className="pb-deep-dive-header">
        <h3>Case Deep Dive</h3>
        <p>
          <strong>{caseRow.case.case_id}</strong>
          {' '}
          — patient:
          {' '}
          <span>{patient?.patient_id ?? caseRow.case.patient_id}</span>
        </p>
      </header>

      <div className="pb-source-panels">
        <section className="pb-text-panel" aria-label="Trial details">
          <h4>Trial</h4>
          <div className="pb-mini-grid">
            <div>Trial ID / NCT</div>
            <div>{trial?.trial_id ?? caseRow.case.trial_id}</div>
            <div>Title</div>
            <div>{trial?.title ?? caseRow.case.trial_id}</div>
            <div>Phase</div>
            <div>{trial?.phase ?? 'Not reported'}</div>
            <div>Recruitment</div>
            <div>{trial?.recruitment_status ?? 'Not reported'}</div>
          </div>

          <div>
            <h5>Conditions</h5>
            {trial?.conditions.length ? (
              <ul className="pb-condition-list">
                {trial.conditions.map((condition) => (
                  <li key={condition}>{condition}</li>
                ))}
              </ul>
            ) : (
              <p className="pb-muted">No condition metadata available.</p>
            )}
          </div>

          <h5>Eligibility text</h5>
          <pre className="pb-text-block">
            {trial?.eligibility_text ?? 'No eligibility criteria payload for this trial.'}
          </pre>
        </section>

        <section className="pb-text-panel" aria-label="Patient records">
          <h4>Patient</h4>
          <div className="pb-mini-grid">
            <div>Patient ID</div>
            <div>{patient?.patient_id ?? caseRow.case.patient_id}</div>
            <div>Source</div>
            <div>{patient?.source ?? caseRow.case.patient_source}</div>
            <div>Snapshot date</div>
            <div>{patient?.snapshot_date ?? caseRow.case.snapshot_date ?? 'Not reported'}</div>
          </div>

          <h5>Demographics (JSON)</h5>
          <pre className="pb-text-block">{formatJson(patient?.demographics)}</pre>

          <h5>Documents in this case ({documents.length})</h5>
          {documents.length === 0 ? (
            <p className="pb-muted">
              No documents were included with this patient bundle entry.
            </p>
          ) : (
            <div className="pb-doc-list">
              {documents.map((doc) => {
                const isActive = activeDocument?.doc_id === doc.doc_id
                const range = isActive ? selectedDocumentHighlight : null

                return (
                  <article key={doc.doc_id} className={`pb-doc ${isActive ? 'active' : ''}`}>
                    <header>
                      <div className="pb-mini-grid">
                        <div>Document ID</div>
                        <div>{doc.doc_id}</div>
                        <div>Type</div>
                        <div>{doc.source_type}</div>
                        <div>Document date</div>
                        <div>{doc.date ?? 'Not reported'}</div>
                      </div>
                    </header>

                    <pre className="pb-text-block">
                      <HighlightedDocument text={doc.text ?? ''} range={range} />
                    </pre>

                    <h5>Structured payload</h5>
                    <pre className="pb-text-block">{formatJson(doc.structured)}</pre>
                  </article>
                )
              })}
            </div>
          )}

          {activeEvidence && !activeDocument && (
            <p className="pb-muted">
              Evidence refers to document
              {' '}
              <strong>{activeEvidence.docId}</strong>
              {', '}
              which is not present in this patient bundle.
            </p>
          )}
        </section>

        <section className="pb-criteria-panel" aria-label="Criterion comparison">
          <h4>Criterion comparison by agent</h4>

          {selectedAgents.length === 0 ? (
            <p className="pb-muted">Select at least one agent to compare grader outputs.</p>
          ) : (
            <div className="pb-agent-criteria-wrapper">
              {selectedGraderOutputs.map(({ agent, output }) => {
                if (!output) {
                  return (
                    <article key={agent} className="pb-agent-criteria">
                      <h5>
                        {agent}
                        {' '}
                        — no output
                      </h5>
                      <p className="pb-muted">No grader output is available for this case.</p>
                    </article>
                  )
                }

                if (!output.criteria.length) {
                  return (
                    <article key={agent} className="pb-agent-criteria">
                      <h5>{agent}</h5>
                      <p className="pb-muted">This grader did not return criterion-level rows for the case.</p>
                    </article>
                  )
                }

                return (
                  <article key={agent} className="pb-agent-criteria">
                    <h5>{agent}</h5>

                    <div className="pb-criteria-table-wrapper">
                      <table className="pb-criteria-table">
                        <thead>
                          <tr>
                            <th scope="col">Criterion</th>
                            <th scope="col">Type</th>
                            <th scope="col">Domain</th>
                            <th scope="col">Safety-critical</th>
                            <th scope="col">Gold label</th>
                            <th scope="col">Prediction</th>
                            <th scope="col">Correctness/status</th>
                            <th scope="col">Rationale</th>
                            <th scope="col">Evidence checks</th>
                          </tr>
                        </thead>
                        <tbody>
                          {output.criteria.map((criterion) => {
                            const criterionStatus = getCriterionStatus(criterion)
                            return (
                              <tr key={`${agent}-${criterion.criterion_id}`}>
                                <td>
                                  <p>
                                    <strong>{criterion.criterion_id}</strong>
                                    <span className="pb-muted"> {criterion.criterion_text}</span>
                                  </p>
                                </td>
                                <td>{criterion.criterion_type}</td>
                                <td>{criterion.clinical_domain}</td>
                                <td>{criterion.is_safety_critical ? 'yes' : 'no'}</td>
                                <td>{criterion.gold_label}</td>
                                <td>{criterion.prediction}</td>
                                <td>
                                  <span className={`pb-status pb-status-${criterionStatus.status}`}>
                                    {criterionStatus.label}
                                  </span>
                                </td>
                                <td>{criterion.rationale || 'No rationale provided'}</td>
                                <td>
                                  {criterion.evidence_checks.length === 0 ? (
                                    <span className="pb-muted">No cited evidence checks</span>
                                  ) : (
                                    <ul className="pb-evidence-list">
                                      {criterion.evidence_checks.map((check: EvidenceCheck, idx) => {
                                        const status = getEvidenceStatus(check)
                                        const isActive =
                                          activeEvidence?.docId === check.doc_id &&
                                          status.status !== 'no-evidence'

                                        return (
                                          <li
                                            key={`${agent}-${criterion.criterion_id}-${idx}-${check.doc_id}`}
                                          >
                                            <EvidenceStatusButton
                                              check={check}
                                              isActive={isActive}
                                              onActivate={() => {
                                                setActiveEvidence({
                                                  docId: check.doc_id,
                                                  range: check.start_char != null && check.end_char != null
                                                    ? { start: check.start_char, end: check.end_char }
                                                    : null,
                                                })
                                              }}
                                            />
                                          </li>
                                          )
                                      })}
                                    </ul>
                                  )}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
