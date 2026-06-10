export function LoadingState({ label = 'Loading data' }) {
  return (
    <div className="glass-panel rounded-[1.5rem] p-6 text-white/70">
      <div className="flex items-center gap-3">
        <span className="h-3 w-3 animate-pulse rounded-full bg-red-500" />
        <p className="text-sm font-medium uppercase tracking-[0.3em]">{label}</p>
      </div>
    </div>
  )
}

export function ErrorState({ message }) {
  return (
    <div className="glass-panel rounded-[1.5rem] border-red-400/30 bg-red-500/10 p-6 text-white">
      <p className="text-sm font-semibold uppercase tracking-[0.3em] text-red-200">Unable to load</p>
      <p className="mt-2 text-sm text-white/75">{message}</p>
    </div>
  )
}
