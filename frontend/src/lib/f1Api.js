import api from './api'

async function request(path) {
  const response = await api.get(path)
  return response.data
}

export async function getLatestSeason() {
  const data = await request('/seasons/latest')
  return data.season
}

export async function getAllSeasons() {
  const data = await request('/seasons')
  return data.seasons // number[], newest first
}

export async function getDashboardData() {
  const [driverStandings, constructorStandings, latestResults, upcomingRace] = await Promise.all([
    request('/standings/drivers?limit=5'),
    request('/standings/constructors?limit=5'),
    request('/results/latest'),
    api
      .get('/races/upcoming')
      .then((response) => response.data)
      .catch((error) => (error.response?.status === 503 ? null : Promise.reject(error))),
  ])

  return {
    driverStandings,
    constructorStandings,
    latestResults,
    upcomingRace,
  }
}

export async function getDriversPage(limit, offset, season = null) {
  const seasonParam = season ? `&season=${season}` : ''
  return request(`/standings/drivers?limit=${limit}&offset=${offset}${seasonParam}`)
}

export async function getConstructorsPage(limit, offset, season = null) {
  const seasonParam = season ? `&season=${season}` : ''
  return request(`/standings/constructors?limit=${limit}&offset=${offset}${seasonParam}`)
}

export async function getRacesPage(limit, offset, season = null) {
  const seasonParam = season ? `&season=${season}` : ''
  return request(`/races?limit=${limit}&offset=${offset}${seasonParam}`)
}

export async function getDriverDetail(driverId) {
  return request(`/drivers/${driverId}`)
}

export async function getRaceDetail(raceId) {
  return request(`/races/${raceId}`)
}

export async function getRaceResults(raceId) {
  return request(`/races/${raceId}/results`)
}

export async function getRaceQualifying(raceId) {
  return request(`/races/${raceId}/qualifying`)
}

export async function postAnalystQuery(question, history = []) {
  const formattedHistory = history.map(msg => ({
    role: msg.role === 'error' ? 'assistant' : msg.role,
    content: msg.content
  }))
  const response = await api.post('/orchestrator/query', { question, history: formattedHistory })
  return response.data
}
