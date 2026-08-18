import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createProject, listProjects, deleteProject, type Project } from '../api/client'

export default function HomePage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [mode, setMode] = useState<'standard' | 'incognito'>('standard')
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const data = await listProjects()
      setProjects(data)
    } catch {
      // API not running yet — that's fine
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    const project = await createProject(name.trim(), mode)
    setShowCreate(false)
    setName('')
    setMode('standard')
    navigate(`/project/${project.id}`)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this project and all its files?')) return
    await deleteProject(id)
    refresh()
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      {/* Hero */}
      <div className="mb-10">
        <h2 className="font-display font-bold text-3xl text-dora-navy mb-2">
          Contract Review Workspace
        </h2>
        <p className="text-slate-500 text-base max-w-xl">
          Upload contract PDFs, run automated clause risk analysis, and download
          structured findings. Each project is a self-contained review.
        </p>
      </div>

      {/* Create button */}
      <div className="mb-8">
        {!showCreate ? (
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Project
          </button>
        ) : (
          <form onSubmit={handleCreate} className="card p-5 max-w-md">
            <h3 className="font-display font-semibold text-base mb-4">Create Project</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">Project Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Harbor Crossing Review"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dora-sky focus:border-transparent"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">Mode</label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="mode"
                      value="standard"
                      checked={mode === 'standard'}
                      onChange={() => setMode('standard')}
                      className="text-dora-blue"
                    />
                    <span>Standard</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="mode"
                      value="incognito"
                      checked={mode === 'incognito'}
                      onChange={() => setMode('incognito')}
                      className="text-dora-blue"
                    />
                    <span className="flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                      </svg>
                      Incognito
                    </span>
                  </label>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  {mode === 'incognito'
                    ? 'Files will be deleted when you close this tab.'
                    : 'Files persist until you delete the project.'}
                </p>
              </div>
              <div className="flex gap-2">
                <button type="submit" className="btn-primary" disabled={!name.trim()}>
                  Create
                </button>
                <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary">
                  Cancel
                </button>
              </div>
            </div>
          </form>
        )}
      </div>

      {/* Projects list */}
      {loading ? (
        <div className="text-sm text-slate-400">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="card p-10 text-center text-slate-400">
          <p className="text-sm">No projects yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {projects.map((project) => (
            <div
              key={project.id}
              className="card px-5 py-4 flex items-center justify-between hover:border-dora-sky/50 transition-colors cursor-pointer"
              onClick={() => navigate(`/project/${project.id}`)}
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-dora-sand flex items-center justify-center">
                  <svg className="w-5 h-5 text-dora-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                  </svg>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-display font-semibold text-sm text-dora-navy">{project.name}</h3>
                    {project.mode === 'incognito' && (
                      <span className="text-[10px] uppercase tracking-wider bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                        incognito
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {project.file_count} file{project.file_count !== 1 ? 's' : ''} · {project.status}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={project.status} />
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(project.id) }}
                  className="p-1.5 text-slate-300 hover:text-dora-danger transition-colors rounded"
                  title="Delete project"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: 'bg-slate-100 text-slate-600',
    analyzing: 'bg-amber-50 text-amber-700',
    complete: 'bg-green-50 text-green-700',
    error: 'bg-red-50 text-red-700',
  }
  return (
    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${styles[status] || styles.ready}`}>
      {status}
    </span>
  )
}
