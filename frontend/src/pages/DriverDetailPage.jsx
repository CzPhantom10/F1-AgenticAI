import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

import { GlassCard } from '../components/GlassCard'
import { ErrorState, LoadingState } from '../components/PageState'
import { formatDate, formatPoints, fullName } from '../lib/format'
import { getDriverDetail } from '../lib/f1Api'

// ── Stat tile ──────────────────────────────────────────────────────────────
function StatTile({ label, value, accent = false }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
      <p className="text-xs uppercase tracking-[0.35em] text-white/45">{label}</p>
      <p
        className={`mt-2 font-display text-3xl font-bold ${
          accent ? 'text-red-200' : 'text-white'
        }`}
      >
        {value}
      </p>
    </div>
  )
}

// ── Position badge ─────────────────────────────────────────────────────────
function PosBadge({ pos }) {
  if (pos == null) return <span className="text-white/30">—</span>

  const color =
    pos === 1
      ? 'text-yellow-300'
      : pos <= 3
        ? 'text-red-200'
        : 'text-white/80'

  return <span className={`font-display text-xl font-bold ${color}`}>P{pos}</span>
}

// ── Status pill ────────────────────────────────────────────────────────────
function StatusPill({ status }) {
  const finished = status === 'Finished'
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        finished
          ? 'bg-emerald-500/15 text-emerald-300'
          : 'bg-white/8 text-white/55'
      }`}
    >
      {status}
    </span>
  )
}

// ── Recent results table ───────────────────────────────────────────────────
function RecentResultsTable({ results }) {
  if (!results.length) {
    return (
      <div className="rounded-2xl border border-dashed border-white/15 bg-black/20 p-5 text-sm text-white/55">
        No race results found.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <div className="min-w-[640px]">
        {/* Header */}
        <div className="grid grid-cols-[2fr_1.2fr_72px_72px_72px_100px_120px] gap-3 border-b border-white/10 bg-black/25 px-4 py-3 text-xs uppercase tracking-[0.28em] text-white/40">
          <span>Race</span>
          <span>Team</span>
          <span>Grid</span>
          <span>Finish</span>
          <span>Pts</span>
          <span>Status</span>
          <span>Date</span>
        </div>

        {/* Rows */}
        <div className="divide-y divide-white/5 bg-white/3">
          {results.map((r) => (
            <div
              key={`${r.race_id}`}
              className="grid grid-cols-[2fr_1.2fr_72px_72px_72px_100px_120px] gap-3 px-4 py-3 transition hover:bg-white/5"
            >
              {/* Race name + circuit */}
              <div>
                <p className="text-sm font-semibold text-white">{r.race_name}</p>
                <p className="text-xs text-white/45">
                  {r.circuit_country} · R{r.round_number} · {r.season}
                </p>
              </div>

              {/* Constructor */}
              <p className="self-center text-sm text-white/70">{r.constructor_name}</p>

              {/* Grid */}
              <p className="self-center text-sm text-white/60">
                {r.grid_position != null ? `P${r.grid_position}` : '—'}
              </p>

              {/* Finish */}
              <div className="self-center">
                <PosBadge pos={r.finish_position} />
              </div>

              {/* Points */}
              <p className="self-center font-display text-base font-bold text-red-200">
                {r.points != null ? formatPoints(r.points) : '—'}
              </p>

              {/* Status */}
              <div className="self-center">
                <StatusPill status={r.status} />
              </div>

              {/* Date */}
              <p className="self-center text-xs text-white/45">{formatDate(r.race_date)}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export function DriverDetailPage() {
  const { driverId } = useParams()
  const [state, setState] = useState({ loading: true, error: null, data: null })

  useEffect(() => {
    let active = true
    setState({ loading: true, error: null, data: null })

    getDriverDetail(driverId)
      .then((data) => {
        if (active) setState({ loading: false, error: null, data })
      })
      .catch((err) => {
        if (active)
          setState({
            loading: false,
            error: err.message || 'Unable to load driver details.',
            data: null,
          })
      })

    return () => {
      active = false
    }
  }, [driverId])

  if (state.loading) return <LoadingState label="Loading driver" />
  if (state.error) return <ErrorState message={state.error} />

  const { driver, total_races, total_wins, total_podiums, total_points, avg_finish_position, recent_results } =
    state.data

  const avgFinish =
    avg_finish_position != null ? avg_finish_position.toFixed(1) : '—'

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to="/drivers"
        className="inline-flex items-center gap-2 text-sm text-white/55 transition hover:text-white"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4"
        >
          <path
            fillRule="evenodd"
            d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10Z"
            clipRule="evenodd"
          />
        </svg>
        Back to Drivers
      </Link>

      {/* Hero card */}
      <div className="glass-panel rounded-[1.5rem] p-6">
        {/* Decorative glow blobs */}
        <div className="pointer-events-none absolute right-0 top-0 h-64 w-64 rounded-full bg-red-500/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-1/4 h-48 w-48 rounded-full bg-white/4 blur-3xl" />

        <div className="relative">
          {/* Eyebrow */}
          <p className="card-title">Driver profile</p>

          {/* Name + code */}
          <div className="mt-3 flex flex-wrap items-end gap-4">
            <h1 className="font-display text-5xl font-bold text-white sm:text-6xl">
              {fullName(driver)}
            </h1>
            <span className="f1-chip mb-1">{driver.driver_code}</span>
          </div>

          {/* Nationality */}
          <p className="mt-2 text-sm text-white/55">{driver.nationality}</p>

          {/* Stat grid */}
          <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatTile label="Races" value={total_races} />
            <StatTile label="Wins" value={total_wins} />
            <StatTile label="Podiums" value={total_podiums} />
            <StatTile label="Points" value={formatPoints(total_points)} accent />
            <StatTile label="Avg Finish" value={avgFinish} />
          </div>
        </div>
      </div>

      {/* Recent results */}
      <GlassCard
        eyebrow="Race history"
        title="Recent results"
        subtitle="Last 10 race appearances, most recent first."
      >
        <RecentResultsTable results={recent_results} />
      </GlassCard>
    </div>
  )
}
