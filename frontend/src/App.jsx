import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppProvider } from './context/AppContext'
import { AppLayout } from './components/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { DriversPage } from './pages/DriversPage'
import { DriverDetailPage } from './pages/DriverDetailPage'
import { ConstructorsPage } from './pages/ConstructorsPage'
import { RacesPage } from './pages/RacesPage'
import { RaceDetailPage } from './pages/RaceDetailPage'
import { AnalystPage } from './pages/AnalystPage'

function Shell() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/drivers" element={<DriversPage />} />
            <Route path="/drivers/:driverId" element={<DriverDetailPage />} />
            <Route path="/constructors" element={<ConstructorsPage />} />
            <Route path="/races" element={<RacesPage />} />
            <Route path="/races/:raceId" element={<RaceDetailPage />} />
            <Route path="/analyst" element={<AnalystPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  )
}

export default Shell
