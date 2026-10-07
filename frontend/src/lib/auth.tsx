import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

const KEY = 'air.admin'

interface Stored { token: string; expires_at: string }

export function readToken(): string | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const s = JSON.parse(raw) as Stored
    if (new Date(s.expires_at).getTime() <= Date.now()) {
      localStorage.removeItem(KEY)
      return null
    }
    return s.token
  } catch {
    return null
  }
}

interface AuthState { isAdmin: boolean; signIn: (s: Stored) => void; signOut: () => void }
const Ctx = createContext<AuthState>({ isAdmin: false, signIn: () => {}, signOut: () => {} })

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAdmin, setIsAdmin] = useState(() => readToken() != null)

  const signIn = useCallback((s: Stored) => {
    try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* storage unavailable: session only */ }
    setIsAdmin(true)
  }, [])
  const signOut = useCallback(() => {
    try { localStorage.removeItem(KEY) } catch { /* ignore */ }
    setIsAdmin(false)
  }, [])

  useEffect(() => {
    const onExpired = () => signOut()
    window.addEventListener('air:auth-expired', onExpired)
    return () => window.removeEventListener('air:auth-expired', onExpired)
  }, [signOut])

  const value = useMemo(() => ({ isAdmin, signIn, signOut }), [isAdmin, signIn, signOut])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
