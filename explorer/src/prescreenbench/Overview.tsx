import { CheckCircle2, ShieldAlert } from 'lucide-react'
import { MetricHelp } from './HelpText'
import { formatMetric } from './types'
import type { DefinitionsPayload, ScoreReport, SplitBundle } from './types'

const METRICS = [
  'score',
  'criterion_macro_f1',
  'evidence_support_accuracy',
  'unsafe_clearance_rate',
  'unsupported_decision_count',
  'fabricated_quote_count',
  'schema_valid_rate',
] as const

type MetricKey = (typeof METRICS)[number]

function metricValue(report: ScoreReport, metric: MetricKey): number {
  return report[metric]
}

function metricLabel(metric: string): string {
  return metric.replaceAll('_', ' ')
}

function formatOptionalMetric(value: number | null | undefined): string {
  return typeof value === 'number' ? formatMetric(value) : 'n/a'
}

export default function Overview({
  bundle,
  definitions,
  selectedAgents,
  onToggleAgent,
}: {
  bundle: SplitBundle
  definitions: DefinitionsPayload
  selectedAgents: string[]
  onToggleAgent: (agent: string) => void
}) {
  const selectedAgentSet = new Set(selectedAgents)
  const visibleAgents = bundle.agents.filter(({ agent }) => selectedAgentSet.has(agent))

  return (
    <section className="pb-overview" aria-label="PrescreenBench overview">
      <div className="pb-agent-row" role="group" aria-label="Agent filters">
        {bundle.agents.map(({ agent, report }) => {
          const passed = report.passed_hard_gates
          return (
            <label key={agent} className="pb-agent-toggle">
              <input
                type="checkbox"
                checked={selectedAgentSet.has(agent)}
                onChange={() => onToggleAgent(agent)}
              />
              {passed ? (
                <CheckCircle2 size={16} className="text-success" aria-hidden="true" />
              ) : (
                <ShieldAlert size={16} className="text-danger" aria-hidden="true" />
              )}
              <span>{agent}</span>
            </label>
          )
        })}
      </div>

      <div className="pb-metric-grid">
        {visibleAgents.map(({ agent, report }) => {
          const passed = report.passed_hard_gates
          return (
            <article key={agent} className="pb-agent-card">
              <div className="pb-agent-card-header">
                <h3>{agent}</h3>
                <p className={passed ? 'pb-gate-pass' : 'pb-gate-fail'}>
                  {passed ? (
                    <CheckCircle2 size={16} aria-hidden="true" />
                  ) : (
                    <ShieldAlert size={16} aria-hidden="true" />
                  )}
                  <span>
                    {passed
                      ? 'Hard gates pass'
                      : `Hard gates fail: ${report.hard_gate_breaches.join(', ')}`}
                  </span>
                </p>
              </div>

              <dl className="pb-metrics">
                {METRICS.map((metric) => (
                  <div key={metric}>
                    <dt>
                      <span>{metricLabel(metric)}</span>
                      <MetricHelp definitions={definitions} metric={metric} />
                    </dt>
                    <dd>{formatMetric(Number(metricValue(report, metric)))}</dd>
                  </div>
                ))}
              </dl>
            </article>
          )
        })}
      </div>

      {visibleAgents.length === 0 && (
        <p className="text-muted text-center">Select at least one agent to compare metrics.</p>
      )}

      {visibleAgents.length > 0 && (
        <section className="pb-metric-detail" aria-label="Patient-level metrics">
          <div className="pb-metric-detail-header">
            <h3>Patient-level metrics</h3>
            <MetricHelp definitions={definitions} metric="patient_level_metrics" />
          </div>

          <div className="pb-metric-table-wrapper">
            <table className="pb-metric-table">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col">Evaluated cases</th>
                  <th scope="col">Patient accuracy</th>
                  <th scope="col">Recommendation classes</th>
                </tr>
              </thead>
              <tbody>
                {visibleAgents.map(({ agent, report }) => {
                  const patientMetrics = report.patient_level_metrics
                  const perClass = patientMetrics?.per_class ?? {}
                  const classLabels = Object.entries(perClass)
                    .map(([label, metrics]) => `${label}: F1 ${formatMetric(metrics.f1)}`)
                    .join(', ')

                  return (
                    <tr key={`patient-${agent}`}>
                      <th scope="row">{agent}</th>
                      <td>{patientMetrics?.total ?? 0}</td>
                      <td>{formatOptionalMetric(patientMetrics?.accuracy)}</td>
                      <td>{classLabels || 'No recommendation cases'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {visibleAgents.length > 0 && (
        <section className="pb-metric-detail" aria-label="Per-criterion metrics">
          <div className="pb-metric-detail-header">
            <h3>Per-criterion metrics</h3>
            <MetricHelp definitions={definitions} metric="per_criterion_metrics" />
          </div>

          <div className="pb-metric-table-wrapper">
            <table className="pb-metric-table">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col">Criterion</th>
                  <th scope="col">Type</th>
                  <th scope="col">Domain</th>
                  <th scope="col">Support</th>
                  <th scope="col">Accuracy</th>
                  <th scope="col">Macro F1</th>
                  <th scope="col">Unsafe clearances</th>
                  <th scope="col">Unsupported</th>
                  <th scope="col">Fabricated quotes</th>
                </tr>
              </thead>
              <tbody>
                {visibleAgents.flatMap(({ agent, report }) => {
                  const rows = report.per_criterion_metrics ?? []

                  if (rows.length === 0) {
                    return [
                      <tr key={`criterion-empty-${agent}`}>
                        <th scope="row">{agent}</th>
                        <td colSpan={9}>No criterion metrics available</td>
                      </tr>,
                    ]
                  }

                  return rows.map((criterion) => (
                    <tr key={`criterion-${agent}-${criterion.criterion_id}`}>
                      <th scope="row">{agent}</th>
                      <td>
                        <span className="pb-criterion-id">{criterion.criterion_id}</span>
                        {criterion.is_safety_critical && (
                          <span className="pb-safety-flag">safety</span>
                        )}
                      </td>
                      <td>{criterion.criterion_type}</td>
                      <td>{criterion.clinical_domain}</td>
                      <td>{criterion.support}</td>
                      <td>{formatMetric(criterion.accuracy)}</td>
                      <td>{formatMetric(criterion.macro_f1)}</td>
                      <td>
                        {criterion.unsafe_clearance_count}
                        {' / '}
                        {formatMetric(criterion.unsafe_clearance_rate)}
                      </td>
                      <td>{criterion.unsupported_decision_count}</td>
                      <td>{criterion.fabricated_quote_count}</td>
                    </tr>
                  ))
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </section>
  )
}
