import { useEffect, useMemo, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Database, 
  FileSpreadsheet, 
  Search, 
  Info, 
  Layers, 
  Users, 
  ArrowLeft, 
  ChevronLeft, 
  ChevronRight, 
  ArrowUpDown,
  FileCode
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

export default function App() {
  const [summary, setSummary] = useState<DatasetSummaryItem[]>([])
  const [metadata, setMetadata] = useState<MetadataPayload | null>(null)
  const [selectedDatasetName, setSelectedDatasetName] = useState<string>('ADSL')
  const [datasetContent, setDatasetContent] = useState<DatasetContent | null>(null)
  const [activeTab, setActiveTab] = useState<'data' | 'metadata' | 'codelists'>('data')
  
  // Loading & Error states
  const [loadingSummary, setLoadingSummary] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)
  
  // Interactive Data Table states
  const [searchQuery, setSearchQuery] = useState('')
  const [sortColumn, setSortColumn] = useState<string>('')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [currentPage, setCurrentPage] = useState(1)
  const rowsPerPage = 25

  // 1. Fetch Global Summary and Define Metadata (bypassing browser cache)
  useEffect(() => {
    async function loadGlobalData() {
      try {
        setLoadingSummary(true)
        const [sumRes, metaRes] = await Promise.all([
          fetch(`/data/summary.json?t=${Date.now()}`),
          fetch(`/data/metadata.json?t=${Date.now()}`)
        ])
        
        if (!sumRes.ok || !metaRes.ok) {
          throw new Error('Failed to load dataset definitions. Run the conversion script.')
        }
        
        const sumData = await sumRes.json()
        const metaData = await metaRes.json()
        
        setSummary(sumData)
        setMetadata(metaData)
        
        // Find default or first dataset
        if (sumData.length > 0) {
          const first = sumData.find((d: any) => d.name === 'ADSL') || sumData[0]
          setSelectedDatasetName(first.name)
        }
      } catch (err: any) {
        setError(err.message)
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
      setDatasetContent(null) // Clear old content to prevent displaying stale data
      setSearchQuery('')
      setSortColumn('')
      setCurrentPage(1)
      
      const res = await fetch(`/data/${datasetName.toLowerCase()}.json?t=${Date.now()}`)
      if (!res.ok) {
        throw new Error(`Failed to load data for dataset ${datasetName} (HTTP ${res.status})`)
      }
      const data = await res.json()
      setDatasetContent(data)
    } catch (err: any) {
      console.error(err)
      setContentError(err.message || 'Unknown error loading dataset')
    } finally {
      setLoadingContent(false)
    }
  }, [])

  useEffect(() => {
    loadDatasetContent(selectedDatasetName)
  }, [selectedDatasetName, loadDatasetContent])

  const selectedSummary = useMemo(() => {
    return summary.find(s => s.name === selectedDatasetName) || null
  }, [summary, selectedDatasetName])

  // Get active dataset details from metadata
  const activeDatasetMeta = useMemo(() => {
    if (!metadata || !selectedDatasetName) return null
    return metadata.datasets[selectedDatasetName] || null
  }, [metadata, selectedDatasetName])

  // Calculate global summary metrics
  const globalMetrics = useMemo(() => {
    if (summary.length === 0) return { datasetsCount: 0, subjectsCount: 0 }
    const adsl = summary.find(d => d.name === 'ADSL')
    return {
      datasetsCount: summary.length,
      subjectsCount: adsl ? adsl.unique_subjects || 254 : 254
    }
  }, [summary])

  // Sort & Search Operations on Data Rows
  const processedRows = useMemo(() => {
    if (!datasetContent) return []
    let rows = [...datasetContent.rows]
    
    // Apply Global Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      rows = rows.filter(row => 
        Object.values(row).some(val => 
          val !== null && String(val).toLowerCase().includes(q)
        )
      )
    }
    
    // Apply Sorting
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

  // Re-order columns so dataset-specific columns appear first (not demographic copies from ADSL)
  const orderedColumns = useMemo(() => {
    if (!datasetContent || !metadata) return []
    const cols = [...datasetContent.columns]
    if (selectedDatasetName === 'ADSL') return cols

    const adslVars = new Set(
      metadata.datasets['ADSL']?.variables.map(v => v.name) || []
    )

    cols.sort((a, b) => {
      // USUBJID always first
      if (a.name === 'USUBJID') return -1
      if (b.name === 'USUBJID') return 1

      const aInAdsl = adslVars.has(a.name)
      const bInAdsl = adslVars.has(b.name)

      // Variables unique to this dataset go first
      if (!aInAdsl && bInAdsl) return -1
      if (aInAdsl && !bInAdsl) return 1

      // Keep original define order if both in same category
      const aMeta = activeDatasetMeta?.variables.find(v => v.name === a.name)
      const bMeta = activeDatasetMeta?.variables.find(v => v.name === b.name)
      const aIdx = activeDatasetMeta?.variables.indexOf(aMeta!) ?? 0
      const bIdx = activeDatasetMeta?.variables.indexOf(bMeta!) ?? 0
      return aIdx - bIdx
    })

    return cols
  }, [datasetContent, metadata, selectedDatasetName, activeDatasetMeta])

  // Pagination bounds
  const totalPages = Math.ceil(processedRows.length / rowsPerPage)
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * rowsPerPage
    return processedRows.slice(start, start + rowsPerPage)
  }, [processedRows, currentPage])

  const handleSort = (colName: string) => {
    if (sortColumn === colName) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(colName)
      setSortDirection('asc')
    }
    setCurrentPage(1)
  }

  // Generate codelists specifically active in this dataset
  const activeDatasetCodelists = useMemo(() => {
    if (!activeDatasetMeta) return []
    const lists: Record<string, { name: string; items: Array<{ value: string; label: string }> }> = {}
    for (const v of activeDatasetMeta.variables) {
      if (v.codelist) {
        lists[v.name] = {
          name: v.codelist.name,
          items: v.codelist.items
        }
      }
    }
    return Object.entries(lists)
  }, [activeDatasetMeta])

  if (loadingSummary) {
    return (
      <div className="loading-container">
        <div className="spinner" />
        <p>Loading FDA submissions pilot data...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="loading-container">
        <Info size={48} className="text-danger" />
        <h2>Data Explorer Error</h2>
        <p>{error}</p>
        <p className="text-muted">Ensure you run the dataset converter script first.</p>
      </div>
    )
  }

  return (
    <div className="relative min-h-screen">
      <div className="observatory-bg" />
      
      <div className="explorer-container">
        {/* Header Section */}
        <header className="explorer-header">
          <div className="header-title-section">
            <a href="/" className="back-home-link">
              <ArrowLeft size={16} />
              <span>Back to Clinique Suite</span>
            </a>
            <h1>Regulatory Submissions Dataset Explorer</h1>
            <p>FDA-pilot CDISC ADaM datasets & metadata validation dashboard</p>
          </div>
          
          <div className="global-stats">
            <div className="stat-chip">
              <Layers size={16} className="text-primary" />
              <span>Datasets:</span>
              <span className="stat-value">{globalMetrics.datasetsCount}</span>
            </div>
            <div className="stat-chip">
              <Users size={16} className="text-secondary" />
              <span>Subjects (ADSL):</span>
              <span className="stat-value">{globalMetrics.subjectsCount}</span>
            </div>
          </div>
        </header>

        {/* Dashboard Panels Layout */}
        <div className="dashboard-grid">
          {/* Sidebar List of Datasets */}
          <aside className="sidebar-panel">
            <div className="sidebar-title">ADaM Datasets</div>
            <div className="dataset-list">
              {summary.map((ds) => (
                <div
                  key={ds.name}
                  className={`dataset-item ${selectedDatasetName === ds.name ? 'active' : ''}`}
                  onClick={() => setSelectedDatasetName(ds.name)}
                >
                  <div className="dataset-item-left">
                    <span className="dataset-name-label">{ds.name}</span>
                    <span className="dataset-desc-label">{ds.description}</span>
                  </div>
                  <div className="dataset-item-right">
                    <span className="dataset-domain-badge">{ds.domain || 'ADaM'}</span>
                    <span className="dataset-row-count">{ds.total_rows.toLocaleString()} rows</span>
                  </div>
                </div>
              ))}
            </div>
          </aside>

          {/* Main Visualizer Area */}
          <main className="main-view-panel">
            {/* Active Dataset Overview Card */}
            <section className="card-view">
              <div className="dataset-header-section">
                <div className="dataset-title-meta">
                  <h2>{activeDatasetMeta?.name || selectedDatasetName}</h2>
                  <p>{activeDatasetMeta?.description || 'No description available in define.xml.'}</p>
                </div>
                
                <div className="dataset-attributes">
                  <div className="attr-badge">
                    <Database size={14} className="text-primary" />
                    <span>Total Rows:</span>
                    <strong className="text-primary">
                      {((datasetContent?.total_rows !== undefined ? datasetContent?.total_rows : selectedSummary?.total_rows) ?? 0).toLocaleString()}
                    </strong>
                  </div>
                  {((datasetContent?.unique_subjects !== undefined ? datasetContent?.unique_subjects : selectedSummary?.unique_subjects) ?? null) !== null && (
                    <div className="attr-badge">
                      <Users size={14} className="text-secondary" />
                      <span>Subjects:</span>
                      <strong className="text-secondary">
                        {datasetContent?.unique_subjects !== undefined ? datasetContent?.unique_subjects : selectedSummary?.unique_subjects}
                      </strong>
                    </div>
                  )}
                  {activeDatasetMeta?.repeating && (
                    <div className="attr-badge text-warning">
                      <span>Repeating</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Navigation Tabs */}
              <div className="tab-row">
                <button
                  onClick={() => setActiveTab('data')}
                  className={`tab-button ${activeTab === 'data' ? 'active' : ''}`}
                >
                  <FileSpreadsheet size={16} />
                  <span>Data View</span>
                </button>
                <button
                  onClick={() => setActiveTab('metadata')}
                  className={`tab-button ${activeTab === 'metadata' ? 'active' : ''}`}
                >
                  <Info size={16} />
                  <span>Variables (Define-XML)</span>
                </button>
                <button
                  onClick={() => setActiveTab('codelists')}
                  className={`tab-button ${activeTab === 'codelists' ? 'active' : ''}`}
                >
                  <FileCode size={16} />
                  <span>Code Lists ({activeDatasetCodelists.length})</span>
                </button>
              </div>

              {/* Tab Contents */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.15 }}
                >
                  {/* DATA VIEW TAB */}
                  {activeTab === 'data' && (
                    <div key={selectedDatasetName}>
                      {loadingContent ? (
                        <div className="loading-container" style={{ minHeight: '300px' }}>
                          <div className="spinner" />
                          <p>Loading records for {selectedDatasetName}...</p>
                        </div>
                      ) : contentError ? (
                        <div className="loading-container text-danger" style={{ minHeight: '300px' }}>
                          <Info size={48} className="text-danger" />
                          <h3>Error Loading Data</h3>
                          <p>{contentError}</p>
                          <button 
                            className="pg-btn" 
                            style={{ marginTop: '16px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                            onClick={() => loadDatasetContent(selectedDatasetName)}
                          >
                            Retry
                          </button>
                        </div>
                      ) : datasetContent ? (
                        <div>
                          {/* Search / Filter Actions */}
                          <div className="table-actions-row">
                            <div className="search-box-container">
                              <Search size={16} className="search-icon-inside" />
                              <input
                                type="text"
                                placeholder={`Search in all columns...`}
                                value={searchQuery}
                                onChange={(e) => {
                                  setSearchQuery(e.target.value)
                                  setCurrentPage(1)
                                }}
                                className="search-input"
                              />
                            </div>
                            
                            {selectedDatasetName !== 'ADSL' && (
                              <div className="text-info attr-badge" style={{ borderColor: 'rgba(6, 182, 212, 0.3)' }}>
                                <span>Showing dataset-specific variables first (demographics at the end)</span>
                              </div>
                            )}

                            {datasetContent.is_sampled && (
                              <div className="text-warning attr-badge" style={{ borderColor: 'rgba(245, 158, 11, 0.3)' }}>
                                <span>Note: Displaying first 1,000 observations (dataset is large)</span>
                              </div>
                            )}
                          </div>

                          {/* Data Table */}
                          <div className="table-wrapper">
                            <table className="data-table">
                              <thead>
                                <tr>
                                  {orderedColumns.map((col) => {
                                    // Identify if variable is key sequence in metadata
                                    const variableMeta = activeDatasetMeta?.variables.find(v => v.name === col.name)
                                    const isKey = variableMeta?.keySequence !== null && variableMeta?.keySequence !== undefined
                                    
                                    return (
                                      <th 
                                        key={col.name} 
                                        onClick={() => handleSort(col.name)}
                                        className={isKey ? 'text-warning' : ''}
                                      >
                                        <div className="flex items-center gap-1">
                                          <span>{col.name}</span>
                                          <ArrowUpDown size={12} className="text-muted" />
                                        </div>
                                      </th>
                                    )
                                  })}
                                </tr>
                              </thead>
                              <tbody>
                                {paginatedRows.length === 0 ? (
                                  <tr>
                                    <td colSpan={orderedColumns.length} className="text-center text-muted" style={{ padding: '40px' }}>
                                      No observations found matching the search criteria.
                                    </td>
                                  </tr>
                                ) : (
                                  paginatedRows.map((row, idx) => (
                                    <tr key={idx}>
                                      {orderedColumns.map((col) => {
                                        const cellVal = row[col.name]
                                        const variableMeta = activeDatasetMeta?.variables.find(v => v.name === col.name)
                                        const isKey = variableMeta?.keySequence !== null && variableMeta?.keySequence !== undefined
                                        
                                        let cellClass = ''
                                        if (col.name === 'USUBJID') cellClass = 'subject-cell'
                                        else if (isKey) cellClass = 'key-cell'
                                        
                                        return (
                                          <td key={col.name} className={cellClass}>
                                            {cellVal === null || cellVal === undefined ? (
                                              <span className="text-muted" style={{ fontSize: '11px', fontFamily: 'monospace' }}>.</span>
                                            ) : (
                                              String(cellVal)
                                            )}
                                          </td>
                                        )
                                      })}
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>

                          {/* Pagination controls */}
                          {totalPages > 1 && (
                            <div className="pagination-row">
                              <span>
                                Showing {((currentPage - 1) * rowsPerPage) + 1} to {Math.min(currentPage * rowsPerPage, processedRows.length)} of {processedRows.length} rows
                              </span>
                              
                              <div className="pagination-buttons">
                                <button
                                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                                  disabled={currentPage === 1}
                                  className="pg-btn"
                                >
                                  <ChevronLeft size={16} />
                                </button>
                                <span className="attr-badge">Page {currentPage} of {totalPages}</span>
                                <button
                                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                                  disabled={currentPage === totalPages}
                                  className="pg-btn"
                                >
                                  <ChevronRight size={16} />
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : null}
                    </div>
                  )}

                  {/* VARIABLES METADATA TAB */}
                  {activeTab === 'metadata' && (
                    <div className="meta-grid">
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
                          
                          <div className="meta-var-desc">
                            {variable.label}
                          </div>
                          
                          <div className="meta-var-details">
                            <span className="meta-type-tag">
                              {variable.dataType.toLowerCase()}
                              {variable.length ? `(${variable.length})` : ''}
                            </span>
                            {variable.sasFormat && (
                              <span className="text-muted" style={{ fontSize: '11px', fontFamily: 'monospace' }}>
                                format: {variable.sasFormat}
                              </span>
                            )}
                            {variable.codelist && (
                              <span 
                                className="codelist-tag"
                                onClick={() => setActiveTab('codelists')}
                              >
                                Codelist: {variable.codelist.name}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* CODELISTS TAB */}
                  {activeTab === 'codelists' && (
                    <div>
                      {activeDatasetCodelists.length === 0 ? (
                        <div className="loading-container" style={{ minHeight: '200px' }}>
                          <Info size={32} className="text-muted" />
                          <p>No variables in {selectedDatasetName} are linked to CodeLists in define.xml.</p>
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
                                <tbody>
                                  {cl.items.map((item, idx) => (
                                    <tr key={idx}>
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
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>
            </section>
          </main>
        </div>
      </div>
    </div>
  )
}
