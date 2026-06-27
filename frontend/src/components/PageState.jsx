export function LoadingState({ label = 'Loading data' }) {
  return (
    <div className="border border-zinc-800 bg-zinc-900 rounded-xl p-6 text-zinc-300">
      <div className="flex items-center gap-3">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-600" />
        <p className="text-xs font-semibold uppercase tracking-wider">{label}</p>
      </div>
    </div>
  )
}

export function ErrorState({ message }) {
  return (
    <div className="border border-red-900/45 bg-zinc-900 rounded-xl p-6 text-zinc-100">
      <p className="text-xs font-bold uppercase tracking-wider text-red-500">Error</p>
      <p className="mt-2 text-sm text-zinc-400">{message}</p>
    </div>
  )
}
