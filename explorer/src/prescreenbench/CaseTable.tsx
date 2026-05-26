/* eslint-disable react-refresh/only-export-components */

import type { CriterionAnnotation, ExplorerCase } from './types'

type CaseRecommendation = {
  agent: string
  recommendation: string
}

export type SliceFilter =
  | 'incorrect'
  | 'unsafe'
  | 'unsupported'
  | 'fabricated'
  | 'schema'
  | 'gold_unknown'
  | 'pred_unknown'
  | 'inclusion'
  | 'exclusion'
  | 'safety_critical'

export const SLICE_FILTERS: Array<{ id: SliceFilter; label: string }> = [
  { id: 'incorrect', label: 'Incorrect' },
  { id: 'unsafe', label: 'Unsafe clearance' },
  { id: 'unsupported', label: 'Unsupported decision' },
  { id: 'fabricated', label: 'Fabricated quote' },
  { id: 'schema', label: 'Schema issue' },
  { id: 'gold_unknown', label: 'Gold unknown' },
  { id: 'pred_unknown', label: 'Predicted unknown' },
  { id: 'inclusion', label: 'Inclusion criteria' },
  { id: 'exclusion', label: 'Exclusion criteria' },
  { id: 'safety_critical', label: 'Safety critical' },
]

function normalizeAgents(criteriaAgents: string[], row: ExplorerCase): CriterionAnnotation[] {
  return criteriaAgents.flatMap((agent) => row.grader[agent]?.criteria ?? [])
}

export function caseMatches(row: ExplorerCase, agents: string[], filter: SliceFilter): boolean {
  const criteria = normalizeAgents(agents, row)

  if (filter === 'schema') {
    return agents.some((agent) => (row.grader[agent]?.schema_errors ?? []).length > 0)
  }

  return criteria.some((criterion) => {
    if (filter === 'incorrect') {
      return !criterion.correct && criterion.counts_toward_core_metrics
    }
    if (filter === 'unsafe') {
      return criterion.unsafe_clearance
    }
    if (filter === 'unsupported') {
      return criterion.unsupported_decision
    }
    if (filter === 'fabricated') {
      return criterion.fabricated_quote_count > 0
    }
    if (filter === 'gold_unknown') {
      return criterion.gold_label === 'unknown'
    }
    if (filter === 'pred_unknown') {
      return criterion.prediction === 'unknown'
    }
    if (filter === 'inclusion') {
      return criterion.criterion_type === 'inclusion'
    }
    if (filter === 'exclusion') {
      return criterion.criterion_type === 'exclusion'
    }

    return criterion.is_safety_critical
  })
}

function worstBadge(row: ExplorerCase, selectedAgents: string[]): string {
  const criteria = normalizeAgents(selectedAgents, row)

  if (criteria.some((criterion) => criterion.unsafe_clearance)) {
    return 'unsafe clearance'
  }
  if (criteria.some((criterion) => criterion.fabricated_quote_count > 0)) {
    return 'fabricated quote'
  }
  if (criteria.some((criterion) => criterion.unsupported_decision)) {
    return 'unsupported decision'
  }
  if (criteria.some((criterion) => !criterion.correct && criterion.counts_toward_core_metrics)) {
    return 'incorrect'
  }

  return 'none'
}

function caseRecommendations(
  row: ExplorerCase,
  selectedAgents: string[],
): CaseRecommendation[] {
  return selectedAgents
    .map((agent) => {
      const output = row.grader[agent]
      return {
        agent,
        recommendation: output?.overall_prediction ?? 'No submission',
      }
    })
    .filter((entry) => entry.recommendation)
}

function evidenceIssueCount(row: ExplorerCase, selectedAgents: string[]): number {
  const criteria = normalizeAgents(selectedAgents, row)

  return criteria.reduce((total, criterion) => {
    if (
      criterion.unsupported_decision ||
      criterion.fabricated_quote_count > 0 ||
      criterion.unsafe_clearance ||
      !criterion.evidence_present
    ) {
      return total + 1
    }

    return total
  }, 0)
}

