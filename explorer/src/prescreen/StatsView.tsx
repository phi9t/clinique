import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import FieldTooltip from './FieldTooltip'
import type { SchemaPayload, StatsPayload } from './types'

interface StatsViewProps {
  stats: StatsPayload
  schema: SchemaPayload
}

function CountChart({
  title,
  data,
  recordType,
  fieldName,
  schema,
}: {
  title: string
  data: Array<{ label: string; count: number }>
  recordType: string
  fieldName: string
  schema: SchemaPayload
}) {
  if (data.length === 0) return null
  return (
    <div className="chart-card">
      <h4>
        <FieldTooltip recordType={recordType} fieldName={fieldName} schema={schema}>
          {title}
        </FieldTooltip>
      </h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis
            dataKey="label"
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            angle={-30}
            textAnchor="end"
            interval={0}
            height={60}
          />
          <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: '#111827',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8,
            }}
          />
          <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function MissingnessPanel({
  title,
  missingness,
}: {
  title: string
  missingness: Array<{ field: string; rate: number }>
}) {
  return (
    <div className="chart-card missingness-panel">
      <h4>{title} — missingness</h4>
      <table className="schema-field-table">
        <caption className="visually-hidden">Missingness rates for {title}</caption>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Missing rate</th>
          </tr>
        </thead>
        <tbody>
          {missingness.map((m) => (
            <tr key={m.field}>
              <td>{m.field}</td>
              <td>{(m.rate * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function StatsView({ stats, schema }: StatsViewProps) {
  const patientSources = [
    { key: 'synthea', label: 'Synthea' },
    { key: 'pmc', label: 'PMC-Patients' },
    { key: 'mimic', label: 'MIMIC-IV demo' },
  ] as const

  return (
    <div className="prescreen-stats">
      <section aria-label="Trial statistics">
        <h3 className="stats-section-title">Trials ({stats.trials.count})</h3>
        <div className="chart-grid">
          <CountChart
            title="Phase"
            data={stats.trials.phase}
            recordType="Trial"
            fieldName="phase"
            schema={schema}
          />
          <CountChart
            title="Recruitment status"
            data={stats.trials.recruitment_status}
            recordType="Trial"
            fieldName="recruitment_status"
            schema={schema}
          />
          <CountChart
            title="Eligible sex"
            data={stats.trials.sex}
            recordType="Trial"
            fieldName="sex"
            schema={schema}
          />
          <CountChart
            title="Minimum age (years)"
            data={stats.trials.minimum_age_years}
            recordType="Trial"
            fieldName="minimum_age"
            schema={schema}
          />
          <CountChart
            title="Eligibility text length"
            data={stats.trials.eligibility_text_length}
            recordType="Trial"
            fieldName="eligibility_text"
            schema={schema}
          />
          <MissingnessPanel
            title="Trial"
            missingness={stats.trials.missingness}
          />
        </div>
      </section>

      {patientSources.map(({ key, label }) => {
        const patientStats = stats.patients[key]
        return (
          <section key={key} aria-label={`${label} statistics`}>
            <h3 className="stats-section-title">
              {label} ({patientStats.count})
            </h3>
            <div className="chart-grid">
              <CountChart
                title="Document source types"
                data={patientStats.source_type}
                recordType="PatientDocument"
                fieldName="source_type"
                schema={schema}
              />
              <CountChart
                title="Patient sex"
                data={patientStats.sex}
                recordType="PatientCorpus"
                fieldName="demographics"
                schema={schema}
              />
              <CountChart
                title="Patient age"
                data={patientStats.age}
                recordType="PatientCorpus"
                fieldName="demographics"
                schema={schema}
              />
              <CountChart
                title="Documents per patient"
                data={patientStats.docs_per_patient}
                recordType="PatientCorpus"
                fieldName="documents"
                schema={schema}
              />
              <MissingnessPanel
                title={label}
                missingness={patientStats.missingness}
              />
            </div>
          </section>
        )
      })}
    </div>
  )
}
