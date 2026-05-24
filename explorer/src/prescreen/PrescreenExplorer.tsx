import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  BarChart3,
  BookOpen,
  Database,
  Info,
  Layers,
  ShieldCheck,
  Users,
} from 'lucide-react'
import DatasetView from './DatasetView'
import ProvenancePanel from './ProvenancePanel'
import SchemaView from './SchemaView'
import StatsView from './StatsView'
import ValidationView from './ValidationView'
import {
  PRESCREEN_TAB_ORDER,
  errorMessage,
  fetchPrescreenJson,
} from './types'
import type {
  IndexEntry,
  PatientCorpusRecord,
  PrescreenTabId,
  SchemaPayload,
  StatsPayload,
  TrialRecord,
  ValidationPayload,
} from './types'

export default function PrescreenExplorer() {
  const [index, setIndex] = useState<IndexEntry[]>([])
  const [schema, setSchema] = useState<SchemaPayload | null>(null)
  const [stats, setStats] = useState<StatsPayload | null>(null)
  const [validation, setValidation] = useState<ValidationPayload | null>(null)
  const [activeTab, setActiveTab] = useState<PrescreenTabId>('schema')

  const [trials, setTrials] = useState<TrialRecord[] | null>(null)
  const [synthea, setSynthea] = useState<PatientCorpusRecord[] | null>(null)
  const [pmc, setPmc] = useState<PatientCorpusRecord[] | null>(null)
  const [mimic, setMimic] = useState<PatientCorpusRecord[] | null>(null)

  const [loadingCore, setLoadingCore] = useState(true)
  const [loadingRecords, setLoadingRecords] = useState(false)
  const [recordsLoaded, setRecordsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recordsError, setRecordsError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState('')

  useEffect(() => {
    async function loadCore() {
      try {
        setLoadingCore(true)
        const [indexData, schemaData, statsData, validationData] =
          await Promise.all([
            fetchPrescreenJson<IndexEntry[]>('index.json'),
            fetchPrescreenJson<SchemaPayload>('schema.json'),
            fetchPrescreenJson<StatsPayload>('stats.json'),
            fetchPrescreenJson<ValidationPayload>('validation.json'),
          ])
        setIndex(indexData)
        setSchema(schemaData)
        setStats(statsData)
        setValidation(validationData)
        setStatusMessage('Loaded prescreen L0 metadata.')
      } catch (err: unknown) {
        setError(errorMessage(err))
      } finally {
        setLoadingCore(false)
      }
    }
    void loadCore()
  }, [])

  const loadRecords = useCallback(async () => {
    if (recordsLoaded || loadingRecords) return
    try {
      setLoadingRecords(true)
      setRecordsError(null)
      const [trialsData, syntheaData, pmcData, mimicData] = await Promise.all([
        fetchPrescreenJson<TrialRecord[]>('trials.json'),
        fetchPrescreenJson<PatientCorpusRecord[]>('patients_synthea.json'),
        fetchPrescreenJson<PatientCorpusRecord[]>('patients_pmc.json'),
        fetchPrescreenJson<PatientCorpusRecord[]>('patients_mimic.json'),
      ])
      setTrials(trialsData)
      setSynthea(syntheaData)
      setPmc(pmcData)
      setMimic(mimicData)
      setRecordsLoaded(true)
      setStatusMessage('Loaded prescreen L0 records for drill-down.')
    } catch (err: unknown) {
      setRecordsError(errorMessage(err))
    } finally {
      setLoadingRecords(false)
    }
  }, [recordsLoaded, loadingRecords])

  const handleSelectTab = (tabId: PrescreenTabId) => {
    setActiveTab(tabId)
    if (tabId === 'datasets') {
      void loadRecords()
    }
  }

  const headerMetrics = useMemo(() => {
    const trialCount = index.find((e) => e.key === 'trials')?.count ?? 0
    const patientCount = index
      .filter((e) => e.family === 'patient')
      .reduce((sum, e) => sum + e.count, 0)
    return { trialCount, patientCount }
  }, [index])

  const handleTabKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    tabId: PrescreenTabId,
  ) => {
    const currentIndex = PRESCREEN_TAB_ORDER.indexOf(tabId)
    let nextIndex: number | null = null

    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault()
      nextIndex = (currentIndex + 1) % PRESCREEN_TAB_ORDER.length
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault()
      nextIndex =
        (currentIndex - 1 + PRESCREEN_TAB_ORDER.length) %
        PRESCREEN_TAB_ORDER.length
    } else if (event.key === 'Home') {
      event.preventDefault()
      nextIndex = 0
    } else if (event.key === 'End') {
      event.preventDefault()
      nextIndex = PRESCREEN_TAB_ORDER.length - 1
    }

    if (nextIndex === null) return
    const nextTab = PRESCREEN_TAB_ORDER[nextIndex]
    setActiveTab(nextTab)
    if (nextTab === 'datasets') {
      void loadRecords()
    }
    document.getElementById(`prescreen-tab-${nextTab}`)?.focus()
  }

  if (loadingCore) {
    return (
      <div className="loading-container" role="status" aria-live="polite">
        <div className="spinner" aria-hidden="true" />
        <p>Loading prescreen L0 data...</p>
      </div>
    )
  }

  if (error || !schema || !stats || !validation) {
    return (
      <div className="loading-container" role="alert">
        <Info size={48} className="text-danger" aria-hidden="true" />
        <h2>Prescreen Explorer Error</h2>
        <p>{error ?? 'Missing prescreen data.'}</p>
        <p className="text-muted">
          Run: uv run clinique prescreen export-explorer
        </p>
      </div>
    )
  }

  return (
    <>
      <div
        className="visually-hidden"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {statusMessage}
      </div>

      <div className="prescreen-stats-row global-stats">
        <div className="stat-chip">
          <Layers size={16} className="text-primary" aria-hidden="true" />
          <span>Trials:</span>
          <span className="stat-value">{headerMetrics.trialCount}</span>
        </div>
        <div className="stat-chip">
          <Users size={16} className="text-secondary" aria-hidden="true" />
          <span>Patients:</span>
          <span className="stat-value">{headerMetrics.patientCount}</span>
        </div>
        <div className="stat-chip">
          <ShieldCheck
            size={16}
            className={validation.ok ? 'text-success' : 'text-danger'}
            aria-hidden="true"
          />
          <span>Validation:</span>
          <span className="stat-value">
            {validation.ok ? 'PASS' : `${validation.error_count} errors`}
          </span>
        </div>
      </div>

      <section
        className={`${activeTab === 'datasets' ? '' : 'card-view '}prescreen-main-panel`}
        aria-label="Prescreen views"
      >
        <div className="tab-row" role="tablist" aria-label="Prescreen views">
          {PRESCREEN_TAB_ORDER.map((tabId) => {
            const labels: Record<PrescreenTabId, string> = {
              schema: 'Schema & data model',
              datasets: 'Datasets',
              stats: 'Stats & distributions',
              validation: 'Validation & provenance',
            }
            const icons = {
              schema: <BookOpen size={16} aria-hidden="true" />,
              datasets: <Database size={16} aria-hidden="true" />,
              stats: <BarChart3 size={16} aria-hidden="true" />,
              validation: <ShieldCheck size={16} aria-hidden="true" />,
            } as const
            return (
              <button
                key={tabId}
                type="button"
                role="tab"
                id={`prescreen-tab-${tabId}`}
                aria-selected={activeTab === tabId}
                aria-controls={`prescreen-panel-${tabId}`}
                tabIndex={activeTab === tabId ? 0 : -1}
                onClick={() => handleSelectTab(tabId)}
                onKeyDown={(e) => handleTabKeyDown(e, tabId)}
                className={`tab-button ${activeTab === tabId ? 'active' : ''}`}
              >
                {icons[tabId]}
                <span>{labels[tabId]}</span>
              </button>
            )
          })}
        </div>

        <div
          role="tabpanel"
          id="prescreen-panel-schema"
          aria-labelledby="prescreen-tab-schema"
          aria-hidden={activeTab !== 'schema'}
          className={`tab-panel ${activeTab === 'schema' ? 'tab-panel-active' : 'tab-panel-inactive'}`}
        >
          {activeTab === 'schema' && <SchemaView schema={schema} />}
        </div>

        <div
          role="tabpanel"
          id="prescreen-panel-datasets"
          aria-labelledby="prescreen-tab-datasets"
          aria-hidden={activeTab !== 'datasets'}
          className={`tab-panel ${activeTab === 'datasets' ? 'tab-panel-active' : 'tab-panel-inactive'}`}
        >
          {activeTab === 'datasets' && (
            <DatasetView
              index={index}
              schema={schema}
              trials={trials}
              synthea={synthea}
              pmc={pmc}
              mimic={mimic}
              loadingRecords={loadingRecords}
              recordsError={recordsError}
            />
          )}
        </div>

        <div
          role="tabpanel"
          id="prescreen-panel-stats"
          aria-labelledby="prescreen-tab-stats"
          aria-hidden={activeTab !== 'stats'}
          className={`tab-panel ${activeTab === 'stats' ? 'tab-panel-active' : 'tab-panel-inactive'}`}
        >
          {activeTab === 'stats' && <StatsView stats={stats} schema={schema} />}
        </div>

        <div
          role="tabpanel"
          id="prescreen-panel-validation"
          aria-labelledby="prescreen-tab-validation"
          aria-hidden={activeTab !== 'validation'}
          className={`tab-panel ${activeTab === 'validation' ? 'tab-panel-active' : 'tab-panel-inactive'}`}
        >
          {activeTab === 'validation' && (
            <>
              <ValidationView validation={validation} />
              <ProvenancePanel index={index} />
            </>
          )}
        </div>
      </section>
    </>
  )
}
