export interface Provenance {
  license: string
  fixture_path: string
  record_command: string
  snapshot_semantics: string
}

export interface IndexEntry {
  key: string
  family: 'trial' | 'patient'
  label: string
  source: string
  record_type: string
  count: number
  provenance: Provenance
}

export interface FieldDoc {
  type: string
  description: string
  vocab?: string[]
}

export interface PipelineStep {
  step: string
  description: string
}

export interface SchemaPayload {
  records: Record<string, Record<string, FieldDoc>>
  vocab_gloss: Record<string, string>
  pipeline: PipelineStep[]
}

export interface CountBucket {
  label: string
  count: number
}

export interface MissingnessEntry {
  field: string
  rate: number
}

export interface TrialStats {
  count: number
  phase: CountBucket[]
  recruitment_status: CountBucket[]
  sex: CountBucket[]
  std_ages: CountBucket[]
  conditions_per_trial: CountBucket[]
  age_bound_coverage: CountBucket[]
  minimum_age_years: CountBucket[]
  eligibility_text_length: CountBucket[]
  missingness: MissingnessEntry[]
}

export interface PatientStats {
  count: number
  docs_per_patient: CountBucket[]
  source_type: CountBucket[]
  sex: CountBucket[]
  age: CountBucket[]
  document_date_present: CountBucket[]
  missingness: MissingnessEntry[]
}

export interface StatsPayload {
  trials: TrialStats
  patients: {
    synthea: PatientStats
    pmc: PatientStats
    mimic: PatientStats
  }
}

export interface ValidationIssue {
  record_id: string
  severity: 'error' | 'warning'
  code: string
  message: string
}

export interface ValidationPayload {
  records_checked: number
  error_count: number
  warning_count: number
  ok: boolean
  issues: ValidationIssue[]
}

export interface AgeBoundRecord {
  raw: string | null
  years: number | null
}

export interface TrialRecord {
  trial_id: string
  source: string
  title: string
  conditions: string[]
  phase: string | null
  recruitment_status: string | null
  eligibility_text: string
  sex: string | null
  accepts_healthy_volunteers: boolean | null
  minimum_age: AgeBoundRecord
  maximum_age: AgeBoundRecord
  std_ages: string[]
  sponsor: string | null
  metadata: Record<string, unknown>
}

export interface PatientDocumentRecord {
  doc_id: string
  patient_id: string
  date: string | null
  source_type: string
  text: string
  structured: Record<string, unknown>
}

export interface PatientCorpusRecord {
  patient_id: string
  snapshot_date: string | null
  source: string
  demographics: Record<string, unknown>
  documents: PatientDocumentRecord[]
}

export type PrescreenTabId = 'schema' | 'datasets' | 'stats' | 'validation'

export type DatasetKey =
  | 'trials'
  | 'patients_synthea'
  | 'patients_pmc'
  | 'patients_mimic'

export const PRESCREEN_TAB_ORDER: PrescreenTabId[] = [
  'schema',
  'datasets',
  'stats',
  'validation',
]

export const DATA_BASE = '/data/prescreen'

export async function fetchPrescreenJson<T>(filename: string): Promise<T> {
  const res = await fetch(`${DATA_BASE}/${filename}?t=${Date.now()}`)
  if (!res.ok) {
    throw new Error(`Failed to load ${filename} (HTTP ${res.status})`)
  }
  return res.json() as Promise<T>
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Unknown error'
}
