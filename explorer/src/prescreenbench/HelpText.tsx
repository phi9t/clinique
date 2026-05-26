import type { DefinitionsPayload } from './types'

export function HelpText({
  title,
  text,
}: {
  title: string
  text: string
}) {
  const label = `${title}: ${text}`

  return (
    <details className="pb-help">
      <summary title={label} aria-label={label}>
        ?
      </summary>
      <span className="pb-help-tooltip" role="tooltip">
        {text}
      </span>
    </details>
  )
}

export function MetricHelp({
  definitions,
  metric,
}: {
  definitions: DefinitionsPayload
  metric: string
}) {
  const text = definitions.metrics[metric]?.plain ?? metric
  return <HelpText title={metric} text={text} />
}
