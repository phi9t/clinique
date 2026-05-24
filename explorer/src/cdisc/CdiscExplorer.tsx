import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import {
  Database,
  FileSpreadsheet,
  Search,
  Info,
  Layers,
  Users,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  FileCode,
} from 'lucide-react'

// TypeScript Types matching converter output
interface Variable {
  oid: string
  name: string
  label: string
  dataType: string
  length: string | null
  sasFormat: string | null
  mandatory: boolean
  keySequence: number | null
  methodOid: string | null
  codelist: {
    name: string
    items: Array<{ value: string; label: string }>
  } | null
}

interface DatasetMetadata {
  oid: string
  name: string
  domain: string | null
  repeating: boolean
  sasName: string
  description: string
  variables: Variable[]
}

interface MetadataPayload {
  datasets: Record<string, DatasetMetadata>
  codelists: Record<string, { name: string; items: Array<{ value: string; label: string }> }>
}

interface DatasetSummaryItem {
  name: string
  domain: string
  description: string
  total_rows: number
  unique_subjects: number | null
  is_sampled: boolean
}

interface DatasetContent {
  name: string
  total_rows: number
  unique_subjects: number | null
  columns: Array<{ name: string; type: string }>
  rows: Array<Record<string, string | number | null>>
  is_sampled: boolean
}

type TabId = 'data' | 'metadata' | 'codelists'

const TAB_ORDER: TabId[] = ['data', 'metadata', 'codelists']

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Unknown error'
}

function getAriaSort(
  colName: string,
  sortColumn: string,
  sortDirection: 'asc' | 'desc',
): 'ascending' | 'descending' | 'none' | undefined {
  if (sortColumn !== colName) return 'none'
  return sortDirection === 'asc' ? 'ascending' : 'descending'
}

