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
      <span className="text-xs uppercase tracking-wider text-zinc-500 font-semibold hidden sm:block">Season</span>
      <div className="flex flex-wrap gap-1.5">
        {seasons.map((year) => (
          <button
            key={year}
            type="button"
            onClick={() => onSeasonChange(year)}
            className={[
              'rounded border px-3 py-1.5 text-xs font-semibold transition cursor-pointer',
              value === year
                ? 'border-red-600 bg-red-600/10 text-red-500'
                : 'border-zinc-800 bg-zinc-900 text-zinc-400 hover:border-zinc-700 hover:text-white',
            ].join(' ')}
          >
            {year}
          </button>
        ))}
      </div>
    </div>
  )
}
