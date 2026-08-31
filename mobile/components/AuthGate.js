import React, { useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from 'react-native'
import AuthScreen from './AuthScreen'
import BillingGate from './BillingGate'
import { ensureBackendReady } from '../src/api'
import { authSession } from '../src/authSession'
import { supabase } from '../lib/supabase'

function WebSessionBar() {
  const [now, setNow] = useState(() => new Date())
  const [signingOut, setSigningOut] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const date = useMemo(() => new Intl.DateTimeFormat('pt-PT', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(now), [now.getFullYear(), now.getMonth(), now.getDate()])

  const time = new Intl.DateTimeFormat('pt-PT', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(now)

  const signOut = async () => {
    if (signingOut) return
    setSigningOut(true)
    try {
      await supabase.auth.signOut()
    } finally {
      setSigningOut(false)
    }
  }

  return <View style={styles.sessionBar} accessibilityLabel="Sessão, data e hora">
    <View style={styles.dateTime}>
      <Text style={styles.date}>{date}</Text>
      <View style={styles.timePill}><Text style={styles.time}>{time}</Text></View>
    </View>
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Terminar sessão"
      disabled={signingOut}
      onPress={signOut}
      style={({ pressed }) => [styles.signOut, pressed && styles.signOutPressed, signingOut && styles.signOutDisabled]}
    >
      <Text style={styles.signOutText}>{signingOut ? 'A sair…' : 'Terminar sessão'}</Text>
    </Pressable>
  </View>
}

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
    return <View style={styles.loading}><Text style={styles.brand}>Obra<Text style={styles.blue}>Signal</Text></Text><ActivityIndicator size="small" color="#5F8DF7" /><Text style={styles.message}>A recuperar a sessão…</Text></View>
  }

  if (authState.status !== 'signed-in') return <AuthScreen />

  // Hard rule: once Supabase has authenticated the user, the application
  // shell opens immediately. Profile, billing and API availability are
  // background concerns and cannot gate the first authenticated render.
  return <BillingGate>
    {Platform.OS === 'web'
      ? <View style={styles.webShell}><WebSessionBar/><View style={styles.webContent}>{children}</View></View>
      : children}
  </BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, backgroundColor: '#07111C' },
  brand: { fontSize: 25, fontWeight: '800', letterSpacing: -0.8, color: '#F4F7FB' },
  blue: { color: '#7FA2FF' },
  message: { color: '#9BAABD', fontSize: 12 },
  webShell: { flex: 1, minHeight: 0, backgroundColor: '#07111C' },
  webContent: { flex: 1, minHeight: 0 },
  sessionBar: {
    minHeight: 42,
    paddingHorizontal: 18,
    paddingVertical: 7,
    borderBottomWidth: 1,
    borderBottomColor: '#182A3E',
    backgroundColor: '#091522',
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  dateTime: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 },
  date: { color: '#8497AD', fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  timePill: { borderWidth: 1, borderColor: '#263B56', backgroundColor: '#0D1B2B', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4 },
  time: { color: '#C7D2E1', fontSize: 10, fontWeight: '800', fontVariant: ['tabular-nums'] },
  signOut: { minHeight: 28, justifyContent: 'center', borderWidth: 1, borderColor: '#3A2A34', borderRadius: 8, paddingHorizontal: 10, backgroundColor: '#151018' },
  signOutPressed: { backgroundColor: '#21151D', borderColor: '#69404B' },
  signOutDisabled: { opacity: 0.55 },
  signOutText: { color: '#E9A8B2', fontSize: 9, fontWeight: '800' },
})
