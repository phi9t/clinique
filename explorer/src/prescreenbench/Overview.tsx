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
    </section>
  )
}
