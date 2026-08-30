import React, { useEffect, useState } from 'react'
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native'
import AuthScreen from './AuthScreen'
import PasswordRecoveryScreen from './PasswordRecoveryScreen'
import BillingGate from './BillingGate'
import AccountPrivacyControls from './AccountPrivacyControls'
import { ensureBackendReady } from '../src/api'
import { authSession } from '../src/authSession'
import { storage } from '../src/storage'

export default function AuthGate({ children }) {
  const [authState, setAuthState] = useState(authSession.getState())
  const [tenantStatus, setTenantStatus] = useState('loading')

  useEffect(() => {
    let active = true
    let generation = 0
    let bindingQueue = Promise.resolve()

    const update = (nextState) => {
      if (!active) return
      const currentGeneration = ++generation

      // Account transitions immediately unmount the authenticated shell. The
      // next account cannot hydrate anything until its private store is bound.
      setTenantStatus('loading')

      bindingQueue = bindingQueue
        .catch(() => {})
        .then(async () => {
          const signedIn = nextState.status === 'signed-in'
          const accountId = signedIn ? nextState.session?.user?.id : null
          if (signedIn && !accountId) throw new Error('Authenticated session is missing user.id')

          await storage.bindPrivateTenant(accountId)
          if (!active || currentGeneration !== generation) return

          setAuthState(nextState)
          setTenantStatus('ready')
          if (nextState.status === 'signed-in' && nextState.event !== 'PASSWORD_RECOVERY') ensureBackendReady().catch(() => {})
        })
        .catch(() => {
          if (!active || currentGeneration !== generation) return
          // A signed-out state is safe even if physical deletion failed: the
          // in-memory tenant binding was already cleared and no private store
          // can be read. Signed-in hydration fails closed.
          if (nextState.status !== 'signed-in') {
            setAuthState(nextState)
            setTenantStatus('ready')
            return
          }
          setTenantStatus('error')
        })
    }

    const unsubscribe = authSession.subscribe(update)
    authSession.start().then(update).catch(() => update({ status: 'signed-out', session: null, event: null }))
    return () => { active = false; generation += 1; unsubscribe() }
  }, [])

  if (authState.status === 'loading' || tenantStatus === 'loading') {
    return <View style={styles.loading}><Text style={styles.brand}>OBRA<Text style={styles.blue}>SIGNAL</Text></Text><ActivityIndicator size="small" color="#5E8BFF" /><Text style={styles.message}>A recuperar a sessão…</Text></View>
  }

  if (tenantStatus === 'error') {
    return <View style={styles.loading}><Text style={styles.brand}>OBRA<Text style={styles.blue}>SIGNAL</Text></Text><Text style={styles.error}>Não foi possível validar o armazenamento privado desta sessão.</Text></View>
  }

  if (authState.status !== 'signed-in') return <AuthScreen />
  if (authState.event === 'PASSWORD_RECOVERY') return <PasswordRecoveryScreen />

  // Privacy rights remain reachable for every authenticated identity, including
  // evaluation/expired billing states. Billing may gate paid product access, but
  // it must never gate account export, deletion status or deletion requests.
  const accountId = authState.session?.user?.id
  return <AccountPrivacyControls key={`privacy:${accountId}`}>
    <BillingGate key={accountId}>{children}</BillingGate>
  </AccountPrivacyControls>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, backgroundColor: '#070C18' },
  brand: { fontSize: 25, fontWeight: '900', color: '#F3F6FF' },
  blue: { color: '#5E8BFF' },
  message: { color: '#9BA8C0', fontSize: 12 },
  error: { color: '#FF8998', fontSize: 12, textAlign: 'center', paddingHorizontal: 24 },
})
