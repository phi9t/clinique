import { useEffect, useMemo, useState } from 'react'
import { Info } from 'lucide-react'
import CaseTable from './CaseTable'
import type { SliceFilter } from './CaseTable'
import Overview from './Overview'
import CaseDeepDive from './CaseDeepDive'
import { fetchBenchmarkJson } from './types'
import type { BenchmarkIndexEntry, DefinitionsPayload, SplitBundle } from './types'

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function fallbackIndexEntry(split: string): BenchmarkIndexEntry {
  return {
    split,
    benchmark_id: 'prescreenbench',
    case_count: 0,
    agents: [],
    task_types: [],
  }
}

export default function PrescreenBenchExplorer() {
  const [index, setIndex] = useState<BenchmarkIndexEntry[]>([])
  const [definitions, setDefinitions] = useState<DefinitionsPayload | null>(null)
  const [selectedSplit, setSelectedSplit] = useState('synthetic')
  const [bundle, setBundle] = useState<SplitBundle | null>(null)
  const [selectedAgents, setSelectedAgents] = useState<string[]>([])
  const [loadingCore, setLoadingCore] = useState(true)
  const [loadingBundle, setLoadingBundle] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeFilters, setActiveFilters] = useState<SliceFilter[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)

  useEffect(() => {
    async function loadCore() {
      try {
        setLoadingCore(true)
        setError(null)
        const [indexData, definitionsData] = await Promise.all([
          fetchBenchmarkJson<BenchmarkIndexEntry[]>('index.json'),
          fetchBenchmarkJson<DefinitionsPayload>('definitions.json'),
        ])
        setIndex(indexData)
        setDefinitions(definitionsData)
        setSelectedSplit(indexData[0]?.split ?? 'synthetic')
      } catch (err: unknown) {
        setError(errorMessage(err))
      } finally {
        setLoadingCore(false)
      }
    }
    void loadCore()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadSplitBundle() {
      try {
        setLoadingBundle(true)
        setError(null)
        const bundleData = await fetchBenchmarkJson<SplitBundle>(`${selectedSplit}.json`)
        if (cancelled) return
        setBundle(bundleData)
        setSelectedAgents(bundleData.agents.map(({ agent }) => agent))
        setSelectedCaseId(bundleData.cases[0]?.case?.case_id ?? null)
        setActiveFilters([])
      } catch (err: unknown) {
        if (!cancelled) {
          setBundle(null)
          setSelectedAgents([])
          setSelectedCaseId(null)
          setActiveFilters([])
          setError(errorMessage(err))
        }
      } finally {
        if (!cancelled) {
          setLoadingBundle(false)
        }
      }
    }

    void loadSplitBundle()

    return () => {
      cancelled = true
    }
  }, [selectedSplit])

  const splitOptions = useMemo(
    () => (index.length > 0 ? index : [fallbackIndexEntry('synthetic')]),
    [index],
  )

  const selectedEntry = useMemo(
    () => splitOptions.find((entry) => entry.split === selectedSplit) ?? splitOptions[0],
    [selectedSplit, splitOptions],
  )

  const selectedCase = useMemo(() => {
    if (!bundle || !selectedCaseId) {
      return null
    }

    return bundle.cases.find((caseRow) => caseRow.case.case_id === selectedCaseId) ?? null
  }, [bundle, selectedCaseId])

  const handleToggleAgent = (agent: string) => {
    setSelectedAgents((current) =>
      current.includes(agent)
        ? current.filter((selectedAgent) => selectedAgent !== agent)
        : [...current, agent],
    )
  }

  if (loadingCore) {
    return (
      <div className="loading-container" role="status" aria-live="polite">
        <div className="spinner" aria-hidden="true" />
        <p>Loading PrescreenBench data...</p>
      </div>
    )
  }

  if (error || !definitions) {
    return (
      <div className="loading-container" role="alert">
        <Info size={48} className="text-danger" aria-hidden="true" />
        <h2>PrescreenBench Explorer Error</h2>
        <p>{error ?? 'Missing PrescreenBench definitions.'}</p>
        <p className="text-muted">
          Run: uv run clinique benchmark prescreen export-explorer
        </p>
      </div>
    )
  }

  return (
    <section className="pb-shell" aria-label="PrescreenBench Explorer">
      <div className="pb-toolbar">
        <div className="dataset-title-meta">
          <h2>PrescreenBench</h2>
          <p>Agent comparison and evidence-grounded grader analysis.</p>
        </div>

        <label className="pb-split-control">
          <span>Split</span>
          <select
            value={selectedSplit}
            onChange={(event) => setSelectedSplit(event.target.value)}
            disabled={loadingBundle}
          >
            {splitOptions.map((entry) => (
              <option key={entry.split} value={entry.split}>
                {entry.split} ({entry.case_count} cases)
              </option>
            ))}
          </select>
        </label>
      </div>

      <p className="pb-caveat">
        {selectedEntry?.benchmark_id ?? 'PrescreenBench'} seed splits support benchmark debugging,
        not clinical capability claims. Hard gates summarize schema failures, unsupported decisions,
        fabricated quotes, and unsafe clearance; benchmark packets are review aids, not enrollment
        decisions.
      </p>

      {loadingBundle || !bundle ? (
        <div className="loading-container" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p>Loading {selectedSplit} split...</p>
        </div>
      ) : (
        <>
          <Overview
            bundle={bundle}
            definitions={definitions}
            selectedAgents={selectedAgents}
            onToggleAgent={handleToggleAgent}
          />
          <CaseTable
            cases={bundle.cases}
            selectedAgents={selectedAgents}
            activeFilters={activeFilters}
            onToggleFilter={(filter) =>
              setActiveFilters((current) =>
                current.includes(filter)
                  ? current.filter((item) => item !== filter)
                  : [...current, filter],
              )
            }
            selectedCaseId={selectedCaseId}
            onSelectCase={setSelectedCaseId}
          />
          <CaseDeepDive
            key={selectedCase?.case.case_id ?? 'no-case'}
            caseRow={selectedCase}
            selectedAgents={selectedAgents}
          />
        </>
      )}
    </section>
  )
}
