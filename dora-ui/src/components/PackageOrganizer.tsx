import { useState } from 'react'

interface PackageOrganizerProps {
  looseFiles: string[]
  existingPackages: { name: string; files: string[] }[]
  onOrganize: (groups: Record<string, string[]>) => Promise<void>
  onSkip: () => void
}

export default function PackageOrganizer({ looseFiles, existingPackages, onOrganize, onSkip }: PackageOrganizerProps) {
  // Groups: package name -> list of file paths assigned to it
  const [groups, setGroups] = useState<Record<string, string[]>>({})
  const [newGroupName, setNewGroupName] = useState('')
  const [saving, setSaving] = useState(false)

  // Files not yet assigned to any group
  const assignedFiles = new Set(Object.values(groups).flat())
  const unassigned = looseFiles.filter((f) => !assignedFiles.has(f))

  const addGroup = () => {
    const name = newGroupName.trim()
    if (!name || groups[name]) return
    setGroups({ ...groups, [name]: [] })
    setNewGroupName('')
  }

  const removeGroup = (name: string) => {
    const updated = { ...groups }
    delete updated[name]
    setGroups(updated)
  }

  const assignFile = (file: string, groupName: string) => {
    // Remove from any current group
    const updated = { ...groups }
    for (const key of Object.keys(updated)) {
      updated[key] = updated[key].filter((f) => f !== file)
    }
    // Add to target group
    updated[groupName] = [...(updated[groupName] || []), file]
    setGroups(updated)
  }

  const unassignFile = (file: string) => {
    const updated = { ...groups }
    for (const key of Object.keys(updated)) {
      updated[key] = updated[key].filter((f) => f !== file)
    }
    setGroups(updated)
  }

  const handleSave = async () => {
    // Only send groups that have files
    const toSend: Record<string, string[]> = {}
    for (const [name, files] of Object.entries(groups)) {
      if (files.length > 0) {
        toSend[name] = files
      }
    }
    if (Object.keys(toSend).length === 0) return
    setSaving(true)
    await onOrganize(toSend)
    setSaving(false)
  }

  const allAssigned = unassigned.length === 0 && Object.keys(groups).length > 0

  return (
    <div className="p-4 bg-amber-50/50 border border-amber-200 rounded-lg">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-display font-semibold text-sm text-dora-navy">Organize into Packages</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {looseFiles.length} loose file{looseFiles.length !== 1 ? 's' : ''} detected.
            Group them into contract packages before analysis.
          </p>
        </div>
        <button onClick={onSkip} className="text-xs text-slate-400 hover:text-slate-600 transition-colors">
          Skip (treat as one package)
        </button>
      </div>

      {/* Create new group */}
      <div className="flex items-center gap-2 mb-3">
        <input
          type="text"
          value={newGroupName}
          onChange={(e) => setNewGroupName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addGroup()}
          placeholder="New package name (e.g. Harbor Crossing)"
          className="flex-1 px-3 py-1.5 border border-slate-300 rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-dora-sky focus:border-transparent"
        />
        <button onClick={addGroup} disabled={!newGroupName.trim()} className="btn-primary text-xs px-3 py-1.5">
          Add Group
        </button>
      </div>

      {/* Existing groups created by user or from folders */}
      <div className="space-y-2 mb-3">
        {existingPackages.map((pkg) => (
          <div key={pkg.name} className="bg-white border border-slate-200 rounded-md p-2">
            <div className="flex items-center gap-2 mb-1">
              <svg className="w-3.5 h-3.5 text-green-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <span className="text-xs font-medium text-slate-700">{pkg.name}</span>
              <span className="text-[10px] text-green-600 ml-auto">{pkg.files.length} files (from folder)</span>
            </div>
          </div>
        ))}

        {Object.entries(groups).map(([name, files]) => (
          <div key={name} className="bg-white border border-dora-sky/30 rounded-md p-2">
            <div className="flex items-center gap-2 mb-1">
              <svg className="w-3.5 h-3.5 text-dora-sky shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <span className="text-xs font-medium text-slate-700">{name}</span>
              <span className="text-[10px] text-slate-400 ml-auto">{files.length} files</span>
              <button
                onClick={() => removeGroup(name)}
                className="p-0.5 text-slate-300 hover:text-dora-danger transition-colors"
                title="Remove group"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            {/* Files in this group */}
            {files.length > 0 && (
              <div className="ml-5 space-y-0.5">
                {files.map((f) => (
                  <div key={f} className="flex items-center justify-between text-[11px] text-slate-600 py-0.5">
                    <span className="truncate">{f}</span>
                    <button
                      onClick={() => unassignFile(f)}
                      className="text-slate-300 hover:text-dora-danger text-[10px] shrink-0 ml-2"
                    >
                      remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Unassigned files */}
      {unassigned.length > 0 && Object.keys(groups).length > 0 && (
        <div className="mb-3">
          <p className="text-[11px] text-slate-500 font-medium mb-1">
            Unassigned files — click a group to assign:
          </p>
          <div className="space-y-1">
            {unassigned.map((file) => (
              <div key={file} className="flex items-center gap-2 text-xs bg-white border border-slate-200 rounded px-2 py-1.5">
                <svg className="w-3.5 h-3.5 text-dora-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <span className="truncate flex-1 text-slate-700">{file}</span>
                <div className="flex items-center gap-1 shrink-0">
                  {Object.keys(groups).map((groupName) => (
                    <button
                      key={groupName}
                      onClick={() => assignFile(file, groupName)}
                      className="px-2 py-0.5 text-[10px] rounded bg-dora-sky/10 text-dora-blue hover:bg-dora-sky/30 transition-colors truncate max-w-[100px]"
                      title={`Move to ${groupName}`}
                    >
                      {groupName}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unassigned files but no groups yet */}
      {unassigned.length > 0 && Object.keys(groups).length === 0 && (
        <div className="mb-3 text-xs text-slate-500">
          Create at least one group above, then assign your files to it.
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={!allAssigned || saving}
          className="btn-primary text-xs"
        >
          {saving ? 'Organizing...' : `Organize into ${Object.keys(groups).length} package${Object.keys(groups).length !== 1 ? 's' : ''}`}
        </button>
        {!allAssigned && Object.keys(groups).length > 0 && (
          <span className="text-[10px] text-amber-600">
            {unassigned.length} file{unassigned.length !== 1 ? 's' : ''} still unassigned
          </span>
        )}
      </div>
    </div>
  )
}
