import { Link } from 'react-router-dom'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-dora-navy text-white shadow-lg">
        <div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
            <div className="w-9 h-9 rounded-lg bg-dora-sky flex items-center justify-center">
              <span className="font-display font-bold text-lg">D</span>
            </div>
            <div>
              <h1 className="font-display font-bold text-lg leading-tight tracking-tight">DORA</h1>
              <p className="text-[10px] text-slate-300 leading-none tracking-wider uppercase">
                DelDOT Orchestrated Review Assistant
              </p>
            </div>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link to="/" className="text-slate-300 hover:text-white transition-colors">
              Projects
            </Link>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white">
        <div className="max-w-screen-2xl mx-auto px-6 py-3 text-center">
          <p className="text-xs text-slate-400 font-medium">
            This is not an official DelDOT application.
          </p>
        </div>
      </footer>
    </div>
  )
}
