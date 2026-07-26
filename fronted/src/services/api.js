/**
 * src/services/api.js
 *
 * Single source of truth for every HTTP call the frontend makes. Contains:
 *   1. A configured Axios instance with JWT attach + silent refresh.
 *   2. One grouped export per backend domain, mirroring api/urls.py 1:1.
 *
 * Usage:
 *   import { authApi, consolesApi, gamingSessionsApi } from '@/services/api'
 *   const { data } = await gamingSessionsApi.start({ console_id, walk_in_name })
 */
import axios from 'axios'

// ---------------------------------------------------------------------------
// Base client
// ---------------------------------------------------------------------------
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

const ACCESS_TOKEN_KEY = 'll_access_token'
const REFRESH_TOKEN_KEY = 'll_refresh_token'

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  set: (access, refresh) => {
    if (access) localStorage.setItem(ACCESS_TOKEN_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

client.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Silent-refresh queue so concurrent 401s only trigger one refresh call.
let isRefreshing = false
let pendingQueue = []

function resolveQueue(error, token = null) {
  pendingQueue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token)))
  pendingQueue = []
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status

    if (status === 401 && !originalRequest._retry && tokenStore.getRefresh()) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return client(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true
      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh/`, {
          refresh: tokenStore.getRefresh(),
        })
        const newAccess = data.access
        tokenStore.set(newAccess, null)
        resolveQueue(null, newAccess)
        originalRequest.headers.Authorization = `Bearer ${newAccess}`
        return client(originalRequest)
      } catch (refreshError) {
        resolveQueue(refreshError, null)
        tokenStore.clear()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// Unwraps the backend's standard envelope: { success, message, data, errors }
const unwrap = (promise) => promise.then((res) => res.data)

// Generic CRUD factory so every resource below stays a one-liner.
function crudResource(basePath) {
  return {
    list: (params) => unwrap(client.get(`${basePath}/`, { params })),
    retrieve: (id) => unwrap(client.get(`${basePath}/${id}/`)),
    create: (payload) => unwrap(client.post(`${basePath}/`, payload)),
    update: (id, payload) => unwrap(client.put(`${basePath}/${id}/`, payload)),
    partialUpdate: (id, payload) => unwrap(client.patch(`${basePath}/${id}/`, payload)),
    remove: (id) => unwrap(client.delete(`${basePath}/${id}/`)),
  }
}

// ===========================================================================
// AUTH
// ===========================================================================
export const authApi = {
  login: (username, password) => unwrap(client.post('/auth/login/', { username, password })),
  refresh: (refresh) => unwrap(client.post('/auth/refresh/', { refresh })),
  logout: () => unwrap(client.post('/auth/logout/', { refresh: tokenStore.getRefresh() })),
  me: () => unwrap(client.get('/auth/me/')),
  updateProfile: (payload) => unwrap(client.patch('/auth/me/', payload)),
  changePassword: (old_password, new_password) =>
    unwrap(client.post('/auth/change-password/', { old_password, new_password })),
}

// ===========================================================================
// USERS
// ===========================================================================
export const usersApi = crudResource('/users')

// ===========================================================================
// CUSTOMERS & WALK-INS
// ===========================================================================
export const customersApi = crudResource('/customers')

export const walkInCustomersApi = {
  ...crudResource('/walk-in-customers'),
  convert: (payload) => unwrap(client.post('/walk-in-customers/convert/', payload)),
}

// ===========================================================================
// CONSOLES, GAMES, PROMOTIONS
// ===========================================================================
export const consolesApi = crudResource('/consoles')
export const gamesApi = crudResource('/games')
export const promotionsApi = crudResource('/promotions')

// ===========================================================================
// GAMING SESSIONS & BOOKINGS
// ===========================================================================
export const gamingSessionsApi = {
  ...crudResource('/gaming-sessions'),
  start: (payload) => unwrap(client.post('/gaming-sessions/start/', payload)),
  stop: (id) => unwrap(client.post(`/gaming-sessions/${id}/stop/`)),
  previewCharges: (id) => unwrap(client.get(`/gaming-sessions/${id}/preview_charges/`)),
}

export const bookingsApi = crudResource('/bookings')

// ===========================================================================
// INVENTORY
// ===========================================================================
export const inventoryCategoriesApi = crudResource('/inventory-categories')
export const suppliersApi = crudResource('/suppliers')

export const inventoryItemsApi = {
  ...crudResource('/inventory-items'),
  adjustStock: (payload) => unwrap(client.post('/inventory-items/adjust_stock/', payload)),
}

export const stockMovementsApi = crudResource('/stock-movements')

// ===========================================================================
// SALES, PAYMENTS, EXPENSES
// ===========================================================================
export const salesApi = crudResource('/sales')
export const paymentsApi = crudResource('/payments')
export const expenseCategoriesApi = crudResource('/expense-categories')
export const expensesApi = crudResource('/expenses')

// ===========================================================================
// TOURNAMENTS & FUTURE BETTING PLATFORM
// ===========================================================================
export const tournamentsApi = {
  ...crudResource('/tournaments'),
  registerParticipant: (payload) => unwrap(client.post('/tournaments/register_participant/', payload)),
}

export const tournamentMatchesApi = crudResource('/tournament-matches')
export const walletsApi = crudResource('/wallets')
export const walletTransactionsApi = crudResource('/wallet-transactions')

export const bettingMarketsApi = {
  ...crudResource('/betting-markets'),
  settle: (id, winning_participant_id) =>
    unwrap(client.post(`/betting-markets/${id}/settle/`, { winning_participant_id })),
}

export const betsApi = crudResource('/bets')

// ===========================================================================
// NOTIFICATIONS, SETTINGS, AUDIT LOGS
// ===========================================================================
export const notificationsApi = {
  ...crudResource('/notifications'),
  markRead: (id) => unwrap(client.post(`/notifications/${id}/mark_read/`)),
  markAllRead: () => unwrap(client.post('/notifications/mark_all_read/')),
}

export const settingsApi = {
  list: () => unwrap(client.get('/settings/')),
  retrieve: (key) => unwrap(client.get(`/settings/${key}/`)),
  update: (key, payload) => unwrap(client.put(`/settings/${key}/`, payload)),
}

export const auditLogsApi = crudResource('/audit-logs')

// ===========================================================================
// DASHBOARD & REPORTS
// ===========================================================================
export const dashboardApi = {
  summary: () => unwrap(client.get('/dashboard/summary/')),
}

export const reportsApi = {
  revenue: (params) => unwrap(client.get('/reports/revenue/', { params })),
  consoleUtilization: (params) => unwrap(client.get('/reports/console-utilization/', { params })),
  bestSellingProducts: (params) => unwrap(client.get('/reports/best-selling-products/', { params })),
  mostPlayedGames: (params) => unwrap(client.get('/reports/most-played-games/', { params })),
}

export default client