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
  if (!country) return '🏁'
  for (const [key, flag] of Object.entries(COUNTRY_FLAGS)) {
    if (country.toLowerCase().includes(key.toLowerCase())) return flag
  }
  return '🏁'
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
      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
        isFinished
          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
          : 'border-red-500/30 bg-red-500/10 text-red-300'
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
  const medals = ['🥇', '🥈', '🥉']

  return (
    <div className="space-y-5">
      {/* Podium */}
      <div className="glass-panel rounded-[1.5rem] p-6">
        <p className="card-title mb-4">Podium</p>
        <div className="grid gap-4 sm:grid-cols-3">
          {podium.map((r, i) => (
            <div
              key={r.id}
              className={`relative overflow-hidden rounded-2xl border p-5 text-center ${
                i === 0
                  ? 'border-yellow-400/30 bg-yellow-400/5'
                  : i === 1
                  ? 'border-slate-400/30 bg-slate-400/5'
                  : 'border-amber-500/30 bg-amber-500/5'
              }`}
            >
              <p className="text-3xl">{medals[i]}</p>
              <Link
                to={`/drivers/${r.driver.id}`}
                className="mt-3 block text-lg font-bold text-white hover:text-red-200 transition"
              >
                {fullName(r.driver)}
              </Link>
              <p className="text-xs text-white/50">{r.constructor.name}</p>
              <p className="mt-3 font-display text-3xl font-bold text-red-200">
                {formatPoints(r.points)}
                <span className="ml-1 text-sm font-normal text-red-300/60">pts</span>
              </p>
              <p className="mt-1 text-xs text-white/40">Grid P{r.grid_position ?? '?'}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="glass-panel rounded-[1.5rem] p-6">
        <div className="mb-5 flex gap-2">
          {['race', 'qualifying'].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                tab === t
                  ? 'border-red-400/50 bg-red-500/15 text-white'
                  : 'border-white/10 bg-white/5 text-white/55 hover:text-white'
              }`}
            >
              {t === 'race' ? '🏁 Race Results' : '⏱ Qualifying'}
            </button>
          ))}
        </div>

        {tab === 'race' && (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <div className="min-w-[560px]">
              <div className="grid grid-cols-[52px_1.8fr_1.2fr_80px_80px_90px] gap-2 border-b border-white/10 bg-black/20 px-4 py-3 text-xs uppercase tracking-[0.3em] text-white/40">
                <span>Pos</span>
                <span>Driver</span>
                <span>Team</span>
                <span className="text-center">Grid</span>
                <span className="text-right">Points</span>
                <span className="text-right">Status</span>
              </div>
              <div className="divide-y divide-white/8">
                {results.map((r) => (
                  <div
                    key={r.id}
                    className="grid grid-cols-[52px_1.8fr_1.2fr_80px_80px_90px] gap-2 px-4 py-3 transition hover:bg-white/3"
                  >
                    <span className={`font-display text-xl font-bold ${positionColor(r.finish_position)}`}>
                      {r.finish_position ?? '—'}
                    </span>
                    <Link
                      to={`/drivers/${r.driver.id}`}
                      className="self-center font-medium text-white hover:text-red-200 transition truncate"
                    >
                      {fullName(r.driver)}
                      <span className="ml-1.5 text-xs text-white/40">{r.driver.driver_code}</span>
                    </Link>
                    <span className="self-center truncate text-sm text-white/55">{r.constructor.name}</span>
                    <span className="self-center text-center text-sm text-white/50">
                      {r.grid_position ?? '—'}
                    </span>
                    <span className="self-center text-right font-display text-base font-bold text-red-200">
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
              <div className="rounded-2xl border border-dashed border-white/15 bg-white/3 p-8 text-center text-sm text-white/40">
                No qualifying data available for this race.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-white/10">
                <div className="min-w-[460px]">
                  <div className="grid grid-cols-[52px_1.8fr_1.2fr_90px_90px_90px] gap-2 border-b border-white/10 bg-black/20 px-4 py-3 text-xs uppercase tracking-[0.3em] text-white/40">
                    <span>Pos</span>
                    <span>Driver</span>
                    <span>Team</span>
                    <span className="text-right">Q1</span>
                    <span className="text-right">Q2</span>
                    <span className="text-right">Q3</span>
                  </div>
                  <div className="divide-y divide-white/8">
                    {qualifying.map((q) => (
                      <div
                        key={q.id}
                        className="grid grid-cols-[52px_1.8fr_1.2fr_90px_90px_90px] gap-2 px-4 py-3 hover:bg-white/3"
                      >
                        <span className={`font-display text-xl font-bold ${positionColor(q.qualifying_position)}`}>
                          {q.qualifying_position ?? '—'}
                        </span>
                        <Link
                          to={`/drivers/${q.driver.id}`}
                          className="self-center font-medium text-white hover:text-red-200 transition truncate"
                        >
                          {fullName(q.driver)}
                          <span className="ml-1.5 text-xs text-white/40">{q.driver.driver_code}</span>
                        </Link>
                        <span className="self-center truncate text-sm text-white/55">{q.constructor.name}</span>
                        {[q.q1_time, q.q2_time, q.q3_time].map((t, i) => (
                          <span key={i} className="self-center text-right text-xs text-white/50 font-mono">
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
      <div className="glass-panel rounded-[1.5rem] p-6">
        <p className="card-title mb-4">Race Countdown</p>
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-2xl border border-red-500/25 bg-red-500/10 p-5 text-center">
            <p className="font-display text-5xl font-bold text-red-100">{days}</p>
            <p className="mt-1 text-xs uppercase tracking-[0.3em] text-red-300/60">Days</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-center">
            <p className="font-display text-5xl font-bold text-white">{hours}</p>
            <p className="mt-1 text-xs uppercase tracking-[0.3em] text-white/40">Hours</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-center">
            <p className="font-display text-5xl font-bold text-white">{race.round_number}</p>
            <p className="mt-1 text-xs uppercase tracking-[0.3em] text-white/40">Round</p>
          </div>
        </div>
        <p className="mt-5 text-center text-sm text-white/50">
          Race day: <span className="text-white font-semibold">{formatDate(race.race_date)}</span>
        </p>
      </div>

      {/* Circuit info */}
      <div className="glass-panel rounded-[1.5rem] p-6">
        <p className="card-title mb-4">Circuit</p>
        <div className="flex items-start gap-4">
          <span className="text-5xl">{flagFor(race.circuit?.country)}</span>
          <div>
            <p className="text-xl font-bold text-white">{race.circuit?.name}</p>
            <p className="text-sm text-white/55">{race.circuit?.location}, {race.circuit?.country}</p>
          </div>
        </div>
      </div>

      {/* What to expect */}
      <div className="glass-panel rounded-[1.5rem] p-6">
        <p className="card-title mb-4">What to expect</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <p className="text-sm font-semibold text-white/80">🏆 Championship Impact</p>
            <p className="mt-2 text-xs leading-5 text-white/50">
              With {daysUntil} days until race day, every point will count. Track how the standings
              shift round-by-round.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <p className="text-sm font-semibold text-white/80">📊 Head to the Analyst</p>
            <p className="mt-2 text-xs leading-5 text-white/50">
              Ask Racecraft AI anything about past races at this circuit or driver form coming into
              this round.
            </p>
            <Link
              to="/analyst"
              className="mt-3 inline-flex items-center rounded-full border border-red-400/30 bg-red-500/10 px-3 py-1.5 text-xs text-red-200 transition hover:bg-red-500/20"
            >
              Open Analyst →
            </Link>
          </div>
          <div className="rounded-2xl border border-dashed border-white/15 bg-white/3 p-4 sm:col-span-2">
            <p className="text-xs uppercase tracking-[0.3em] text-white/35">Predictions — Coming in Memory Agent v2</p>
            <p className="mt-2 text-xs text-white/30">
              ML-powered podium predictions and qualifying grid estimates will appear here once the
              prediction engine is live.
            </p>
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
      <div className="glass-panel rounded-[1.5rem] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <Link
                to="/races"
                className="text-xs text-white/40 hover:text-white/70 transition"
              >
                ← Races
              </Link>
              <span
                className={`f1-chip ${isFuture ? 'border-blue-400/30 bg-blue-500/10 text-blue-200' : ''}`}
              >
                {isFuture ? '⏳ Upcoming' : '🏁 Completed'}
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-bold text-white sm:text-4xl">{race.race_name}</h1>
            <p className="mt-1 text-sm text-white/55">
              Season {race.season} · Round {race.round_number} · {formatDate(race.race_date)}
            </p>
          </div>
          <div className="text-right">
            <span className="text-6xl">{flagFor(race.circuit?.country)}</span>
            {race.circuit && (
              <p className="mt-1 text-xs text-white/40">{race.circuit.name}</p>
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
