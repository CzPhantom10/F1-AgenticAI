import { useEffect, useState } from 'react'

import { GlassCard } from '../components/GlassCard'
import { ErrorState, LoadingState } from '../components/PageState'
import { SeasonSelector } from '../components/SeasonSelector'
import { useAppContext } from '../context/AppContext'
import { formatPoints } from '../lib/format'
import { getConstructorsPage } from '../lib/f1Api'

const ALL_CONSTRUCTORS_LIMIT = 50

export function ConstructorsPage() {
  const { season, setSeason } = useAppContext()
  const [state, setState] = useState({ loading: true, error: null, data: null })

  function handleSeasonChange(year) {
    setSeason(year)
  }

  useEffect(() => {
    if (season === null) return

    let active = true
    setState((current) => ({ ...current, loading: true, error: null }))

    getConstructorsPage(ALL_CONSTRUCTORS_LIMIT, 0, season)
      .then((data) => {
        if (active) setState({ loading: false, error: null, data })
      })
      .catch((error) => {
        if (active)
          setState({
            loading: false,
            error: error.message || 'Unable to load constructor standings.',
            data: null,
          })
      })

    return () => {
      active = false
    }
  }, [season])

  return (
    <GlassCard eyebrow="Constructors" title="Constructor Standings">
      {/* Season selector */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SeasonSelector value={season} onSeasonChange={handleSeasonChange} />
        {state.data && (
          <p className="text-xs text-white/40">
            {state.data.pagination.total} constructors · Season {season} (data from 2018 to present)
          </p>
        )}
      </div>

      {state.loading && <LoadingState label="Loading constructors" />}
      {state.error && <ErrorState message={state.error} />}

      {state.data && !state.loading && (
        <div className="overflow-x-auto rounded-2xl border border-white/10">
          <div className="min-w-[520px]">
            {/* Header */}
            <div className="grid grid-cols-[60px_1.6fr_1fr_80px_80px_90px] gap-2 border-b border-white/10 bg-black/20 px-4 py-3 text-xs uppercase tracking-[0.3em] text-white/45">
              <span>Pos</span>
              <span>Constructor</span>
              <span>Nationality</span>
              <span className="text-center">Wins</span>
              <span className="text-center">Podiums</span>
              <span className="text-right">Points</span>
            </div>

            {/* Rows */}
            <div className="divide-y divide-white/8 bg-white/3">
              {state.data.items.map((entry) => {
                const isTopTeam = ["Red Bull", "Red Bull Racing", "Ferrari", "Mercedes", "McLaren"].some(name => entry.constructor.name.includes(name));
                return (
                  <div
                    key={entry.constructor.id}
                    className={`grid grid-cols-[60px_1.6fr_1fr_80px_80px_90px] gap-2 px-4 py-4 transition ${
                      isTopTeam ? 'bg-red-500/5 hover:bg-red-500/10' : 'hover:bg-white/5'
                    }`}
                  >
                    <div
                      className={`font-display text-2xl font-bold ${
                        entry.position === 1
                          ? 'text-yellow-300'
                          : entry.position === 2
                          ? 'text-slate-300'
                          : entry.position === 3
                          ? 'text-amber-600'
                          : 'text-white/60'
                      }`}
                    >
                      {entry.position}
                    </div>
                    <div className="self-center">
                      <p className="font-semibold text-white">{entry.constructor.name}</p>
                    </div>
                    <p className="self-center text-sm text-white/60">{entry.constructor.nationality}</p>
                    <p className="self-center text-center text-sm text-white/70">{entry.wins}</p>
                    <p className="self-center text-center text-sm text-white/70">{entry.podiums}</p>
                    <p className="self-center text-right font-display text-xl font-bold text-red-200">
                      {formatPoints(entry.points)}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </GlassCard>
  )
}
