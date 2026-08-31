import React, { useEffect, useState } from 'react'
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native'
import AuthScreen from './AuthScreen'
import BillingGate from './BillingGate'
import { ensureBackendReady } from '../src/api'
import { authSession } from '../src/authSession'
import { storage } from '../src/storage'

export default function AuthGate({ children }) {
  const [authState, setAuthState] = useState(authSession.getState())
  const [privateReady, setPrivateReady] = useState(false)
  const [privateError, setPrivateError] = useState('')

  useEffect(() => {
    let active = true
    let generation = 0

    const update = async (nextState) => {
      if (!active) return
      const current = ++generation
      setPrivateReady(false)
      setPrivateError('')
      try {
        const identity = nextState.status === 'signed-in' ? nextState.session?.user?.id : null
        if (nextState.status === 'signed-in' && !identity) throw new Error('authenticated user identity unavailable')
        await storage.bindPrivateTenant(identity)
        if (!active || current !== generation) return
        setAuthState(nextState)
        setPrivateReady(true)
        if (nextState.status === 'signed-in') ensureBackendReady().catch(() => {})
      } catch (_) {
        if (!active || current !== generation) return
        setAuthState(nextState)
        setPrivateError('Não foi possível preparar o armazenamento privado desta conta.')
      }
    }

    const unsubscribe = authSession.subscribe(update)
    authSession.start().then(update)
    return () => { active = false; generation += 1; unsubscribe() }
  }, [])

  if (privateError) {
    return <View style={styles.loading}><Text style={styles.brand}>OBRA<Text style={styles.blue}>SIGNAL</Text></Text><Text style={styles.error}>{privateError}</Text><Text style={styles.message}>A área autenticada permanece bloqueada para impedir mistura de dados entre contas.</Text></View>
  }

  if (authState.status === 'loading' || (authState.status === 'signed-in' && !privateReady)) {
    return <View style={styles.loading}><Text style={styles.brand}>OBRA<Text style={styles.blue}>SIGNAL</Text></Text><ActivityIndicator size="small" color="#5E8BFF" /><Text style={styles.message}>A preparar a sessão privada…</Text></View>
  }

  if (authState.status !== 'signed-in') return <AuthScreen />

  return <BillingGate>{children}</BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, padding: 28, backgroundColor: '#070C18' },
  brand: { fontSize: 25, fontWeight: '900', color: '#F3F6FF' },
  blue: { color: '#5E8BFF' },
  message: { color: '#9BA8C0', fontSize: 12, textAlign: 'center', maxWidth: 420 },
  error: { color: '#ff8998', fontSize: 14, fontWeight: '700', textAlign: 'center', maxWidth: 420 },
})