export default function CaseTable({
  cases,
  selectedAgents,
  activeFilters,
  onToggleFilter,
  selectedCaseId,
  onSelectCase,
}: {
  cases: ExplorerCase[]
  selectedAgents: string[]
  activeFilters: SliceFilter[]
  onToggleFilter: (filter: SliceFilter) => void
  selectedCaseId: string | null
  onSelectCase: (caseId: string) => void
}) {
  const filteredCases = cases.filter((caseRow) =>
    activeFilters.every((filter) => caseMatches(caseRow, selectedAgents, filter)),
  )

  return (
    <section className="pb-case-section" aria-label="Case table">
      <div className="pb-filter-row" aria-label="Metric slices">
        {SLICE_FILTERS.map((filter) => {
          const isActive = activeFilters.includes(filter.id)

          return (
            <button
              type="button"
              key={filter.id}
              className={isActive ? 'pb-filter active' : 'pb-filter'}
              aria-pressed={isActive}
              onClick={() => onToggleFilter(filter.id)}
            >
              {filter.label}
            </button>
          )
        })}
      </div>

      {filteredCases.length === 0 ? (
        <p className="text-muted text-center pb-empty-case-state">No cases match the active metric filters.</p>
      ) : (
        <div className="table-wrapper">
          <table className="pb-case-table">
            <thead>
              <tr>
                <th scope="col">Case</th>
                <th scope="col">Trial</th>
                <th scope="col">Patient</th>
                <th scope="col">Task</th>
                <th scope="col">Gold overall</th>
                <th scope="col">Agent recommendations</th>
                <th scope="col">Worst failure</th>
                <th scope="col">Criteria</th>
                <th scope="col">Evidence issues</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.map((caseRow) => {
                const trial = caseRow.trial
                const patient = caseRow.patient
                const recommendations = caseRecommendations(caseRow, selectedAgents)
                const issueCount = evidenceIssueCount(caseRow, selectedAgents)
                const worst = worstBadge(caseRow, selectedAgents)

                return (
                  <tr
                    key={caseRow.case.case_id}
                    className={selectedCaseId === caseRow.case.case_id ? 'active-row' : ''}
                  >
                    <td>
                      <button type="button" onClick={() => onSelectCase(caseRow.case.case_id)}>
                        {caseRow.case.case_id}
                      </button>
                    </td>
                    <td>
                      <span
                        className="pb-table-cell-compact"
                        title={trial?.title ?? caseRow.case.trial_id}
                      >
                        {trial?.trial_id ? `${trial.trial_id}: ${trial.title}` : caseRow.case.trial_id}
                      </span>
                    </td>
                    <td>
                      <span
                        className="pb-table-cell-compact"
                        title={patient ? `${patient.patient_id} (${patient.source})` : `${caseRow.case.patient_id}`}
                      >
                        {patient
                          ? `${patient.patient_id} (${patient.source})`
                          : `${caseRow.case.patient_id}`}
                      </span>
                    </td>
                    <td>{caseRow.case.task}</td>
                    <td>{caseRow.gold.overall_label}</td>
                    <td>
                      {recommendations.length === 0 ? (
                        <span className="text-muted">Not available</span>
                      ) : (
                        <ul className="pb-cell-list" aria-label="Agent recommendations">
                          {recommendations.map((entry) => (
                            <li key={entry.agent}>
                              <span className="pb-recommendation-agent">{entry.agent}</span>:
                              {' '}
                              <span className="pb-recommendation-value">{entry.recommendation}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td>
                      <span
                        className={`pb-badge ${
                          worst === 'none' ? 'pb-badge-ok' : 'pb-badge-warning'
                        }`}
                      >
                        {worst}
                      </span>
                    </td>
                    <td>{caseRow.gold.criterion_labels.length}</td>
                    <td>{issueCount}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
