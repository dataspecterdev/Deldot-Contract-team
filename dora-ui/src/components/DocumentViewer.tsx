import { useMemo } from 'react'

interface DocumentViewerProps {
  content: string
  fileName: string
}

export default function DocumentViewer({ content, fileName }: DocumentViewerProps) {
  const isJson = fileName.endsWith('.json')
  const isCsv = fileName.endsWith('.csv')
  const isPdf = fileName.endsWith('.pdf')

  if (isPdf) {
    return <PdfNotice fileName={fileName} />
  }
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
    // Re-join lines that are inside quoted fields (CSV allows newlines within quotes)
    const rows: string[] = []
    let current = ''
    let inQuotes = false
    for (const line of lines) {
      if (current) {
        current += '\n' + line
      } else {
        current = line
      }
      // Count unescaped quotes to determine if we're still inside a quoted field
      for (const ch of line) {
        if (ch === '"') inQuotes = !inQuotes
      }
      if (!inQuotes) {
        rows.push(current)
        current = ''
      }
    }
    if (current) rows.push(current)

    return rows.map((row) => {
      // RFC 4180 CSV parsing: handles quoted fields with commas and newlines
      const cells: string[] = []
      let cell = ''
      let quoted = false
      for (let i = 0; i < row.length; i++) {
        const ch = row[i]
        if (quoted) {
          if (ch === '"') {
            // Check for escaped quote ("")
            if (i + 1 < row.length && row[i + 1] === '"') {
              cell += '"'
              i++ // skip next quote
            } else {
              quoted = false
            }
          } else {
            cell += ch
          }
        } else {
          if (ch === '"') {
            quoted = true
          } else if (ch === ',') {
            cells.push(cell)
            cell = ''
          } else {
            cell += ch
          }
        }
      }
      cells.push(cell)
      return cells
    })
  }, [content])

  if (rows.length === 0) return <p className="p-4 text-sm text-slate-400">Empty file</p>

  const headers = rows[0]
  const data = rows.slice(1)

  return (
    // No `overflow-*` here on purpose: the parent in WorkspacePage is the scroll
    // container, and `position: sticky` only sticks relative to the nearest
    // scrollport. An intermediate overflow wrapper would capture the sticky
    // header and let it scroll away with the rows.
    <div>
      <table className="w-full text-xs border-separate border-spacing-0">
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th
                key={i}
                // sticky lives on the cells (not just <thead>) so it works
                // consistently across browsers; the bottom rule is an inset
                // shadow because collapsed-table borders scroll away.
                className="sticky top-0 z-10 bg-slate-50 px-3 py-2 text-left font-semibold text-slate-600 whitespace-nowrap shadow-[inset_0_-1px_0_theme(colors.slate.200)]"
              >
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

function PdfNotice({ fileName }: { fileName: string }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center">
        <svg className="w-12 h-12 mx-auto text-slate-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
        <p className="text-sm font-medium text-slate-600 mb-1">{fileName}</p>
        <p className="text-xs text-slate-400 mb-3">PDF files cannot be previewed inline. Use the download button to open it.</p>
      </div>
    </div>
  )
}
