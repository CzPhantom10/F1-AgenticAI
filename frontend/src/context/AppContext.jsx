import { createContext, useContext, useMemo, useState } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  // null = not resolved yet; pages auto-select the latest via SeasonSelector
  const [season, setSeason] = useState(null)

  const value = useMemo(
    () => ({
      season,
      setSeason,
    }),
    [season],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useAppContext() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider')
  }

  return context
}

