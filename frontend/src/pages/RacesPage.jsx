import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { GlassCard } from '../components/GlassCard'
import { ErrorState, LoadingState } from '../components/PageState'
import { SeasonSelector } from '../components/SeasonSelector'
import { useAppContext } from '../context/AppContext'
import { formatDate } from '../lib/format'
import { getRacesPage } from '../lib/f1Api'

// Max F1 calendar size — fetch all at once, no pagination needed
const ALL_RACES_LIMIT = 30

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

export function RacesPage() {
  const { season, setSeason } = useAppContext()
  const [state, setState] = useState({ loading: true, error: null, data: null })

  function handleSeasonChange(year) {
    setSeason(year)
  }

  useEffect(() => {
    if (season === null) return

    let active = true
    setState((current) => ({ ...current, loading: true, error: null }))

    // Fetch all races in one shot — no pagination
    getRacesPage(ALL_RACES_LIMIT, 0, season)
      .then((data) => {
        if (active) setState({ loading: false, error: null, data })
      })
      .catch((error) => {
        if (active)
          setState({ loading: false, error: error.message || 'Unable to load races.', data: null })
      })

    return () => { active = false }
  }, [season])

  return (
    <GlassCard eyebrow="Races" title="Race Schedule">
      {/* Season selector */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SeasonSelector value={season} onSeasonChange={handleSeasonChange} />
        {state.data && (
          <p className="text-xs text-white/40">
            {state.data.pagination.total} rounds · Season {season}
          </p>
        )}
      </div>

      {state.loading && <LoadingState label="Loading races" />}
      {state.error && <ErrorState message={state.error} />}

      {state.data && !state.loading && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {state.data.items.map((race) => {
            const isPast = new Date(race.race_date) <= new Date()
            return (
              <Link
                key={race.id}
                to={`/races/${race.id}`}
                className="group relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 transition hover:border-red-600 hover:bg-zinc-900 cursor-pointer"
              >


                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs uppercase tracking-wider text-zinc-500 font-semibold">
                    Round {race.round_number}
                  </p>
                  <div className="flex gap-1.5">
                    <span
                      className={`rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                        isPast
                          ? 'border-zinc-800 bg-zinc-900 text-zinc-500'
                          : 'border-red-600/30 bg-red-600/10 text-red-400'
                      }`}
                    >
                      {isPast ? 'Completed' : 'Upcoming'}
                    </span>
                    <span className="f1-chip text-[10px]">{race.season}</span>
                  </div>
                </div>

                <h3 className="mt-3 text-lg font-bold leading-snug text-white group-hover:text-red-400 transition">
                  {race.race_name}
                </h3>

                {race.circuit && (
                  <div className="mt-3 space-y-0.5">
                    <p className="text-sm text-zinc-300 font-medium">{race.circuit.name}</p>
                    <p className="text-xs text-zinc-500">
                      {race.circuit.location}, {race.circuit.country}
                    </p>
                  </div>
                )}

                <div className="mt-4 flex items-center justify-between">
                  <p className="text-sm font-bold text-red-400">{formatDate(race.race_date)}</p>
                  
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </GlassCard>
  )
}
