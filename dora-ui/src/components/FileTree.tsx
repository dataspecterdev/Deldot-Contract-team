import { useState } from 'react'

interface FileTreeProps {
  files: { file_name: string; size_bytes: number }[]
  onDelete: (filePath: string) => void
  onFileClick?: (filePath: string) => void
}

interface TreeNode {
  name: string
  path: string
  isFolder: boolean
  children: TreeNode[]
  size?: number
}

function buildTree(files: { file_name: string; size_bytes: number }[]): TreeNode[] {
  const root: TreeNode[] = []

  for (const file of files) {
    const parts = file.file_name.split('/')
    let current = root

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isLast = i === parts.length - 1
      const pathSoFar = parts.slice(0, i + 1).join('/')

      let existing = current.find((n) => n.name === part && n.isFolder === !isLast)
      if (!existing) {
        existing = {
          name: part,
          path: pathSoFar,
          isFolder: !isLast,
          children: [],
          size: isLast ? file.size_bytes : undefined,
        }
        current.push(existing)
      }
      current = existing.children
    }
  }

  // Sort: folders first, then files, alphabetical within each
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.isFolder && !b.isFolder) return -1
      if (!a.isFolder && b.isFolder) return 1
      return a.name.localeCompare(b.name)
    })
    nodes.forEach((n) => sortNodes(n.children))
  }
  sortNodes(root)

  return root
}

export default function FileTree({ files, onDelete, onFileClick }: FileTreeProps) {
  const tree = buildTree(files)

  if (tree.length === 0) return null

  return (
    <div className="text-xs">
      {tree.map((node) => (
        <TreeNodeItem key={node.path} node={node} onDelete={onDelete} onFileClick={onFileClick} depth={0} />
      ))}
    </div>
  )
}

function TreeNodeItem({ node, onDelete, onFileClick, depth }: { node: TreeNode; onDelete: (path: string) => void; onFileClick?: (path: string) => void; depth: number }) {
  const [expanded, setExpanded] = useState(true)

  if (node.isFolder) {
    return (
      <div>
        <div
          className="flex items-center gap-1 py-1.5 px-2 rounded-md hover:bg-slate-50 cursor-pointer select-none"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          onClick={() => setExpanded(!expanded)}
        >
          {/* Arrow */}
          <svg
            className={`w-3 h-3 text-slate-400 transition-transform shrink-0 ${expanded ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          {/* Folder icon */}
          <svg className="w-4 h-4 text-dora-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
          </svg>
          <span className="text-slate-700 font-medium truncate">{node.name}</span>
          <span className="text-slate-400 ml-auto text-[10px]">{node.children.length}</span>
        </div>
        {expanded && (
          <div>
            {node.children.map((child) => (
              <TreeNodeItem key={child.path} node={child} onDelete={onDelete} onFileClick={onFileClick} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    )
  }

  // File node
  const isJson = node.name.toLowerCase().endsWith('.json')
  const isPdf = node.name.toLowerCase().endsWith('.pdf')
  return (
    <div
      className={`flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-slate-50 group ${onFileClick ? 'cursor-pointer' : ''}`}
      style={{ paddingLeft: `${depth * 12 + 20}px` }}
      onClick={() => onFileClick?.(node.path)}
    >
      <div className="flex items-center gap-2 min-w-0">
        {isJson ? (
          <svg className="w-3.5 h-3.5 text-dora-sky shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5 text-dora-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        )}
        <span className="text-slate-700 truncate">{node.name}</span>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(node.path) }}
        className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-dora-danger transition-all shrink-0"
        title="Delete file"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
