import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  timeout: 60000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg ?? item).join(', ')
          : error.message || 'Request failed'

    return Promise.reject(new Error(message))
  },
)

export default api