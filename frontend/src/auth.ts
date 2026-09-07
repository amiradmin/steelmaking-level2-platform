export type OperatorProfile = {
  username: string
  display_name: string
  is_staff: boolean
}

type TokenPair = {
  access: string
  refresh: string
}

type StoredTokens = TokenPair & {
  remember: boolean
}

const TOKEN_KEY = 'level2-auth-tokens'

export class AuthenticationExpiredError extends Error {
  constructor() {
    super('Authentication expired')
    this.name = 'AuthenticationExpiredError'
  }
}

function parseStoredTokens(raw: string | null, remember: boolean): StoredTokens | null {
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as Partial<TokenPair>
    if (typeof value.access !== 'string' || typeof value.refresh !== 'string') return null
    return { access: value.access, refresh: value.refresh, remember }
  } catch {
    return null
  }
}

export function loadTokens(): StoredTokens | null {
  return parseStoredTokens(sessionStorage.getItem(TOKEN_KEY), false)
    ?? parseStoredTokens(localStorage.getItem(TOKEN_KEY), true)
}

function saveTokens(tokens: TokenPair, remember: boolean) {
  const storage = remember ? localStorage : sessionStorage
  const otherStorage = remember ? sessionStorage : localStorage
  otherStorage.removeItem(TOKEN_KEY)
  storage.setItem(TOKEN_KEY, JSON.stringify(tokens))
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_KEY)
}

async function responseBody(response: Response): Promise<Record<string, unknown>> {
  try {
    return await response.json() as Record<string, unknown>
  } catch {
    return {}
  }
}

export async function login(username: string, password: string, remember: boolean): Promise<OperatorProfile> {
  const response = await fetch('/api/v1/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const body = await responseBody(response)
  if (!response.ok || typeof body.access !== 'string' || typeof body.refresh !== 'string') {
    throw new Error(response.status === 401
      ? 'کد کاربری یا رمز عبور صحیح نیست.'
      : 'سرویس احراز هویت در دسترس نیست؛ دوباره تلاش کنید.')
  }

  saveTokens({ access: body.access, refresh: body.refresh }, remember)
  try {
    const profileResponse = await authorizedFetch('/api/v1/auth/me')
    if (!profileResponse.ok) throw new Error('Profile unavailable')
    return await profileResponse.json() as OperatorProfile
  } catch (error) {
    clearTokens()
    throw error
  }
}

async function refreshAccessToken(tokens: StoredTokens): Promise<string> {
  const response = await fetch('/api/v1/auth/token/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
  const body = await responseBody(response)
  if (!response.ok || typeof body.access !== 'string') {
    clearTokens()
    throw new AuthenticationExpiredError()
  }
  saveTokens({ access: body.access, refresh: tokens.refresh }, tokens.remember)
  return body.access
}

function withBearer(init: RequestInit, accessToken: string): RequestInit {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${accessToken}`)
  return { ...init, headers }
}

export async function authorizedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const tokens = loadTokens()
  if (!tokens) throw new AuthenticationExpiredError()

  let response = await fetch(input, withBearer(init, tokens.access))
  if (response.status !== 401) return response

  const accessToken = await refreshAccessToken(tokens)
  response = await fetch(input, withBearer(init, accessToken))
  if (response.status === 401) {
    clearTokens()
    throw new AuthenticationExpiredError()
  }
  return response
}
