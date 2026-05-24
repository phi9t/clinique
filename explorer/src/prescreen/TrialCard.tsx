import type { ReactNode } from 'react'
import FieldTooltip from './FieldTooltip'
import type { SchemaPayload, TrialRecord } from './types'

interface TrialCardProps {
  trial: TrialRecord
  schema: SchemaPayload
}

function emphasizeEligibility(text: string): ReactNode[] {
  const lines = text.split('\n')
  return lines.map((line, index) => {
    const trimmed = line.trim()
    const isHeader =
      /^inclusion criteria/i.test(trimmed) ||
      /^exclusion criteria/i.test(trimmed)
    return (
      <span
        key={`${index}-${trimmed.slice(0, 20)}`}
        className={isHeader ? 'eligibility-header-line' : undefined}
      >
        {line}
        {index < lines.length - 1 ? '\n' : ''}
      </span>
    )
  })
}

export default function TrialCard({ trial, schema }: TrialCardProps) {
  return (
    <article className="trial-card">
      <header className="trial-card-header">
        <h3>{trial.trial_id}</h3>
        <p className="trial-title">{trial.title}</p>
      </header>

      <div className="trial-meta-grid">
        <div className="trial-meta-item">
          <FieldTooltip recordType="Trial" fieldName="phase" schema={schema}>
            Phase
          </FieldTooltip>
          <span className="attr-badge">{trial.phase ?? '—'}</span>
        </div>
        <div className="trial-meta-item">
          <FieldTooltip
            recordType="Trial"
            fieldName="recruitment_status"
            schema={schema}
          >
            Status
          </FieldTooltip>
          <span className="attr-badge">{trial.recruitment_status ?? '—'}</span>
        </div>
        <div className="trial-meta-item">
          <FieldTooltip recordType="Trial" fieldName="sex" schema={schema}>
            Sex
          </FieldTooltip>
          <span className="attr-badge">{trial.sex ?? '—'}</span>
        </div>
        <div className="trial-meta-item">
          <FieldTooltip recordType="Trial" fieldName="sponsor" schema={schema}>
            Sponsor
          </FieldTooltip>
          <span>{trial.sponsor ?? '—'}</span>
        </div>
      </div>

      {trial.conditions.length > 0 && (
        <div className="chip-row">
          <FieldTooltip recordType="Trial" fieldName="conditions" schema={schema}>
            Conditions
          </FieldTooltip>
          {trial.conditions.map((c) => (
            <span key={c} className="dataset-domain-badge">
              {c}
            </span>
          ))}
        </div>
      )}

      {trial.std_ages.length > 0 && (
        <div className="chip-row">
          <FieldTooltip recordType="Trial" fieldName="std_ages" schema={schema}>
            Std ages
          </FieldTooltip>
          {trial.std_ages.map((a) => (
            <span key={a} className="meta-type-tag">
              {a}
            </span>
          ))}
        </div>
      )}

      <div className="age-bounds-row">
        <div className="age-bound-block">
          <FieldTooltip
            recordType="Trial"
            fieldName="minimum_age"
            schema={schema}
          >
            Minimum age
          </FieldTooltip>
          <span>
            {trial.minimum_age.raw ?? '—'}
            {trial.minimum_age.years !== null &&
              ` (${trial.minimum_age.years} yrs)`}
          </span>
        </div>
        <div className="age-bound-block">
          <FieldTooltip
            recordType="Trial"
            fieldName="maximum_age"
            schema={schema}
          >
            Maximum age
          </FieldTooltip>
          <span>
            {trial.maximum_age.raw ?? '—'}
            {trial.maximum_age.years !== null &&
              ` (${trial.maximum_age.years} yrs)`}
          </span>
        </div>
        <div className="age-bound-block">
          <FieldTooltip
            recordType="Trial"
            fieldName="accepts_healthy_volunteers"
            schema={schema}
          >
            Healthy volunteers
          </FieldTooltip>
          <span>
            {trial.accepts_healthy_volunteers === null
              ? '—'
              : trial.accepts_healthy_volunteers
                ? 'Yes'
                : 'No'}
          </span>
        </div>
      </div>

      <section className="eligibility-section">
        <FieldTooltip
          recordType="Trial"
          fieldName="eligibility_text"
          schema={schema}
        >
          <h4>Eligibility text</h4>
        </FieldTooltip>
        <pre className="eligibility-text">
          {emphasizeEligibility(trial.eligibility_text)}
        </pre>
      </section>
    </article>
  )
}
