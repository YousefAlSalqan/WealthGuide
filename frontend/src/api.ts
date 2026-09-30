import type { Session } from './types'

const SESSION_KEY = 'wealthguide-session-v1'
let session: Session | null = null
try { session = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null') } catch { /* Empty or cleared browser storage. */ }

export function saveSession(value: Session | null) {
  session = value
  if (value) localStorage.setItem(SESSION_KEY, JSON.stringify(value))
  else localStorage.removeItem(SESSION_KEY)
}
export const getSession = () => session

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init, signal: init.signal ?? AbortSignal.timeout(35_000),
    headers: { 'Content-Type': 'application/json', ...(session ? { Authorization: `Bearer ${session.token}` } : {}), ...init.headers },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'The service could not complete this request.' }))
    if (response.status === 401) saveSession(null)
    const message = Array.isArray(error.detail)
      ? error.detail.map((e: { loc: string[]; msg: string }) => `${e.loc.slice(1).join(' › ')}: ${e.msg}`).join('\n')
      : error.detail
    throw new Error(message || 'Something went wrong. Please try again.')
  }
  return response.status === 204 ? undefined as T : response.json()
}

export async function ensureSession(): Promise<Session> {
  if (session) return session
  const created = await api<Session>('/v1/sessions', { method: 'POST' })
  saveSession(created)
  return created
}

export function errorMessage(error: unknown) {
  if (error instanceof Error && (error.name === 'TimeoutError' || error.name === 'AbortError'))
    return 'The request took longer than expected. Retry without changing the form; your request will not be saved twice.'
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}
