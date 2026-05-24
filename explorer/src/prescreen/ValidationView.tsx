import type { ValidationPayload } from './types'

interface ValidationViewProps {
  validation: ValidationPayload
}

export default function ValidationView({ validation }: ValidationViewProps) {
  const grouped = validation.issues.reduce<
    Record<string, typeof validation.issues>
  >((acc, issue) => {
    const key = issue.code
    if (!acc[key]) acc[key] = []
    acc[key].push(issue)
    return acc
  }, {})

  const sortedCodes = Object.keys(grouped).sort()

  return (
    <div className="prescreen-validation">
      <div className="validation-summary-row">
        <div className={`attr-badge ${validation.ok ? 'validation-ok' : 'validation-fail'}`}>
          <span>Gate:</span>
          <strong>{validation.ok ? 'PASS' : 'FAIL'}</strong>
        </div>
        <div className="attr-badge">
          <span>Records checked:</span>
          <strong>{validation.records_checked}</strong>
        </div>
        <div className="attr-badge text-danger">
          <span>Errors:</span>
          <strong>{validation.error_count}</strong>
        </div>
        <div className="attr-badge text-warning">
          <span>Warnings:</span>
          <strong>{validation.warning_count}</strong>
        </div>
      </div>

      {sortedCodes.length === 0 ? (
        <div className="loading-container empty-detail" role="status">
          <p>No conformance issues found in the committed fixtures.</p>
        </div>
      ) : (
        <div className="validation-issue-groups">
          {sortedCodes.map((code) => {
            const issues = grouped[code]
            const isLeakage = code.includes('leakage')
            return (
              <section
                key={code}
                className={`validation-group ${isLeakage ? 'validation-group-leakage' : ''}`}
              >
                <h4>
                  {code}
                  {isLeakage && (
                    <span className="leakage-badge" role="note">
                      temporal leakage
                    </span>
                  )}
                  <span className="validation-group-count">
                    ({issues.length})
                  </span>
                </h4>
                <ul className="validation-issue-list" role="list">
                  {issues.map((issue) => (
                    <li
                      key={`${issue.record_id}-${issue.message}`}
                      className={`validation-issue-item severity-${issue.severity}`}
                    >
                      <span className="validation-severity-badge">
                        {issue.severity}
                      </span>
                      <span className="validation-record-id">{issue.record_id}</span>
                      <span>{issue.message}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
