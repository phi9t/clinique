import type { DefinitionsPayload } from './types'

export function HelpText({
  title,
  text,
}: {
  title: string
  text: string
}) {
  return (
    <span className="pb-help" title={`${title}: ${text}`} aria-label={`${title}: ${text}`}>
      ?
    </span>
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
