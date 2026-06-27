import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ErrorState, LoadingState } from '../components/PageState'
import { formatDate, formatPoints, fullName } from '../lib/format'
import { getRaceResults, getRaceQualifying } from '../lib/f1Api'

// ── Helpers ────────────────────────────────────────────────────────────────

const COUNTRY_FLAGS = {
  Australia: '🇦🇺', Austria: '🇦🇹', Azerbaijan: '🇦🇿', Bahrain: '🇧🇭',
  Belgium: '🇧🇪', Brazil: '🇧🇷', Canada: '🇨🇦', China: '🇨🇳',
  France: '🇫🇷', Germany: '🇩🇪', Hungary: '🇭🇺', Italy: '🇮🇹',
  Japan: '🇯🇵', Mexico: '🇲🇽', Monaco: '🇲🇨', Netherlands: '🇳🇱',
  Portugal: '🇵🇹', Qatar: '🇶🇦', Russia: '🇷🇺', 'Saudi Arabia': '🇸🇦',
  Singapore: '🇸🇬', Spain: '🇪🇸', 'United Kingdom': '🇬🇧', 'United States': '🇺🇸',
  USA: '🇺🇸', UAE: '🇦🇪', 'Abu Dhabi': '🇦🇪', Turkey: '🇹🇷',
  'South Africa': '🇿🇦', Vietnam: '🇻🇳', 'Las Vegas': '🇺🇸', Miami: '🇺🇸',
}

function flagFor(country) {
  return ''
}

function positionColor(pos) {
  if (pos === 1) return 'text-yellow-300'
  if (pos === 2) return 'text-slate-300'
  if (pos === 3) return 'text-amber-500'
  return 'text-white/50'
}

function StatusPill({ status }) {
  const isFinished = status === 'Finished' || /^\+\d/.test(status)
  return (
    <span
      className={`rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
        isFinished
          ? 'border-zinc-800 bg-zinc-900 text-zinc-400'
          : 'border-red-600/30 bg-red-600/10 text-red-400'
      }`}
    >
      {status}
    </span>
  )
}

// ── Past Race ────────────────────────────────────────────────────────────────

