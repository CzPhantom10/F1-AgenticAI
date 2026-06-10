import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ErrorState, LoadingState } from '../components/PageState'
import { formatDate, formatPoints, fullName } from '../lib/format'
import { getDashboardData } from '../lib/f1Api'

export function DashboardPage() {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  useEffect(() => {
    let active = true

    getDashboardData()
      .then((data) => {
        if (active) setState({ loading: false, error: null, data })
      })
      .catch((error) => {
        if (active)
          setState({
            loading: false,
            error: error.message || 'Unable to load dashboard data.',
            data: null,
          })
      })

    return () => {
      active = false
    }
  }, [])

  if (state.loading) return <LoadingState label="Loading dashboard" />
  if (state.error) return <ErrorState message={state.error} />

  const { driverStandings, constructorStandings, latestResults, upcomingRace } = state.data
  const currentSeason = latestResults?.race?.season || '2026';

  return (
    <div className="space-y-4">
      {/* ── 1. Compact Dashboard Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-white/10 pb-4 mb-4 gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Formula 1 Command Center</h1>
          <p className="text-xs text-white/55 mt-0.5">Live championship analytics and race intelligence.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="f1-chip text-[10px] py-0.5 px-3">Season {currentSeason}</span>
        </div>
      </div>

      {/* ── 2. Statistics Row (KPI Tiles) ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="border border-white/5 bg-white/3 rounded-xl px-4 py-3 shadow-sm">
          <span className="text-[10px] uppercase tracking-[0.2em] text-white/40 font-semibold">Active Drivers</span>
          <p className="text-2xl font-bold text-white mt-0.5">{driverStandings.pagination.total}</p>
        </div>
        <div className="border border-white/5 bg-white/3 rounded-xl px-4 py-3 shadow-sm">
          <span className="text-[10px] uppercase tracking-[0.2em] text-white/40 font-semibold">Constructors</span>
          <p className="text-2xl font-bold text-white mt-0.5">{constructorStandings.pagination.total}</p>
        </div>
        <div className="border border-white/5 bg-white/3 rounded-xl px-4 py-3 shadow-sm">
          <span className="text-[10px] uppercase tracking-[0.2em] text-white/40 font-semibold">Rounds Scheduled</span>
          <p className="text-2xl font-bold text-white mt-0.5">22</p>
        </div>
        {driverStandings.items[0] && (
          <div className="border border-white/5 bg-white/3 rounded-xl px-4 py-3 shadow-sm">
            <span className="text-[10px] uppercase tracking-[0.2em] text-white/40 font-semibold">Championship Leader</span>
            <p className="text-sm font-bold text-red-300 mt-0.5 truncate">{fullName(driverStandings.items[0].driver)}</p>
            <p className="text-[10px] text-white/50">{formatPoints(driverStandings.items[0].points)} pts</p>
          </div>
        )}
      </div>

      {/* ── 3. Race Information Area (Two-Column Layout) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Last Race */}
        <div className="border border-white/5 bg-white/3 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-white/5 pb-2 mb-3">
            <span className="text-xs font-bold uppercase tracking-[0.2em] text-red-400">Last Race</span>
            <span className="text-[10px] text-white/40">{formatDate(latestResults.race.race_date)}</span>
          </div>
          <h3 className="text-md font-bold text-white">{latestResults.race.race_name}</h3>
          <p className="text-xs text-white/50 mt-0.5 mb-3">{latestResults.race.circuit?.name}</p>

          <div className="grid grid-cols-3 gap-2">
            {latestResults.results.slice(0, 3).map((res, i) => (
              <div key={res.id} className="bg-black/10 rounded-lg p-2.5 border border-white/5 text-center">
                <span className="text-[10px] font-bold text-red-300">
                  {i === 0 ? '🥇 P1' : i === 1 ? '🥈 P2' : '🥉 P3'}
                </span>
                <p className="text-xs font-semibold text-white truncate mt-1">{fullName(res.driver)}</p>
                <p className="text-[9px] text-white/40 truncate">{res.constructor?.name}</p>
                <p className="text-[10px] font-bold text-white/80 mt-1.5">{formatPoints(res.points)} pts</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Next Race */}
        <div className="border border-white/5 bg-white/3 rounded-xl p-4 shadow-sm">
          {upcomingRace ? (
            <div className="flex flex-col justify-between h-full">
              <div>
                <div className="flex items-center justify-between border-b border-white/5 pb-2 mb-3">
                  <span className="text-xs font-bold uppercase tracking-[0.2em] text-red-400">Next Race</span>
                  <span className="text-[10px] font-bold text-red-300 bg-red-500/10 px-2 py-0.5 rounded">
                    {upcomingRace.days_until} days remaining
                  </span>
                </div>
                <h3 className="text-md font-bold text-white">{upcomingRace.race_name}</h3>
                <p className="text-xs text-white/50 mt-0.5 mb-3">{upcomingRace.circuit?.name} · {upcomingRace.circuit?.country}</p>
              </div>

              <div className="flex items-center justify-between text-xs text-white/70 bg-black/15 p-2.5 rounded-lg border border-white/5">
                <div>
                  <p className="text-[9px] uppercase tracking-[0.1em] text-white/40">Race Date</p>
                  <p className="font-semibold">{formatDate(upcomingRace.race_date)}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-[0.1em] text-white/40">Round</p>
                  <p className="font-semibold text-right">R{upcomingRace.round_number}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col justify-between">
              <div className="flex items-center justify-between border-b border-white/5 pb-2 mb-3">
                <span className="text-xs font-bold uppercase tracking-[0.2em] text-red-400">Next Race</span>
              </div>
              <div className="py-6 text-center text-xs text-white/45">
                No upcoming race scheduled.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 4. Standings Preview (Clean Tables) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Driver Standings preview */}
        <div className="border border-white/5 bg-white/3 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
            <span className="text-xs font-bold uppercase tracking-[0.2em] text-red-400">Drivers Championship</span>
            <Link to="/drivers" className="text-[10px] text-white/60 hover:text-white border border-white/10 rounded px-2.5 py-0.5 bg-white/5 transition">
              View All
            </Link>
          </div>
          <div className="space-y-1">
            {driverStandings.items.slice(0, 5).map((entry) => (
              <Link
                key={entry.driver.id}
                to={`/drivers/${entry.driver.id}`}
                className="flex items-center justify-between text-xs px-2 py-1.5 hover:bg-white/5 rounded transition cursor-pointer"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-bold text-white/40 w-4">{entry.position}</span>
                  <span className="font-semibold text-white truncate">{fullName(entry.driver)}</span>
                  <span className="text-[9px] text-white/40">{entry.driver.driver_code}</span>
                </div>
                <span className="font-semibold text-red-300">{formatPoints(entry.points)}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Constructor Standings preview */}
        <div className="border border-white/5 bg-white/3 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
            <span className="text-xs font-bold uppercase tracking-[0.2em] text-red-400">Constructors Championship</span>
            <Link to="/constructors" className="text-[10px] text-white/60 hover:text-white border border-white/10 rounded px-2.5 py-0.5 bg-white/5 transition">
              View All
            </Link>
          </div>
          <div className="space-y-1">
            {constructorStandings.items.slice(0, 5).map((entry) => (
              <div
                key={entry.constructor.id}
                className="flex items-center justify-between text-xs px-2 py-1.5 hover:bg-white/5 rounded transition"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-bold text-white/40 w-4">{entry.position}</span>
                  <span className="font-semibold text-white truncate">{entry.constructor.name}</span>
                </div>
                <span className="font-semibold text-red-300">{formatPoints(entry.points)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 5. AI Analyst & ML Factors preview ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Prediction Factors */}
        <div className="border border-white/5 bg-white/3 rounded-xl p-4 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-red-400 block mb-3 border-b border-white/5 pb-2">
            Prediction Engine V2
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[10px]">
            {[
              { label: 'Recent Form (40%)', desc: 'Wins, podiums, points last 5 rounds' },
              { label: 'Circuit History (20%)', desc: 'Driver records at target track' },
              { label: 'Constructor Form (20%)', desc: 'Championship points trend' },
              { label: 'Qualifying Record (10%)', desc: 'Starting grid or avg qual position' },
              { label: 'Championship Standing (10%)', desc: 'Season points comparison' },
            ].map((f, i) => (
              <div key={i} className="bg-black/10 rounded p-2 border border-white/5">
                <p className="font-semibold text-white/95">{f.label}</p>
                <p className="text-[9px] text-white/45 truncate mt-0.5">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* AI Analyst Panel */}
        <div className="border border-white/5 bg-white/3 rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.2em] text-red-400 block mb-2 border-b border-white/5 pb-2">
              AI Analyst Unit
            </span>
            <p className="text-xs text-white/60 leading-relaxed">
              Racecraft AI provides direct conversational analytics, historical summaries, and race predictions powered by Groq and localized F1 memory databases.
            </p>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-white/5 pt-3">
            <span className="text-[9px] uppercase tracking-[0.2em] text-white/30">llama-3.3-70b active</span>
            <Link to="/analyst" className="text-xs text-red-300 font-bold hover:text-red-400 flex items-center gap-1 transition">
              Launch Agent &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
