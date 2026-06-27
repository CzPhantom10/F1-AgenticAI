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
    <div className="min-h-screen text-white bg-zinc-950">
      <header className="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="glass-panel flex flex-col gap-4 rounded-xl px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-red-500 font-semibold">
              Racecraft F1
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-white tracking-tight sm:text-3xl">Formula 1 Analytics & Insights</h1>
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