export default function CdiscExplorer() {
  const [summary, setSummary] = useState<DatasetSummaryItem[]>([])
  const [metadata, setMetadata] = useState<MetadataPayload | null>(null)
  const [selectedDatasetName, setSelectedDatasetName] = useState<string>('ADSL')
  const [datasetContent, setDatasetContent] = useState<DatasetContent | null>(null)
  const [activeTab, setActiveTab] = useState<TabId>('data')

  // Loading & Error states
  const [loadingSummary, setLoadingSummary] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState('')

  // Interactive Data Table states
  const [searchQuery, setSearchQuery] = useState('')
  const [sortColumn, setSortColumn] = useState<string>('')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [currentPage, setCurrentPage] = useState(1)
  const rowsPerPage = 25

  const shouldReduceMotion = useReducedMotion()
  const mainContentRef = useRef<HTMLElement>(null)

  // 1. Fetch Global Summary and Define Metadata (bypassing browser cache)
  useEffect(() => {
    async function loadGlobalData() {
      try {
        setLoadingSummary(true)
        const [sumRes, metaRes] = await Promise.all([
          fetch(`/data/summary.json?t=${Date.now()}`),
          fetch(`/data/metadata.json?t=${Date.now()}`),
        ])

        if (!sumRes.ok || !metaRes.ok) {
          throw new Error('Failed to load dataset definitions. Run the conversion script.')
        }

        const sumData: DatasetSummaryItem[] = await sumRes.json()
        const metaData: MetadataPayload = await metaRes.json()

        setSummary(sumData)
        setMetadata(metaData)

        if (sumData.length > 0) {
          const first = sumData.find((d) => d.name === 'ADSL') ?? sumData[0]
          setSelectedDatasetName(first.name)
        }
        setStatusMessage(`Loaded ${sumData.length} datasets.`)
      } catch (err: unknown) {
        setError(errorMessage(err))
      } finally {
        setLoadingSummary(false)
      }
    }
    loadGlobalData()
  }, [])

  // 2. Fetch Selected Dataset Observations (bypassing browser cache)
  const loadDatasetContent = useCallback(async (datasetName: string) => {
    if (!datasetName) return
    try {
      setLoadingContent(true)
      setContentError(null)
      setDatasetContent(null)
      setSearchQuery('')
      setSortColumn('')
      setCurrentPage(1)
      setStatusMessage(`Loading records for ${datasetName}...`)

      const res = await fetch(`/data/${datasetName.toLowerCase()}.json?t=${Date.now()}`)
      if (!res.ok) {
        throw new Error(`Failed to load data for dataset ${datasetName} (HTTP ${res.status})`)
      }
      const data: DatasetContent = await res.json()
      setDatasetContent(data)
      setStatusMessage(
        `Loaded ${datasetName} with ${data.total_rows.toLocaleString()} rows.`,
      )
    } catch (err: unknown) {
      console.error(err)
      setContentError(errorMessage(err))
      setStatusMessage(`Failed to load ${datasetName}.`)
    } finally {
      setLoadingContent(false)
    }
  }, [])

  useEffect(() => {
    // Fetch dataset JSON when the sidebar selection changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional fetch-on-selection
    void loadDatasetContent(selectedDatasetName)
  }, [selectedDatasetName, loadDatasetContent])

  const selectedSummary = useMemo(() => {
    return summary.find((s) => s.name === selectedDatasetName) ?? null
  }, [summary, selectedDatasetName])

  const activeDatasetMeta = useMemo(() => {
    if (!metadata || !selectedDatasetName) return null
    return metadata.datasets[selectedDatasetName] ?? null
  }, [metadata, selectedDatasetName])

  const globalMetrics = useMemo(() => {
    if (summary.length === 0) return { datasetsCount: 0, subjectsCount: null as number | null }
    const adsl = summary.find((d) => d.name === 'ADSL')
    return {
      datasetsCount: summary.length,
      subjectsCount: adsl?.unique_subjects ?? null,
    }
  }, [summary])

  const processedRows = useMemo(() => {
    if (!datasetContent) return []
    let rows = [...datasetContent.rows]

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      rows = rows.filter((row) =>
        Object.values(row).some(
          (val) => val !== null && String(val).toLowerCase().includes(q),
        ),
      )
    }

    if (sortColumn) {
      rows.sort((a, b) => {
        const valA = a[sortColumn]
        const valB = b[sortColumn]

        if (valA === null || valA === undefined) return sortDirection === 'asc' ? 1 : -1
        if (valB === null || valB === undefined) return sortDirection === 'asc' ? -1 : 1

        if (typeof valA === 'number' && typeof valB === 'number') {
          return sortDirection === 'asc' ? valA - valB : valB - valA
        }

        return sortDirection === 'asc'
          ? String(valA).localeCompare(String(valB))
          : String(valB).localeCompare(String(valA))
      })
    }

    return rows
  }, [datasetContent, searchQuery, sortColumn, sortDirection])

  const orderedColumns = useMemo(() => {
    if (!datasetContent || !metadata) return []
    const cols = [...datasetContent.columns]
    if (selectedDatasetName === 'ADSL') return cols

    const adslVars = new Set(metadata.datasets['ADSL']?.variables.map((v) => v.name) ?? [])

    cols.sort((a, b) => {
      if (a.name === 'USUBJID') return -1
      if (b.name === 'USUBJID') return 1

      const aInAdsl = adslVars.has(a.name)
      const bInAdsl = adslVars.has(b.name)

      if (!aInAdsl && bInAdsl) return -1
      if (aInAdsl && !bInAdsl) return 1

      const aMeta = activeDatasetMeta?.variables.find((v) => v.name === a.name)
      const bMeta = activeDatasetMeta?.variables.find((v) => v.name === b.name)
      const aIdx = aMeta ? (activeDatasetMeta?.variables.indexOf(aMeta) ?? 0) : 0
      const bIdx = bMeta ? (activeDatasetMeta?.variables.indexOf(bMeta) ?? 0) : 0
      return aIdx - bIdx
    })

    return cols
  }, [datasetContent, metadata, selectedDatasetName, activeDatasetMeta])

  const totalPages = Math.ceil(processedRows.length / rowsPerPage)
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * rowsPerPage
    return processedRows.slice(start, start + rowsPerPage)
  }, [processedRows, currentPage])

  const rowRangeStart = processedRows.length === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1
  const rowRangeEnd =
    processedRows.length === 0
      ? 0
      : Math.min(currentPage * rowsPerPage, processedRows.length)

  const searchResultsSummary =
    processedRows.length === 0
      ? 'No rows match the current search.'
      : totalPages > 1
        ? `Showing ${rowRangeStart} to ${rowRangeEnd} of ${processedRows.length.toLocaleString()} matching rows.`
        : `${processedRows.length.toLocaleString()} rows match the current search.`

  const handleSort = (colName: string) => {
    if (sortColumn === colName) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(colName)
      setSortDirection('asc')
    }
    setCurrentPage(1)
  }

  const activeDatasetCodelists = useMemo(() => {
    if (!activeDatasetMeta) return []
    const lists: Record<string, { name: string; items: Array<{ value: string; label: string }> }> =
      {}
    for (const v of activeDatasetMeta.variables) {
      if (v.codelist) {
        lists[v.name] = {
          name: v.codelist.name,
          items: v.codelist.items,
        }
      }
    }
    return Object.entries(lists)
  }, [activeDatasetMeta])

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, tabId: TabId) => {
    const currentIndex = TAB_ORDER.indexOf(tabId)
    let nextIndex: number | null = null

    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault()
      nextIndex = (currentIndex + 1) % TAB_ORDER.length
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault()
      nextIndex = (currentIndex - 1 + TAB_ORDER.length) % TAB_ORDER.length
    } else if (event.key === 'Home') {
      event.preventDefault()
      nextIndex = 0
    } else if (event.key === 'End') {
      event.preventDefault()
      nextIndex = TAB_ORDER.length - 1
    }

    if (nextIndex === null) return

    const nextTab = TAB_ORDER[nextIndex]
    setActiveTab(nextTab)
    document.getElementById(`tab-${nextTab}`)?.focus()
  }

  const motionTransition = shouldReduceMotion
    ? { duration: 0 }
    : { duration: 0.15 }

  const motionInitial = shouldReduceMotion ? false : { opacity: 0, y: 6 }
  const motionAnimate = { opacity: 1, y: 0 }
  const motionExit = shouldReduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }

  if (loadingSummary) {
    return (
      <div className="loading-container" role="status" aria-live="polite">
        <div className="spinner" aria-hidden="true" />
        <p>Loading FDA submissions pilot data...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="loading-container" role="alert">
        <Info size={48} className="text-danger" aria-hidden="true" />
        <h2>Data Explorer Error</h2>
        <p>{error}</p>
        <p className="text-muted">Ensure you run the dataset converter script first.</p>
      </div>
    )
  }

  const displayRowCount =
    (datasetContent?.total_rows !== undefined
      ? datasetContent?.total_rows
      : selectedSummary?.total_rows) ?? 0

  const displaySubjects =
    datasetContent?.unique_subjects !== undefined
      ? datasetContent?.unique_subjects
      : selectedSummary?.unique_subjects

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

      <div className="cdisc-stats-row global-stats">
        <div className="stat-chip">
          <Layers size={16} className="text-primary" aria-hidden="true" />
          <span>Datasets:</span>
          <span className="stat-value">{globalMetrics.datasetsCount}</span>
        </div>
        <div className="stat-chip">
          <Users size={16} className="text-secondary" aria-hidden="true" />
          <span>Subjects (ADSL):</span>
          <span className="stat-value">
            {globalMetrics.subjectsCount !== null
              ? globalMetrics.subjectsCount
              : '—'}
          </span>
        </div>
      </div>

      <div className="dashboard-grid">
          <aside className="sidebar-panel">
            <div className="sidebar-title" id="dataset-nav-label">
              ADaM Datasets
            </div>
            <nav aria-labelledby="dataset-nav-label">
              <ul className="dataset-list" role="list">
                {summary.map((ds) => {
                  const isActive = selectedDatasetName === ds.name
                  return (
                    <li key={ds.name}>
                      <button
                        type="button"
                        className={`dataset-item ${isActive ? 'active' : ''}`}
                        aria-current={isActive ? 'true' : undefined}
                        onClick={() => setSelectedDatasetName(ds.name)}
                      >
                        <span className="dataset-item-left">
                          <span className="dataset-name-label">{ds.name}</span>
                          <span className="dataset-desc-label">{ds.description}</span>
                        </span>
                        <span className="dataset-item-right">
                          <span className="dataset-domain-badge">{ds.domain || 'ADaM'}</span>
                          <span className="dataset-row-count">
                            {ds.total_rows.toLocaleString()} rows
                          </span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </nav>
          </aside>

          <main
            id="main-content"
            className="main-view-panel"
            ref={mainContentRef}
            tabIndex={-1}
          >
            <section className="card-view" aria-label="Dataset details">
              <div className="dataset-header-section">
                <div className="dataset-title-meta">
                  <h2>{activeDatasetMeta?.name || selectedDatasetName}</h2>
                  <p>
                    {activeDatasetMeta?.description ||
                      'No description available in define.xml.'}
                  </p>
                </div>

                <div className="dataset-attributes">
                  <div className="attr-badge">
                    <Database size={14} className="text-primary" aria-hidden="true" />
                    <span>Total Rows:</span>
                    <strong className="text-primary">{displayRowCount.toLocaleString()}</strong>
                  </div>
                  {displaySubjects !== null && displaySubjects !== undefined && (
                    <div className="attr-badge">
                      <Users size={14} className="text-secondary" aria-hidden="true" />
                      <span>Subjects:</span>
                      <strong className="text-secondary">{displaySubjects}</strong>
                    </div>
                  )}
                  {activeDatasetMeta?.repeating && (
                    <div className="attr-badge text-warning">
                      <span>Repeating</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="tab-row" role="tablist" aria-label="Dataset views">
                <button
                  type="button"
                  role="tab"
                  id="tab-data"
                  aria-selected={activeTab === 'data'}
                  aria-controls="panel-data"
                  tabIndex={activeTab === 'data' ? 0 : -1}
                  onClick={() => setActiveTab('data')}
                  onKeyDown={(e) => handleTabKeyDown(e, 'data')}
                  className={`tab-button ${activeTab === 'data' ? 'active' : ''}`}
                >
                  <FileSpreadsheet size={16} aria-hidden="true" />
                  <span>Data View</span>
                </button>
                <button
                  type="button"
                  role="tab"
                  id="tab-metadata"
                  aria-selected={activeTab === 'metadata'}
                  aria-controls="panel-metadata"
                  tabIndex={activeTab === 'metadata' ? 0 : -1}
                  onClick={() => setActiveTab('metadata')}
                  onKeyDown={(e) => handleTabKeyDown(e, 'metadata')}
                  className={`tab-button ${activeTab === 'metadata' ? 'active' : ''}`}
                >
                  <Info size={16} aria-hidden="true" />
                  <span>Variables (Define-XML)</span>
                </button>
                <button
                  type="button"
                  role="tab"
                  id="tab-codelists"
                  aria-selected={activeTab === 'codelists'}
                  aria-controls="panel-codelists"
                  tabIndex={activeTab === 'codelists' ? 0 : -1}
                  onClick={() => setActiveTab('codelists')}
                  onKeyDown={(e) => handleTabKeyDown(e, 'codelists')}
                  className={`tab-button ${activeTab === 'codelists' ? 'active' : ''}`}
                >
                  <FileCode size={16} aria-hidden="true" />
                  <span>Code Lists ({activeDatasetCodelists.length})</span>
                </button>
              </div>

              <div
                role="tabpanel"
                id="panel-data"
                aria-labelledby="tab-data"
                aria-hidden={activeTab !== 'data'}
                tabIndex={activeTab === 'data' ? 0 : -1}
                className={`tab-panel ${activeTab === 'data' ? 'tab-panel-active' : 'tab-panel-inactive'}`}
              >
                {activeTab === 'data' && (
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={selectedDatasetName}
                      initial={motionInitial}
                      animate={motionAnimate}
                      exit={motionExit}
                      transition={motionTransition}
                    >
                      {loadingContent ? (
                        <div
                          className="loading-container"
                          style={{ minHeight: '300px' }}
                          role="status"
                          aria-live="polite"
                        >
                          <div className="spinner" aria-hidden="true" />
                          <p>Loading records for {selectedDatasetName}...</p>
                        </div>
                      ) : contentError ? (
                        <div
                          className="loading-container text-danger"
                          style={{ minHeight: '300px' }}
                          role="alert"
                        >
                          <Info size={48} className="text-danger" aria-hidden="true" />
                          <h3>Error Loading Data</h3>
                          <p>{contentError}</p>
                          <button
                            type="button"
                            className="pg-btn retry-btn"
                            onClick={() => loadDatasetContent(selectedDatasetName)}
                          >
                            Retry loading {selectedDatasetName}
                          </button>
                        </div>
                      ) : datasetContent ? (
                        <div>
                          <div className="table-actions-row">
                            <div className="search-box-container">
                              <label htmlFor="dataset-search" className="visually-hidden">
                                Search dataset rows
                              </label>
                              <Search
                                size={16}
                                className="search-icon-inside"
                                aria-hidden="true"
                              />
                              <input
                                type="search"
                                id="dataset-search"
                                name="dataset-search"
                                placeholder="Search in all columns..."
                                value={searchQuery}
                                onChange={(e) => {
                                  setSearchQuery(e.target.value)
                                  setCurrentPage(1)
                                }}
                                className="search-input"
                                aria-describedby="search-results-summary"
                              />
                            </div>

                            {selectedDatasetName !== 'ADSL' && (
                              <div
                                className="text-info attr-badge column-order-hint"
                                role="note"
                              >
                                <span>
                                  Showing dataset-specific variables first (demographics at the
                                  end)
                                </span>
                              </div>
                            )}

                            {datasetContent.is_sampled && (
                              <div className="text-warning attr-badge sampled-hint" role="note">
                                <span>
                                  Note: Displaying first 1,000 observations (dataset is large)
                                </span>
                              </div>
                            )}
                          </div>

                          <p
                            id="search-results-summary"
                            className="search-results-summary"
                            aria-live="polite"
                            aria-atomic="true"
                          >
                            {searchResultsSummary}
                          </p>

                          <div className="table-wrapper">
                            <table className="data-table">
                              <caption className="visually-hidden">
                                {selectedDatasetName} observations,{' '}
                                {processedRows.length.toLocaleString()} rows
                              </caption>
                              <thead>
                                <tr>
                                  {orderedColumns.map((col) => {
                                    const variableMeta = activeDatasetMeta?.variables.find(
                                      (v) => v.name === col.name,
                                    )
                                    const isKey =
                                      variableMeta?.keySequence !== null &&
                                      variableMeta?.keySequence !== undefined

                                    return (
                                      <th
                                        key={col.name}
                                        scope="col"
                                        aria-sort={getAriaSort(
                                          col.name,
                                          sortColumn,
                                          sortDirection,
                                        )}
                                        className={isKey ? 'text-warning' : ''}
                                      >
                                        <button
                                          type="button"
                                          className="th-sort-btn"
                                          onClick={() => handleSort(col.name)}
                                        >
                                          <span>{col.name}</span>
                                          <ArrowUpDown
                                            size={12}
                                            className="text-muted"
                                            aria-hidden="true"
                                          />
                                        </button>
                                      </th>
                                    )
                                  })}
                                </tr>
                              </thead>
                              <tbody>
                                {paginatedRows.length === 0 ? (
                                  <tr>
                                    <td
                                      colSpan={orderedColumns.length}
                                      className="text-center text-muted empty-table-cell"
                                    >
                                      No observations found matching the search criteria.
                                    </td>
                                  </tr>
                                ) : (
                                  paginatedRows.map((row, idx) => {
                                    const rowStart = (currentPage - 1) * rowsPerPage
                                    const rowKey = `${String(row.USUBJID ?? 'row')}-${rowStart + idx}`
                                    return (
                                      <tr key={rowKey}>
                                        {orderedColumns.map((col) => {
                                          const cellVal = row[col.name]
                                          const variableMeta =
                                            activeDatasetMeta?.variables.find(
                                              (v) => v.name === col.name,
                                            )
                                          const isKey =
                                            variableMeta?.keySequence !== null &&
                                            variableMeta?.keySequence !== undefined

                                          let cellClass = ''
                                          if (col.name === 'USUBJID') cellClass = 'subject-cell'
                                          else if (isKey) cellClass = 'key-cell'

                                          return (
                                            <td key={col.name} className={cellClass}>
                                              {cellVal === null || cellVal === undefined ? (
                                                <span className="null-cell" aria-label="missing">
                                                  .
                                                </span>
                                              ) : (
                                                String(cellVal)
                                              )}
                                            </td>
                                          )
                                        })}
                                      </tr>
                                    )
                                  })
                                )}
                              </tbody>
                            </table>
                          </div>

                          {totalPages > 1 && (
                            <nav
                              className="pagination-row"
                              aria-label={`${selectedDatasetName} table pagination`}
                            >
                              <span>
                                Showing {rowRangeStart} to {rowRangeEnd} of{' '}
                                {processedRows.length} rows
                              </span>

                              <div className="pagination-buttons">
                                <button
                                  type="button"
                                  onClick={() =>
                                    setCurrentPage((prev) => Math.max(prev - 1, 1))
                                  }
                                  disabled={currentPage === 1}
                                  className="pg-btn"
                                  aria-label="Previous page"
                                >
                                  <ChevronLeft size={16} aria-hidden="true" />
                                </button>
                                <span className="attr-badge">
                                  Page {currentPage} of {totalPages}
                                </span>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setCurrentPage((prev) => Math.min(prev + 1, totalPages))
                                  }
                                  disabled={currentPage === totalPages}
                                  className="pg-btn"
                                  aria-label="Next page"
                                >
                                  <ChevronRight size={16} aria-hidden="true" />
                                </button>
                              </div>
                            </nav>
                          )}
                        </div>
                      ) : null}
                    </motion.div>
                  </AnimatePresence>
                )}
              </div>

              <div
                role="tabpanel"
                id="panel-metadata"
                aria-labelledby="tab-metadata"
                aria-hidden={activeTab !== 'metadata'}
                tabIndex={activeTab === 'metadata' ? 0 : -1}
                className={`tab-panel ${activeTab === 'metadata' ? 'tab-panel-active' : 'tab-panel-inactive'}`}
              >
                {activeTab === 'metadata' && (
                  <motion.div
                    initial={motionInitial}
                    animate={motionAnimate}
                    exit={motionExit}
                    transition={motionTransition}
                    className="meta-grid"
                  >
                    {activeDatasetMeta?.variables.map((variable) => (
                      <div key={variable.name} className="meta-card">
                        <div className="meta-var-name">
                          <span>{variable.name}</span>
                          {variable.keySequence !== null && (
                            <span className="key-badge">Key {variable.keySequence}</span>
                          )}
                          {variable.mandatory && (
                            <span className="mandatory-badge">Req</span>
                          )}
                        </div>

                        <div className="meta-var-desc">{variable.label}</div>

                        <div className="meta-var-details">
                          <span className="meta-type-tag">
                            {variable.dataType.toLowerCase()}
                            {variable.length ? `(${variable.length})` : ''}
                          </span>
                          {variable.sasFormat && (
                            <span className="meta-format-tag">
                              format: {variable.sasFormat}
                            </span>
                          )}
                          {variable.codelist && (
                            <button
                              type="button"
                              className="codelist-tag"
                              onClick={() => setActiveTab('codelists')}
                            >
                              Codelist: {variable.codelist.name}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </motion.div>
                )}
              </div>

              <div
                role="tabpanel"
                id="panel-codelists"
                aria-labelledby="tab-codelists"
                aria-hidden={activeTab !== 'codelists'}
                tabIndex={activeTab === 'codelists' ? 0 : -1}
                className={`tab-panel ${activeTab === 'codelists' ? 'tab-panel-active' : 'tab-panel-inactive'}`}
              >
                {activeTab === 'codelists' && (
                  <motion.div
                    initial={motionInitial}
                    animate={motionAnimate}
                    exit={motionExit}
                    transition={motionTransition}
                  >
                    {activeDatasetCodelists.length === 0 ? (
                      <div
                        className="loading-container empty-codelists"
                        role="status"
                      >
                        <Info size={32} className="text-muted" aria-hidden="true" />
                        <p>
                          No variables in {selectedDatasetName} are linked to CodeLists in
                          define.xml.
                        </p>
                      </div>
                    ) : (
                      <div className="codelist-grid">
                        {activeDatasetCodelists.map(([varName, cl]) => (
                          <div key={varName} className="codelist-card">
                            <div className="codelist-card-header">
                              <h3>{varName}</h3>
                              <span>CodeList: {cl.name}</span>
                            </div>
                            <table className="codelist-table">
                              <caption className="visually-hidden">
                                Code list values for {varName}
                              </caption>
                              <tbody>
                                {cl.items.map((item) => (
                                  <tr key={`${varName}-${item.value}`}>
                                    <td className="codelist-value-col">{item.value}</td>
                                    <td className="codelist-label-col">{item.label}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
              </div>
            </section>
          </main>
        </div>
    </>
  )
}
