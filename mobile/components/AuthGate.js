import React, { useEffect, useState } from 'react'
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native'
import AuthScreen from './AuthScreen'
import BillingGate from './BillingGate'
import { ensureBackendReady } from '../src/api'
import { authSession } from '../src/authSession'

export default function AuthGate({ children }) {
  const [authState, setAuthState] = useState(authSession.getState())


  useEffect(() => {
    let active = true
    const update = (nextState) => {
      if (!active) return
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

  if (authState.status !== 'signed-in') return <AuthScreen />

  // Hard rule: once Supabase has authenticated the user, the application
  // shell opens immediately. Profile, billing and API availability are
  // background concerns and cannot gate the first authenticated render.
  return <BillingGate>{children}</BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, backgroundColor: '#070C18' },
  brand: { fontSize: 25, fontWeight: '900', color: '#F3F6FF' },
  blue: { color: '#5E8BFF' },
  message: { color: '#9BA8C0', fontSize: 12 },
})
