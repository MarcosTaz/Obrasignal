import React, { useEffect, useState } from 'react'
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native'
import AuthScreen from './AuthScreen'
import BillingGate from './BillingGate'
import { ensureBackendReady } from '../src/api'
import { authSession } from '../src/authSession'
import { storage } from '../src/storage'

function accountScopeFor(state) {
  return state?.status === 'signed-in' ? state?.session?.user?.id || null : null
}

export default function AuthGate({ children }) {
  const [authState, setAuthState] = useState(() => {
    const initial = authSession.getState()
    storage.setAccountScope(accountScopeFor(initial))
    return initial
  })

  useEffect(() => {
    let active = true
    const update = (nextState) => {
      if (!active) return
      // Bind local customer cache/profile/settings only to an ordinary signed-in
      // subject. A provider password-recovery session has no application/cache authority.
      storage.setAccountScope(accountScopeFor(nextState))
      setAuthState(nextState)
      if (nextState.status === 'signed-in') ensureBackendReady().catch(() => {})
    }
    const unsubscribe = authSession.subscribe(update)
    authSession.start().then(update)
    return () => { active = false; unsubscribe() }
  }, [])

  if (authState.status === 'loading') {
    return <View style={styles.loading}><Text style={styles.brand}>OBRA<Text style={styles.blue}>SIGNAL</Text></Text><ActivityIndicator size="small" color="#5E8BFF" /><Text style={styles.message}>A recuperar a sessão…</Text></View>
  }

  if (authState.status === 'password-recovery') {
    return <AuthScreen recoverySession={authState.session} />
  }

  if (authState.status !== 'signed-in') return <AuthScreen />

  // Hard rule: once Supabase has authenticated the user through an ordinary
  // sign-in, the application shell opens immediately. Recovery sessions are
  // intentionally intercepted above and cannot enter the product shell.
  return <BillingGate>{children}</BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, backgroundColor: '#070C18' },
  brand: { fontSize: 25, fontWeight: '900', color: '#F3F6FF' },
  blue: { color: '#5E8BFF' },
  message: { color: '#9BA8C0', fontSize: 12 },
})
