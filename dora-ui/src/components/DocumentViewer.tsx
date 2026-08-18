import { useMemo } from 'react'

interface DocumentViewerProps {
  content: string
  fileName: string
}

export default function DocumentViewer({ content, fileName }: DocumentViewerProps) {
  const isJson = fileName.endsWith('.json')
  const isCsv = fileName.endsWith('.csv')

  if (isJson) {
    return <JsonViewer content={content} />
  }
  if (isCsv) {
    return <CsvViewer content={content} />
  }
  return <PlainViewer content={content} />
}

function JsonViewer({ content }: { content: string }) {
  const parsed = useMemo(() => {
    try {
      return JSON.stringify(JSON.parse(content), null, 2)
    } catch {
      return content
    }
  }, [content])

  return (
    <pre className="p-4 text-xs font-mono text-slate-700 leading-relaxed whitespace-pre-wrap break-words">
      {parsed}
    </pre>
  )
}

function CsvViewer({ content }: { content: string }) {
  const rows = useMemo(() => {
    const lines = content.split('\n').filter((l) => l.trim())
    return lines.map((line) => {
      // Simple CSV parsing (handles basic comma-separated values)
      const cells: string[] = []
      let current = ''
      let inQuotes = false
      for (let i = 0; i < line.length; i++) {
        const ch = line[i]
        if (ch === '"') {
          inQuotes = !inQuotes
        } else if (ch === ',' && !inQuotes) {
          cells.push(current.trim())
          current = ''
        } else {
          current += ch
        }
      }
      cells.push(current.trim())
      return cells
    })
  }, [content])

  if (rows.length === 0) return <p className="p-4 text-sm text-slate-400">Empty file</p>

  const headers = rows[0]
  const data = rows.slice(1)

  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead className="bg-slate-50 sticky top-0">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="px-3 py-2 text-left font-semibold text-slate-600 border-b border-slate-200 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, ri) => (
            <tr key={ri} className="hover:bg-slate-50/50">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 border-b border-slate-100 text-slate-700 max-w-xs truncate" title={cell}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PlainViewer({ content }: { content: string }) {
  return (
    <pre className="p-4 text-xs font-mono text-slate-700 leading-relaxed whitespace-pre-wrap">
      {content}
    </pre>
  )
}
