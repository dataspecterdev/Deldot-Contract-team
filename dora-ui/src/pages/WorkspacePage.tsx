import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getProject, deleteProject, uploadFiles, listFiles, deleteFile,
  triggerAnalysis, cancelAnalysis, getStatus, listOutputs, fetchOutputContent,
  getOutputDownloadUrl, getFileViewUrl, listPackages, organizeFiles, listModels,
  type Project, type UploadedFile, type OutputFile, type PackagesInfo, type StatusResponse, type ModelInfo,
} from '../api/client'
import DocumentViewer from '../components/DocumentViewer'
import FileTree from '../components/FileTree'
import PackageOrganizer from '../components/PackageOrganizer'
import { useResizable } from '../hooks/useResizable'

export default function WorkspacePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [outputs, setOutputs] = useState<OutputFile[]>([])
  const [viewerContent, setViewerContent] = useState<string | null>(null)
  const [viewerFileName, setViewerFileName] = useState('')
  const [pdfViewUrl, setPdfViewUrl] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [packagesInfo, setPackagesInfo] = useState<PackagesInfo | null>(null)
  const [showOrganizer, setShowOrganizer] = useState(false)
  const [tokenInfo, setTokenInfo] = useState<StatusResponse['tokens']>(null)
  const [analysisStats, setAnalysisStats] = useState<{ flags: number; findings: number; packages: number } | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Resizable panels: horizontal (left/right split) and vertical (file list/viewer split)
  const hResize = useResizable({ direction: 'horizontal', initialSize: 33, minSize: 20, maxSize: 60 })
  const vResize = useResizable({ direction: 'vertical', initialSize: 35, minSize: 15, maxSize: 75 })

  const refresh = useCallback(async () => {
    if (!projectId) return
    try {
      const [proj, fileList, outputList, pkgInfo] = await Promise.all([
        getProject(projectId),
        listFiles(projectId),
        listOutputs(projectId),
        listPackages(projectId),
      ])
      setProject(proj)
      setFiles(fileList)
      setOutputs(outputList)
      setPackagesInfo(pkgInfo)
      // Auto-show organizer if there are loose files that need grouping
      if (pkgInfo.needs_grouping && !showOrganizer) {
        setShowOrganizer(true)
      }
      // Load token info if analysis is already complete
      if (proj.status === 'complete') {
        const status = await getStatus(projectId)
        if (status.tokens) {
          setTokenInfo(status.tokens)
          setAnalysisStats({
            flags: status.total_flags || 0,
            findings: status.total_findings || 0,
            packages: status.packages_analyzed || 1,
          })
        }
      }
    } catch {
      setError('Failed to load project')
    }
  }, [projectId])

  useEffect(() => { refresh() }, [refresh])

  // Load available models
  useEffect(() => {
    listModels().then((res) => {
      setModels(res.models)
      setSelectedModel(res.default)
    }).catch(() => {})
  }, [])

  // Incognito cleanup on tab close
  useEffect(() => {
    if (!project || project.mode !== 'incognito') return
    const cleanup = () => {
      if (projectId) {
        // sendBeacon sends a POST to the cleanup endpoint (sendBeacon can't do DELETE)
        navigator.sendBeacon(`/api/projects/${projectId}/cleanup`)
      }
    }
    window.addEventListener('beforeunload', cleanup)
    return () => window.removeEventListener('beforeunload', cleanup)
  }, [project, projectId])

  // Poll for analysis status
  useEffect(() => {
    if (project?.status === 'analyzing') {
      pollRef.current = setInterval(async () => {
        if (!projectId) return
        const status = await getStatus(projectId)
        if (status.status !== 'analyzing') {
          if (pollRef.current) clearInterval(pollRef.current)
          // Capture token usage when complete
          if (status.tokens) {
            setTokenInfo(status.tokens)
            setAnalysisStats({
              flags: status.total_flags || 0,
              findings: status.total_findings || 0,
              packages: status.packages_analyzed || 1,
            })
          }
          refresh()
        }
      }, 3000)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [project?.status, projectId, refresh])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length || !projectId) return
    setUploading(true)
    setError('')
    try {
      // For folder uploads, filter to only PDF/JSON; for file input, send all
      const allFiles = Array.from(e.target.files)
      const validFiles = allFiles.filter((f) => {
        const lower = f.name.toLowerCase()
        return lower.endsWith('.pdf') || lower.endsWith('.json')
      })
      if (validFiles.length === 0) {
        setError('No PDF or JSON files found.')
        return
      }
      await uploadFiles(projectId, validFiles)
      await refresh()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    if (!projectId) return

    // Recursively collect files from dropped folders and loose files,
    // preserving the relative path so same-name files don't collide.
    const allFiles: File[] = []
    const items = Array.from(e.dataTransfer.items)

    const readEntry = (entry: FileSystemEntry, parentPath: string): Promise<File[]> => {
      return new Promise((resolve) => {
        if (entry.isFile) {
          (entry as FileSystemFileEntry).file((f) => {
            const lower = f.name.toLowerCase()
            if (lower.endsWith('.pdf') || lower.endsWith('.json')) {
              // Attach relative path as custom property for upload
              const relativePath = parentPath ? `${parentPath}/${f.name}` : f.name;
              (f as any)._relativePath = relativePath
              resolve([f])
            } else {
              resolve([])
            }
          }, () => resolve([]))
        } else if (entry.isDirectory) {
          const dirPath = parentPath ? `${parentPath}/${entry.name}` : entry.name
          const reader = (entry as FileSystemDirectoryEntry).createReader()
          const results: File[] = []
          const readBatch = () => {
            reader.readEntries(async (entries) => {
              if (entries.length === 0) {
                resolve(results)
              } else {
                for (const e of entries) {
                  const files = await readEntry(e, dirPath)
                  results.push(...files)
                }
                readBatch() // readEntries can paginate
              }
            }, () => resolve(results))
          }
          readBatch()
        } else {
          resolve([])
        }
      })
    }

    for (const item of items) {
      const entry = item.webkitGetAsEntry?.()
      if (entry) {
        const files = await readEntry(entry, '')
        allFiles.push(...files)
      } else if (item.kind === 'file') {
        const file = item.getAsFile()
        if (file) {
          const lower = file.name.toLowerCase()
          if (lower.endsWith('.pdf') || lower.endsWith('.json')) {
            allFiles.push(file)
          }
        }
      }
    }

    if (!allFiles.length) {
      setError('No PDF or JSON files found in the dropped items.')
      return
    }
    setUploading(true)
    setError('')
    try {
      await uploadFiles(projectId, allFiles)
      await refresh()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleAnalyze = async () => {
    if (!projectId) return
    setError('')
    setTokenInfo(null)
    setAnalysisStats(null)
    try {
      await triggerAnalysis(projectId, selectedModel || undefined)
      setProject((prev) => prev ? { ...prev, status: 'analyzing' } : prev)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleCancel = async () => {
    if (!projectId) return
    try {
      await cancelAnalysis(projectId)
      setProject((prev) => prev ? { ...prev, status: 'ready' } : prev)
      if (pollRef.current) clearInterval(pollRef.current)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleDeleteFile = async (fileName: string) => {
    if (!projectId) return
    await deleteFile(projectId, fileName)
    refresh()
  }

  const handleViewOutput = async (fileName: string) => {
    if (!projectId) return
    setPdfViewUrl(null)
    try {
      const content = await fetchOutputContent(projectId, fileName)
      setViewerContent(content)
      setViewerFileName(fileName)
    } catch {
      setError('Failed to load file')
    }
  }

  const handleDeleteProject = async () => {
    if (!projectId) return
    if (!confirm('Delete this project and all files?')) return
    await deleteProject(projectId)
    navigate('/')
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
        Loading workspace...
      </div>
    )
  }

  const isAnalyzing = project.status === 'analyzing'
  const isComplete = project.status === 'complete'

  return (
    <div className="h-[calc(100vh-108px)] flex flex-col">
      {/* Workspace toolbar */}
      <div className="px-6 py-3 border-b border-slate-200 bg-white flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/')} className="text-slate-400 hover:text-slate-600 transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
          </button>
          <h2 className="font-display font-semibold text-base text-dora-navy">{project.name}</h2>
          {project.mode === 'incognito' && (
            <span className="text-[10px] uppercase tracking-wider bg-slate-700 text-white px-2 py-0.5 rounded-full">
              incognito
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {error && <span className="text-xs text-dora-danger">{error}</span>}
          {/* Model selector */}
          {models.length > 0 && (
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={isAnalyzing}
              className="px-2 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-dora-sky focus:border-transparent disabled:opacity-50"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          )}
          <button
            onClick={handleAnalyze}
            disabled={files.length === 0 || isAnalyzing}
            className="btn-primary"
          >
            {isAnalyzing ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Analyzing...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                </svg>
                Run Analysis
              </>
            )}
          </button>
          {isAnalyzing && (
            <button onClick={handleCancel} className="btn-secondary text-xs px-3 py-1.5 border-amber-300 text-amber-700 hover:bg-amber-50">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 7.5A2.25 2.25 0 017.5 5.25h9a2.25 2.25 0 012.25 2.25v9a2.25 2.25 0 01-2.25 2.25h-9a2.25 2.25 0 01-2.25-2.25v-9z" />
              </svg>
              Cancel
            </button>
          )}
          {tokenInfo && (
            <span className="text-[11px] text-slate-500 flex items-center gap-1" title={`Input: ${tokenInfo.input.toLocaleString()} | Output: ${tokenInfo.output.toLocaleString()}`}>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
              {tokenInfo.total.toLocaleString()} tokens
            </span>
          )}
          <button onClick={handleDeleteProject} className="btn-danger text-xs px-3 py-1.5">
            Delete
          </button>
        </div>
      </div>

      {/* Split panels */}
      <div className="flex-1 flex overflow-hidden" ref={hResize.containerRef}>
        {/* LEFT: Upload panel */}
        <div className="border-r border-slate-200 flex flex-col bg-white overflow-hidden" style={{ width: `${hResize.size}%` }}>
          <div className="panel-header flex items-center justify-between">
            <span>Contract Documents</span>
            <span className="text-xs font-normal text-slate-400">{files.length} file{files.length !== 1 ? 's' : ''}</span>
          </div>

          {/* Drop zone */}
          <div
            className="m-3 border-2 border-dashed border-slate-200 rounded-lg p-4 text-center hover:border-dora-sky/60 transition-colors"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            <input
              type="file"
              multiple
              onChange={handleUpload}
              className="hidden"
              id="file-upload"
              disabled={uploading}
            />
            <input
              type="file"
              multiple
              onChange={handleUpload}
              className="hidden"
              id="folder-upload"
              disabled={uploading}
              {...{ webkitdirectory: '', directory: '' } as any}
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer flex flex-col items-center gap-2"
            >
              <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
              </svg>
              <span className="text-xs text-slate-500">
                {uploading ? 'Uploading...' : 'Drop files or folders here, or click to upload files'}
              </span>
            </label>
            <div className="mt-2 flex items-center justify-center gap-3">
              <label
                htmlFor="folder-upload"
                className="cursor-pointer inline-flex items-center gap-1 text-[11px] text-dora-blue hover:text-dora-navy transition-colors font-medium"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
                Upload folder
              </label>
            </div>
            <span className="block mt-1 text-[10px] text-slate-400">
              Accepts .pdf and .json files (nested folders supported)
            </span>
          </div>

          {/* Package organizer (shown when loose files need grouping) */}
          {showOrganizer && packagesInfo && packagesInfo.loose_files.length > 0 && (
            <div className="px-3 pt-2">
              <PackageOrganizer
                looseFiles={packagesInfo.loose_files}
                existingPackages={packagesInfo.packages}
                onOrganize={async (groups) => {
                  if (!projectId) return
                  await organizeFiles(projectId, groups)
                  setShowOrganizer(false)
                  await refresh()
                }}
                onSkip={() => setShowOrganizer(false)}
              />
            </div>
          )}

          {/* File tree */}
          <div className="flex-1 overflow-y-auto px-2 pb-3">
            <FileTree
              files={files}
              onDelete={handleDeleteFile}
              onFileClick={(filePath) => {
                if (!projectId) return
                if (filePath.toLowerCase().endsWith('.pdf')) {
                  setPdfViewUrl(getFileViewUrl(projectId, filePath))
                  setViewerContent(null)
                  setViewerFileName(filePath.split('/').pop() || filePath)
                }
              }}
            />
          </div>
        </div>

        {/* Horizontal resize handle */}
        <div
          className="w-1.5 bg-slate-100 hover:bg-dora-sky/30 active:bg-dora-sky/50 cursor-col-resize flex items-center justify-center shrink-0 transition-colors"
          onMouseDown={hResize.onMouseDown}
        >
          <div className="w-0.5 h-8 bg-slate-300 rounded-full" />
        </div>

        {/* RIGHT: Output panel */}
        <div className="flex-1 flex flex-col bg-dora-sand overflow-hidden">
          <div className="panel-header bg-white flex items-center justify-between shrink-0">
            <span>Analysis Output</span>
            {isComplete && outputs.length > 0 && (
              <div className="flex items-center gap-2">
                <a
                  href={`/api/projects/${projectId}/outputs/download-all`}
                  download
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-dora-blue bg-dora-sky/10 hover:bg-dora-sky/20 transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  Download All
                </a>
                <span className="text-[10px] font-normal text-green-600 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                  </svg>
                  Complete
                </span>
              </div>
            )}
          </div>

          {isAnalyzing ? (
            /* Analyzing state */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <svg className="w-10 h-10 mx-auto text-dora-sky animate-spin mb-3" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <p className="text-sm text-slate-500 font-medium">Running contract analysis...</p>
                <p className="text-xs text-slate-400 mt-1">This may take a few minutes per requirement.</p>
              </div>
            </div>
          ) : outputs.length > 0 ? (
            /* Output files + viewer stacked */
            <div className="flex-1 flex flex-col overflow-hidden" ref={vResize.containerRef}>
              {/* Output file list — resizable top section */}
              <div className="overflow-y-auto p-3 bg-dora-sand" style={{ height: `${vResize.size}%` }}>
                <div className="grid gap-2">
                  {sortOutputFiles(outputs).map((output) => (
                    <div
                      key={output.file_name}
                      className={`card px-4 py-3 flex items-center justify-between transition-colors ${
                        viewerFileName === output.file_name ? 'ring-2 ring-dora-sky/40 bg-blue-50/30' : ''
                      }`}
                    >
                      <div className="flex items-center gap-3 cursor-pointer" onClick={() => handleViewOutput(output.file_name)}>
                        <FileIcon type={output.file_type} />
                        <div>
                          <p className="text-sm font-medium text-slate-700">{output.file_name}</p>
                          <p className="text-xs text-slate-400">{formatBytes(output.size_bytes)}</p>
                        </div>
                      </div>
                      <a
                        href={getOutputDownloadUrl(projectId!, output.file_name)}
                        download={output.file_name}
                        className="btn-secondary text-xs px-3 py-1.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                        </svg>
                        Download
                      </a>
                    </div>
                  ))}
                </div>
              </div>

              {/* Vertical resize handle */}
              <div
                className="h-1.5 bg-slate-100 hover:bg-dora-sky/30 active:bg-dora-sky/50 cursor-row-resize flex items-center justify-center shrink-0 transition-colors"
                onMouseDown={vResize.onMouseDown}
              >
                <div className="h-0.5 w-8 bg-slate-300 rounded-full" />
              </div>

              {/* Document viewer — fills remaining space */}
              {viewerContent || pdfViewUrl ? (
                <div className="flex-1 flex flex-col overflow-hidden">
                  {/* Sticky close bar */}
                  <div className="shrink-0 px-4 py-2 bg-white border-b border-slate-200 flex items-center justify-between shadow-sm">
                    <span className="text-xs font-mono text-slate-600">{viewerFileName}</span>
                    <button
                      onClick={() => { setViewerContent(null); setViewerFileName(''); setPdfViewUrl(null) }}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium text-slate-600 hover:text-white hover:bg-dora-danger transition-colors border border-slate-200 hover:border-transparent"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Close file
                    </button>
                  </div>
                  {/* Scrollable content */}
                  <div className="flex-1 overflow-auto bg-white">
                    {pdfViewUrl ? (
                      <iframe
                        src={pdfViewUrl}
                        className="w-full h-full border-0"
                        title={viewerFileName}
                      />
                    ) : viewerContent ? (
                      <DocumentViewer content={viewerContent} fileName={viewerFileName} />
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  <p className="text-sm text-slate-400">Click a file above to view its contents.</p>
                </div>
              )}
            </div>
          ) : (
            /* Empty state */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center px-8">
                <svg className="w-12 h-12 mx-auto text-slate-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <p className="text-sm text-slate-400">
                  Upload contract PDFs on the left, then run analysis to see results here.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function FileIcon({ type }: { type: string }) {
  const color = type === 'csv' ? 'text-green-600' : type === 'json' ? 'text-dora-sky' : type === 'pdf' ? 'text-red-500' : 'text-slate-400'
  return (
    <div className={`w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center ${color}`}>
      <span className="text-[10px] font-mono font-bold uppercase">{type}</span>
    </div>
  )
}

function sortOutputFiles(files: OutputFile[]): OutputFile[] {
  // Order: summary PDF first, then submission CSV, evidence trace CSV, then JSON files, then anything else
  const priority: Record<string, number> = {
    'findings_summary.pdf': 1,
    'run_summary.json': 2,
    'submission.csv': 3,
    'evidence_trace.csv': 4,
    'findings_report.json': 5,
  }
  return [...files].sort((a, b) => {
    const pa = priority[a.file_name] ?? 99
    const pb = priority[b.file_name] ?? 99
    if (pa !== pb) return pa - pb
    return a.file_name.localeCompare(b.file_name)
  })
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
