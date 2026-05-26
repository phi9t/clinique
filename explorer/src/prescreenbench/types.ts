import { dataUrl } from '../lib/assets'

export interface ScoreReport {
  split: string
  benchmark_id: string
  cases: number
  criterion_total: number
  schema_valid_rate: number
  criterion_accuracy: number
  criterion_macro_f1: number
  evidence_support_accuracy: number
  blocking_criterion_recall: number
  overall_recommendation_accuracy: number
  unknown_precision: number
  unknown_recall: number
  unsafe_clearance_rate: number
  unsafe_clearance_count: number
  unsupported_decision_count: number
  fabricated_quote_count: number
  score: number
  hard_gate_breaches: string[]
  passed_hard_gates: boolean
  per_class_f1: Record<string, { precision: number; recall: number; f1: number; support: number }>
  errors: string[]
  patient_level_metrics?: {
    total: number
    accuracy: number | null
    per_class: Record<
      string,
      { precision: number; recall: number; f1: number; support: number }
    >
    confusion_matrix: Record<string, Record<string, number>>
  }
  per_criterion_metrics?: Array<{
    criterion_id: string
    criterion_type: 'inclusion' | 'exclusion'
    clinical_domain: string
    is_safety_critical: boolean
    support: number
    accuracy: number
    macro_f1: number
    per_class_f1: Record<string, { precision: number; recall: number; f1: number; support: number }>
    unsafe_clearance_rate: number
    unsafe_clearance_count: number
    unsupported_decision_count: number
    fabricated_quote_count: number
  }>
  agent?: string
}

export interface BenchmarkIndexEntry {
  split: string
  benchmark_id: string
  case_count: number
  agents: string[]
  task_types: string[]
}

export interface DefinitionsPayload {
  labels: Record<string, { plain: string }>
  recommendations: Record<string, { plain: string }>
  metrics: Record<string, { plain: string }>
  hard_gates: Record<string, number>
  primer: Record<string, string>
  field_docs: Record<string, Record<string, { type: string; description: string; vocab?: string[] }>>
  prediction_vocab: string[]
  recommendation_vocab: string[]
}

export interface EvidenceCheck {
  doc_id: string
  quote: string
  document_found: boolean
  quote_found: boolean
  empty_quote: boolean
  start_char: number | null
  end_char: number | null
}

export interface CriterionAnnotation {
  criterion_id: string
  criterion_text: string
  criterion_type: 'inclusion' | 'exclusion'
  clinical_domain: string
  is_safety_critical: boolean
  gold_label: string
  prediction: string
  correct: boolean
  evidence_present: boolean
  quotes_verbatim: boolean
  fabricated_quote_count: number
  unsupported_decision: boolean
  unsafe_clearance: boolean
  blocking_gold: boolean
  blocking_pred: boolean
  counts_toward_core_metrics: boolean
  counts_toward_gate_metrics: boolean
  schema_errors: string[]
  rationale: string
  evidence_checks: EvidenceCheck[]
}

export interface CaseGrader {
  case_id: string
  case_errors: string[]
  schema_errors: string[]
  overall_prediction: string | null
  overall_correct: boolean | null
  criteria: CriterionAnnotation[]
}

export interface BenchmarkAgent {
  agent: string
  report: ScoreReport
}

export interface BenchmarkCase {
  case_id: string
  trial_id: string
  patient_id: string
  patient_source: string
  snapshot_date: string | null
  task: string
}

export interface TrialRecord {
  trial_id: string
  title: string
  conditions: string[]
  phase: string | null
  recruitment_status: string | null
  eligibility_text: string
  sex: string | null
  minimum_age: { raw: string | null; years: number | null }
  maximum_age: { raw: string | null; years: number | null }
  sponsor: string | null
}

export interface PatientDocument {
  doc_id: string
  patient_id: string
  date: string | null
  source_type: string
  text: string
  structured: Record<string, unknown>
}

export interface PatientRecord {
  patient_id: string
  snapshot_date: string | null
  source: string
  demographics: Record<string, unknown>
  documents: PatientDocument[]
}

export interface GoldLabel {
  case_id: string
  overall_label: string
  criterion_labels: Array<{
    criterion_id: string
    label: string
    criterion_type: string
    clinical_domain: string
    is_safety_critical: boolean
  }>
}

export interface ExplorerCase {
  case: BenchmarkCase
  trial: TrialRecord | null
  patient: PatientRecord | null
  gold: GoldLabel
  agent_outputs: Record<string, unknown>
  grader: Record<string, CaseGrader>
}

export interface SplitBundle {
  split: string
  benchmark_id: string
  task_types: string[]
  agents: BenchmarkAgent[]
  cases: ExplorerCase[]
}

export const BENCHMARK_BASE = dataUrl('data/prescreenbench')

export async function fetchBenchmarkJson<T>(filename: string): Promise<T> {
  const res = await fetch(`${BENCHMARK_BASE}/${filename}?t=${Date.now()}`)
  if (!res.ok) {
    throw new Error(`Failed to load ${filename} (HTTP ${res.status})`)
  }
  return res.json() as Promise<T>
}

export function formatMetric(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3)
}