function PastRaceView({ race, results, qualifying }) {
  const [tab, setTab] = useState('race')
  const podium = results.slice(0, 3)
  const medals = ['1st', '2nd', '3rd']

  return (
    <div className="space-y-5">
      {/* Podium */}
      <div className="glass-panel rounded-xl p-6">
        <p className="card-title mb-4">Podium</p>
        <div className="grid gap-4 sm:grid-cols-3">
          {podium.map((r, i) => (
            <div
              key={r.id}
              className={`relative overflow-hidden rounded-xl border p-5 text-center ${
                i === 0
                  ? 'border-yellow-600/30 bg-zinc-900'
                  : i === 1
                  ? 'border-zinc-700 bg-zinc-900'
                  : 'border-amber-700/30 bg-zinc-900'
              }`}
            >
              <p className="text-sm font-bold uppercase tracking-wider text-zinc-500">{medals[i]}</p>
              <Link
                to={`/drivers/${r.driver.id}`}
                className="mt-3 block text-lg font-bold text-white hover:text-red-400 transition"
              >
                {fullName(r.driver)}
              </Link>
              <p className="text-xs text-zinc-500">{r.constructor.name}</p>
              <p className="mt-3 font-display text-3xl font-bold text-red-400">
                {formatPoints(r.points)}
                <span className="ml-1 text-sm font-normal text-zinc-500">pts</span>
              </p>
              <p className="mt-1 text-xs text-zinc-500">Grid P{r.grid_position ?? '?'}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="glass-panel rounded-xl p-6">
        <div className="mb-5 flex gap-2">
          {['race', 'qualifying'].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded border px-4 py-2 text-sm font-medium transition cursor-pointer ${
                tab === t
                  ? 'border-red-600/50 bg-red-600/10 text-red-500'
                  : 'border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-white'
              }`}
            >
              {t === 'race' ? 'Race Results' : 'Qualifying'}
            </button>
          ))}
        </div>

        {tab === 'race' && (
          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <div className="min-w-[560px]">
              <div className="grid grid-cols-[52px_1.8fr_1.2fr_80px_80px_90px] gap-2 border-b border-zinc-800 bg-zinc-950/60 px-4 py-3 text-xs uppercase tracking-wider text-zinc-500 font-semibold">
                <span>Pos</span>
                <span>Driver</span>
                <span>Team</span>
                <span className="text-center">Grid</span>
                <span className="text-right">Points</span>
                <span className="text-right">Status</span>
              </div>
              <div className="divide-y divide-zinc-800/60">
                {results.map((r) => (
                  <div
                    key={r.id}
                    className="grid grid-cols-[52px_1.8fr_1.2fr_80px_80px_90px] gap-2 px-4 py-3 transition hover:bg-zinc-850"
                  >
                    <span className={`font-display text-xl font-bold ${positionColor(r.finish_position)}`}>
                      {r.finish_position ?? '—'}
                    </span>
                    <Link
                      to={`/drivers/${r.driver.id}`}
                      className="self-center font-medium text-white hover:text-red-400 transition truncate"
                    >
                      {fullName(r.driver)}
                      <span className="ml-1.5 text-xs text-zinc-500">{r.driver.driver_code}</span>
                    </Link>
                    <span className="self-center truncate text-sm text-zinc-400">{r.constructor.name}</span>
                    <span className="self-center text-center text-sm text-zinc-500">
                      {r.grid_position ?? '—'}
                    </span>
                    <span className="self-center text-right font-display text-base font-bold text-red-400">
                      {formatPoints(r.points)}
                    </span>
                    <div className="self-center text-right">
                      <StatusPill status={r.status} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'qualifying' && (
          <>
            {qualifying.length === 0 ? (
              <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 p-8 text-center text-sm text-zinc-500">
                No qualifying data available for this race.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-zinc-800">
                <div className="min-w-[460px]">
                  <div className="grid grid-cols-[52px_1.8fr_1.2fr_90px_90px_90px] gap-2 border-b border-zinc-800 bg-zinc-950/60 px-4 py-3 text-xs uppercase tracking-wider text-zinc-500 font-semibold">
                    <span>Pos</span>
                    <span>Driver</span>
                    <span>Team</span>
                    <span className="text-right">Q1</span>
                    <span className="text-right">Q2</span>
                    <span className="text-right">Q3</span>
                  </div>
                  <div className="divide-y divide-zinc-800/60">
                    {qualifying.map((q) => (
                      <div
                        key={q.id}
                        className="grid grid-cols-[52px_1.8fr_1.2fr_90px_90px_90px] gap-2 px-4 py-3 hover:bg-zinc-850"
                      >
                        <span className={`font-display text-xl font-bold ${positionColor(q.qualifying_position)}`}>
                          {q.qualifying_position ?? '—'}
                        </span>
                        <Link
                          to={`/drivers/${q.driver.id}`}
                          className="self-center font-medium text-white hover:text-red-400 transition truncate"
                        >
                          {fullName(q.driver)}
                          <span className="ml-1.5 text-xs text-zinc-500">{q.driver.driver_code}</span>
                        </Link>
                        <span className="self-center truncate text-sm text-zinc-400">{q.constructor.name}</span>
                        {[q.q1_time, q.q2_time, q.q3_time].map((t, i) => (
                          <span key={i} className="self-center text-right text-xs text-zinc-500 font-mono">
                            {t != null ? t.toFixed(3) : '—'}
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Future Race ───────────────────────────────────────────────────────────────

function FutureRaceView({ race }) {
  const raceDate = new Date(race.race_date)
  const today = new Date()
  const daysUntil = Math.ceil((raceDate - today) / (1000 * 60 * 60 * 24))

  // Build a visual countdown (days / hours)
  const totalHours = Math.max(0, Math.floor((raceDate - today) / (1000 * 60 * 60)))
  const days = Math.floor(totalHours / 24)
  const hours = totalHours % 24

  return (
    <div className="space-y-5">
      {/* Countdown */}
      <div className="glass-panel rounded-xl p-6">
        <p className="card-title mb-4">Race Countdown</p>
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 text-center">
            <p className="font-display text-5xl font-bold text-red-500">{days}</p>
            <p className="mt-1 text-xs uppercase tracking-wider text-zinc-500 font-semibold">Days</p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 text-center">
            <p className="font-display text-5xl font-bold text-white">{hours}</p>
            <p className="mt-1 text-xs uppercase tracking-wider text-zinc-500 font-semibold">Hours</p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5 text-center">
            <p className="font-display text-5xl font-bold text-white">{race.round_number}</p>
            <p className="mt-1 text-xs uppercase tracking-wider text-zinc-500 font-semibold">Round</p>
          </div>
        </div>
        <p className="mt-5 text-center text-sm text-zinc-400">
          Race day: <span className="text-white font-bold">{formatDate(race.race_date)}</span>
        </p>
      </div>

      {/* Circuit info */}
      <div className="glass-panel rounded-xl p-6">
        <p className="card-title mb-4">Circuit</p>
        <div className="flex items-start gap-4">
          
          <div>
            <p className="text-xl font-bold text-white">{race.circuit?.name}</p>
            <p className="text-sm text-zinc-400">{race.circuit?.location}, {race.circuit?.country}</p>
          </div>
        </div>
      </div>

      {/* What to expect */}
      <div className="glass-panel rounded-xl p-6">
        <p className="card-title mb-4">Race details</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
            <p className="text-sm font-semibold text-white">Championship Standings</p>
            <p className="mt-2 text-xs leading-5 text-zinc-400">
              Results will apply to the seasonal standings immediately after the race is completed.
            </p>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
            <p className="text-sm font-semibold text-white">F1 AI Assistant</p>
            <p className="mt-2 text-xs leading-5 text-zinc-400">
              Ask questions about historical races, previous qualifying times, and driver stats at this circuit.
            </p>
            <Link
              to="/analyst"
              className="mt-3 inline-flex items-center rounded border border-red-600/30 bg-red-600/10 px-3 py-1.5 text-xs text-red-400 hover:bg-red-650 transition font-medium cursor-pointer"
            >
              Open Assistant →
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Page shell ────────────────────────────────────────────────────────────────

export function RaceDetailPage() {
  const { raceId } = useParams()
  const [state, setState] = useState({ loading: true, error: null, data: null })

  useEffect(() => {
    let active = true
    setState({ loading: true, error: null, data: null })

    // Fetch race results — if 404 (no results) treat as future race
    getRaceResults(raceId)
      .then(async (raceData) => {
        // Also fetch qualifying
        let qualifying = []
        try {
          const qualData = await getRaceQualifying(raceId)
          qualifying = qualData.results
        } catch {
          // No qualifying data — not a blocking error
        }
        if (active) {
          setState({
            loading: false,
            error: null,
            data: { race: raceData.race, results: raceData.results, qualifying, isFuture: false },
          })
        }
      })
      .catch(async (err) => {
        // If 404 "No race results found" — fetch race info only and render future view
        if (err.message?.includes('No race results') || err.message?.includes('404')) {
          try {
            const { default: api } = await import('../lib/api')
            const resp = await api.get(`/races/${raceId}`)
            if (active) {
              setState({
                loading: false,
                error: null,
                data: { race: resp.data, results: [], qualifying: [], isFuture: true },
              })
            }
          } catch (innerErr) {
            if (active)
              setState({ loading: false, error: innerErr.message || 'Race not found.', data: null })
          }
        } else {
          if (active) setState({ loading: false, error: err.message || 'Failed to load race.', data: null })
        }
      })

    return () => { active = false }
  }, [raceId])

  if (state.loading) return <LoadingState label="Loading race" />
  if (state.error) return <ErrorState message={state.error} />

  const { race, results, qualifying, isFuture } = state.data

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="glass-panel rounded-xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <Link
                to="/races"
                className="text-xs text-zinc-500 hover:text-zinc-300 font-semibold transition"
              >
                ← Races
              </Link>
              <span
                className={`rounded border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                  isFuture
                    ? 'border-red-600/30 bg-red-600/10 text-red-400'
                    : 'border-zinc-800 bg-zinc-900 text-zinc-500'
                }`}
              >
                {isFuture ? 'Upcoming' : 'Completed'}
              </span>
            </div>
            <h1 className="mt-3 text-2xl font-bold text-white tracking-tight sm:text-3xl">{race.race_name}</h1>
            <p className="mt-1 text-xs text-zinc-400">
              Season {race.season} · Round {race.round_number} · {formatDate(race.race_date)}
            </p>
          </div>
          <div className="text-right">
            
            {race.circuit && (
              <p className="mt-1 text-[10px] uppercase font-bold tracking-wider text-zinc-500">{race.circuit.name}</p>
            )}
          </div>
        </div>
      </div>

      {/* Body — past or future */}
      {isFuture ? (
        <FutureRaceView race={race} />
      ) : (
        <PastRaceView race={race} results={results} qualifying={qualifying} />
      )}
    </div>
  )
}
