import { NavLink, Outlet } from 'react-router-dom'

import { useAppContext } from '../context/AppContext'

const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/drivers', label: 'Drivers' },
  { to: '/constructors', label: 'Constructors' },
  { to: '/races', label: 'Races' },
  { to: '/analyst', label: 'Analyst' },
]

export function AppLayout() {
  const { season } = useAppContext()

  return (
    <div className="min-h-screen text-white">
      <div className="fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute left-0 top-0 h-72 w-72 rounded-full bg-red-500/20 blur-3xl" />
        <div className="absolute right-0 top-20 h-96 w-96 rounded-full bg-white/5 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-80 w-80 rounded-full bg-red-950/30 blur-3xl" />
      </div>

      <header className="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="glass-panel flex flex-col gap-4 rounded-[1.75rem] px-5 py-4 shadow-glow sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-display text-xs uppercase tracking-[0.45em] text-red-300/90">
              PitWall AI
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-bold text-white sm:text-4xl">Formula 1 Command Center</h1>
            </div>
          </div>
          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `nav-link ${isActive ? 'nav-link-active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl px-4 pb-12 pt-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
