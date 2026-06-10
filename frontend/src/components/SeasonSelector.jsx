import { useEffect, useState } from 'react'
import { getAllSeasons } from '../lib/f1Api'

/**
 * Reusable season selector pill bar.
 * Fetches available seasons from the DB on mount.
 * Calls onSeasonChange(year) when a new season is picked.
 */
export function SeasonSelector({ value, onSeasonChange }) {
  const [seasons, setSeasons] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAllSeasons()
      .then((s) => {
        setSeasons(s)
        // Auto-select the latest if nothing is selected yet
        if (!value && s.length > 0) {
          onSeasonChange(s[0])
        }
      })
      .catch(() => {
        // Silently ignore — pages still work without the selector
      })
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading || seasons.length === 0) return null

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase tracking-[0.3em] text-white/40 hidden sm:block">Season</span>
      <div className="flex flex-wrap gap-1.5">
        {seasons.map((year) => (
          <button
            key={year}
            type="button"
            onClick={() => onSeasonChange(year)}
            className={[
              'rounded-full border px-3 py-1 text-xs font-semibold transition',
              value === year
                ? 'border-red-400/60 bg-red-500/20 text-red-100 shadow-sm shadow-red-500/20'
                : 'border-white/10 bg-white/5 text-white/60 hover:border-white/25 hover:text-white',
            ].join(' ')}
          >
            {year}
          </button>
        ))}
      </div>
    </div>
  )
}
