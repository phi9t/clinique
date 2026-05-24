import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import TrialCard from './TrialCard'
import PatientTimeline from './PatientTimeline'
import type {
  DatasetKey,
  IndexEntry,
  PatientCorpusRecord,
  SchemaPayload,
  TrialRecord,
} from './types'

interface DatasetViewProps {
  index: IndexEntry[]
  schema: SchemaPayload
  trials: TrialRecord[] | null
  synthea: PatientCorpusRecord[] | null
  pmc: PatientCorpusRecord[] | null
  mimic: PatientCorpusRecord[] | null
  loadingRecords: boolean
  recordsError: string | null
}

function recordLabel(record: TrialRecord | PatientCorpusRecord): string {
  if ('trial_id' in record) {
    return `${record.trial_id} — ${record.title.slice(0, 60)}`
  }
  return `${record.patient_id} (${record.documents.length} docs)`
}

export default function DatasetView({
  index,
  schema,
  trials,
  synthea,
  pmc,
  mimic,
  loadingRecords,
  recordsError,
}: DatasetViewProps) {
  const [selectedKey, setSelectedKey] = useState<DatasetKey>('trials')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const activeRecords = useMemo(() => {
    switch (selectedKey) {
      case 'trials':
        return trials ?? []
      case 'patients_synthea':
        return synthea ?? []
      case 'patients_pmc':
        return pmc ?? []
      case 'patients_mimic':
        return mimic ?? []
      default:
        return []
    }
  }, [selectedKey, trials, synthea, pmc, mimic])

  const filteredRecords = useMemo(() => {
    if (activeRecords.length === 0) return []
    const q = searchQuery.trim().toLowerCase()
    if (!q) return activeRecords
    return activeRecords.filter((record) => {
      const label = recordLabel(record).toLowerCase()
      return label.includes(q)
    })
  }, [activeRecords, searchQuery])

  const selectedRecord = useMemo(() => {
    if (!selectedId || activeRecords.length === 0) return null
    if (selectedKey === 'trials') {
      return (activeRecords as TrialRecord[]).find(
        (r) => r.trial_id === selectedId,
      )
    }
    return (activeRecords as PatientCorpusRecord[]).find(
      (r) => r.patient_id === selectedId,
    )
  }, [activeRecords, selectedId, selectedKey])

  const handleSelectDataset = (key: DatasetKey) => {
    setSelectedKey(key)
    setSelectedId(null)
    setSearchQuery('')
  }

  const handleSelectRecord = (record: TrialRecord | PatientCorpusRecord) => {
    const id = 'trial_id' in record ? record.trial_id : record.patient_id
    setSelectedId(id)
  }

  return (
    <div className="prescreen-datasets dashboard-grid">
      <aside className="sidebar-panel">
        <div className="sidebar-title" id="prescreen-dataset-nav">
          L0 Datasets
        </div>
        <nav aria-labelledby="prescreen-dataset-nav">
          <ul className="dataset-list" role="list">
            {index.map((entry) => (
              <li key={entry.key}>
                <button
                  type="button"
                  className={`dataset-item ${selectedKey === entry.key ? 'active' : ''}`}
                  aria-current={selectedKey === entry.key ? 'true' : undefined}
                  onClick={() => handleSelectDataset(entry.key as DatasetKey)}
                >
                  <span className="dataset-item-left">
                    <span className="dataset-name-label">{entry.label}</span>
                    <span className="dataset-desc-label">{entry.source}</span>
                  </span>
                  <span className="dataset-item-right">
                    <span className="dataset-domain-badge">{entry.record_type}</span>
                    <span className="dataset-row-count">
                      {entry.count.toLocaleString()} records
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <main className="main-view-panel">
        <section className="card-view" aria-label="Record drill-down">
          {loadingRecords ? (
            <div className="loading-container" role="status">
              <div className="spinner" aria-hidden="true" />
              <p>Loading records...</p>
            </div>
          ) : recordsError ? (
            <div className="loading-container text-danger" role="alert">
              <p>{recordsError}</p>
            </div>
          ) : (
            <div className="dataset-split">
              <div className="record-list-panel">
                <div className="search-box-container">
                  <label htmlFor="prescreen-record-search" className="visually-hidden">
                    Search records
                  </label>
                  <Search
                    size={16}
                    className="search-icon-inside"
                    aria-hidden="true"
                  />
                  <input
                    type="search"
                    id="prescreen-record-search"
                    placeholder="Search records..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="search-input"
                  />
                </div>
                <ul className="record-picker-list" role="list">
                  {filteredRecords.map((record) => {
                    const id =
                      'trial_id' in record ? record.trial_id : record.patient_id
                    const isActive = selectedId === id
                    return (
                      <li key={id}>
                        <button
                          type="button"
                          className={`record-picker-item ${isActive ? 'active' : ''}`}
                          aria-current={isActive ? 'true' : undefined}
                          onClick={() => handleSelectRecord(record)}
                        >
                          {recordLabel(record)}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>

              <div className="record-detail-panel">
                {!selectedRecord ? (
                  <div className="loading-container empty-detail" role="status">
                    <p>Select a record to inspect eligibility text or document timeline.</p>
                  </div>
                ) : selectedKey === 'trials' ? (
                  <TrialCard
                    trial={selectedRecord as TrialRecord}
                    schema={schema}
                  />
                ) : (
                  <PatientTimeline
                    patient={selectedRecord as PatientCorpusRecord}
                    schema={schema}
                  />
                )}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
