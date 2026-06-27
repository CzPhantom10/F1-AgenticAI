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
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-zinc-800 pb-4 mb-4 gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Formula 1 Standings & Results</h1>
          <p className="text-xs text-zinc-400 mt-0.5">Current standings, recent race results, and upcoming calendar schedule.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="f1-chip text-[10px] py-0.5 px-3">Season {currentSeason}</span>
        </div>
      </div>

      {/* ── 2. Statistics Row (KPI Tiles) ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl px-4 py-3 shadow-sm">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">Active Drivers</span>
          <p className="text-2xl font-bold text-white mt-0.5">{driverStandings.pagination.total}</p>
        </div>
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl px-4 py-3 shadow-sm">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">Constructors</span>
          <p className="text-2xl font-bold text-white mt-0.5">{constructorStandings.pagination.total}</p>
        </div>
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl px-4 py-3 shadow-sm">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">Rounds Scheduled</span>
          <p className="text-2xl font-bold text-white mt-0.5">22</p>
        </div>
        {driverStandings.items[0] && (
          <div className="border border-zinc-800 bg-zinc-900 rounded-xl px-4 py-3 shadow-sm">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">Championship Leader</span>
            <p className="text-sm font-bold text-red-400 mt-0.5 truncate">{fullName(driverStandings.items[0].driver)}</p>
            <p className="text-[10px] text-zinc-400">{formatPoints(driverStandings.items[0].points)} pts</p>
          </div>
        )}
      </div>

      {/* ── 3. Race Information Area (Two-Column Layout) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Last Race */}
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-red-500">Last Race</span>
            <span className="text-[10px] text-zinc-400">{formatDate(latestResults.race.race_date)}</span>
          </div>
          <h3 className="text-md font-bold text-white">{latestResults.race.race_name}</h3>
          <p className="text-xs text-zinc-400 mt-0.5 mb-3">{latestResults.race.circuit?.name}</p>

          <div className="grid grid-cols-3 gap-2">
            {latestResults.results.slice(0, 3).map((res, i) => (
              <div key={res.id} className="bg-zinc-950 rounded-lg p-2.5 border border-zinc-800 text-center">
                <span className="text-[10px] font-bold text-red-400">
                  {i === 0 ? 'P1' : i === 1 ? 'P2' : 'P3'}
                </span>
                <p className="text-xs font-semibold text-white truncate mt-1">{fullName(res.driver)}</p>
                <p className="text-[9px] text-zinc-500 truncate">{res.constructor?.name}</p>
                <p className="text-[10px] font-bold text-zinc-300 mt-1.5">{formatPoints(res.points)} pts</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Next Race */}
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-4 shadow-sm">
          {upcomingRace ? (
            <div className="flex flex-col justify-between h-full">
              <div>
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-red-500">Next Race</span>
                  <span className="text-[10px] font-semibold text-red-400 bg-red-600/10 px-2 py-0.5 rounded border border-red-600/20">
                    {upcomingRace.days_until} days remaining
                  </span>
                </div>
                <h3 className="text-md font-bold text-white">{upcomingRace.race_name}</h3>
                <p className="text-xs text-zinc-400 mt-0.5 mb-3">{upcomingRace.circuit?.name} · {upcomingRace.circuit?.country}</p>
              </div>

              <div className="flex items-center justify-between text-xs text-zinc-300 bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-zinc-500">Race Date</p>
                  <p className="font-semibold">{formatDate(upcomingRace.race_date)}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-zinc-500">Round</p>
                  <p className="font-semibold text-right">R{upcomingRace.round_number}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col justify-between">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-red-500">Next Race</span>
              </div>
              <div className="py-6 text-center text-xs text-zinc-500">
                No upcoming race scheduled.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 4. Standings Preview (Clean Tables) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Driver Standings preview */}
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3 border-b border-zinc-800 pb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-red-500">Drivers Championship</span>
            <Link to="/drivers" className="text-[10px] text-zinc-300 hover:text-white border border-zinc-800 rounded px-2.5 py-1 bg-zinc-950 transition hover:bg-zinc-900 cursor-pointer font-semibold">
              View All
            </Link>
          </div>
          <div className="space-y-1">
            {driverStandings.items.slice(0, 5).map((entry) => (
              <Link
                key={entry.driver.id}
                to={`/drivers/${entry.driver.id}`}
                className="flex items-center justify-between text-xs px-2 py-1.5 hover:bg-zinc-800 rounded transition cursor-pointer"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-bold text-zinc-500 w-4">{entry.position}</span>
                  <span className="font-semibold text-white truncate">{fullName(entry.driver)}</span>
                  <span className="text-[9px] text-zinc-500">{entry.driver.driver_code}</span>
                </div>
                <span className="font-semibold text-red-400">{formatPoints(entry.points)}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Constructor Standings preview */}
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3 border-b border-zinc-800 pb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-red-500">Constructors Championship</span>
            <Link to="/constructors" className="text-[10px] text-zinc-300 hover:text-white border border-zinc-800 rounded px-2.5 py-1 bg-zinc-950 transition hover:bg-zinc-900 cursor-pointer font-semibold">
              View All
            </Link>
          </div>
          <div className="space-y-1">
            {constructorStandings.items.slice(0, 5).map((entry) => (
              <div
                key={entry.constructor.id}
                className="flex items-center justify-between text-xs px-2 py-1.5 hover:bg-zinc-800 rounded transition"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-bold text-zinc-500 w-4">{entry.position}</span>
                  <span className="font-semibold text-white truncate">{entry.constructor.name}</span>
                </div>
                <span className="font-semibold text-red-400">{formatPoints(entry.points)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 5. AI Analyst & Season Statistics ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Live Season Statistics Summary */}
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-4 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-red-500 block mb-3 border-b border-zinc-800 pb-2">
            Season Standings Summary
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {driverStandings.items.length >= 2 && (
              <div className="bg-zinc-950 rounded p-2.5 border border-zinc-800">
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">Championship Gap</p>
                <p className="font-bold text-white mt-0.5">
                  {driverStandings.items[0].points - driverStandings.items[1].points} pts
                </p>
                <p className="text-[9px] text-zinc-400 truncate mt-0.5">
                  Between {fullName(driverStandings.items[0].driver)} and {fullName(driverStandings.items[1].driver)}
                </p>
              </div>
            )}
            {constructorStandings.items.length >= 1 && (
              <div className="bg-zinc-950 rounded p-2.5 border border-zinc-800">
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">Constructor Leader</p>
                <p className="font-bold text-white mt-0.5">
                  {constructorStandings.items[0].constructor.name}
                </p>
                <p className="text-[9px] text-zinc-400 truncate mt-0.5">
                  Leading with {formatPoints(constructorStandings.items[0].points)} pts
                </p>
              </div>
            )}
            {latestResults?.results?.[0] && (
              <div className="bg-zinc-950 rounded p-2.5 border border-zinc-800">
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">Latest Winner</p>
                <p className="font-bold text-white mt-0.5">
                  {fullName(latestResults.results[0].driver)}
                </p>
                <p className="text-[9px] text-zinc-400 truncate mt-0.5">
                  Won the {latestResults.race.race_name}
                </p>
              </div>
            )}
            {upcomingRace && (
              <div className="bg-zinc-950 rounded p-2.5 border border-zinc-800">
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">Next Venue</p>
                <p className="font-bold text-white mt-0.5">
                  {upcomingRace.circuit?.name}
                </p>
                <p className="text-[9px] text-zinc-400 truncate mt-0.5">
                  Located in {upcomingRace.circuit?.country}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* AI Analyst Panel */}
        <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-red-500 block mb-2 border-b border-zinc-800 pb-2">
              F1 AI Assistant
            </span>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Ask details about race history, driver comparisons, and season trends. Answers are generated using local race database contexts from 2018 to the present.
            </p>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-zinc-800 pt-3">
            <span className="text-[9px] uppercase tracking-wider text-zinc-500">Model: Llama 3.3 (Groq)</span>
            <Link to="/analyst" className="text-xs text-red-400 font-bold hover:text-red-500 flex items-center gap-1 transition">
              Open Analyst Chat &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
