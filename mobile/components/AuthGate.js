import React, { useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from 'react-native'
import AuthScreen from './AuthScreen'
import BillingGate from './BillingGate'
import { supabase } from '../lib/supabase'
import { ensureBackendReady } from '../src/api'
import { authSession } from '../src/authSession'
import { storage } from '../src/storage'

const TRANSLATE_ELEMENT_ID = 'obrasignal-google-translate'
const TRANSLATE_SCRIPT_ID = 'obrasignal-google-translate-script'

function WebTranslator() {
  const [enabled, setEnabled] = useState(false)
  const [available, setAvailable] = useState(true)

  useEffect(() => {
    if (!enabled || typeof window === 'undefined' || typeof document === 'undefined') return undefined
    let active = true

    const mountTranslator = () => {
      if (!active) return
      const host = document.getElementById(TRANSLATE_ELEMENT_ID)
      const TranslateElement = window.google?.translate?.TranslateElement
      if (!host || !TranslateElement || host.querySelector('.goog-te-combo')) return
      try {
        new TranslateElement({ pageLanguage: 'pt', autoDisplay: false, multilanguagePage: true }, TRANSLATE_ELEMENT_ID)
        setAvailable(true)
      } catch (_) { setAvailable(false) }
    }

    window.obrasignalGoogleTranslateInit = mountTranslator
    if (window.google?.translate?.TranslateElement) {
      mountTranslator()
    } else if (!document.getElementById(TRANSLATE_SCRIPT_ID)) {
      const script = document.createElement('script')
      script.id = TRANSLATE_SCRIPT_ID
      script.async = true
      script.src = 'https://translate.google.com/translate_a/element.js?cb=obrasignalGoogleTranslateInit'
      script.onerror = () => { if (active) setAvailable(false) }
      document.head.appendChild(script)
    }
    return () => { active = false }
  }, [enabled])

  return <View style={styles.translateArea} accessibilityLabel="Tradutor da página">
    {!enabled
      ? <Pressable accessibilityRole="button" accessibilityLabel="Ativar tradutor" onPress={() => setEnabled(true)} style={({pressed}) => [styles.translateButton, pressed && styles.translatePressed]}><Text style={styles.translateButtonText}>Traduzir ▾</Text></Pressable>
      : <><Text style={styles.translateLabel}>Tradutor</Text>{available ? <View nativeID={TRANSLATE_ELEMENT_ID} style={styles.translateWidget}/> : <Text style={styles.translateUnavailable}>indisponível</Text>}</>}
  </View>
}

function WebSessionBar() {
  const [now, setNow] = useState(() => new Date())
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState('')

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const date = useMemo(() => new Intl.DateTimeFormat('pt-PT', {
    weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
  }).format(now), [now.getFullYear(), now.getMonth(), now.getDate()])
  const time = new Intl.DateTimeFormat('pt-PT', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(now)

  const signOut = async () => {
    if (signingOut) return
    setSigningOut(true)
    setSignOutError('')
    try {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    } catch (_) {
      setSignOutError('Não foi possível terminar a sessão. Tenta novamente.')
    } finally { setSigningOut(false) }
  }

  return <View style={styles.sessionBar} accessibilityLabel="Data, hora, tradutor e sessão">
    <View style={styles.dateTime}>
      <Text style={styles.date}>{date}</Text>
      <View style={styles.timePill}><Text style={styles.time}>{time}</Text></View>
      <WebTranslator/>
    </View>
    <View style={styles.sessionActions}>
      {signOutError ? <Text accessibilityRole="alert" style={styles.sessionError}>{signOutError}</Text> : null}
      <Pressable disabled={signingOut} accessibilityRole="button" accessibilityLabel="Terminar sessão" onPress={signOut} style={({pressed}) => [styles.logoutButton, pressed && styles.translatePressed, signingOut && styles.disabled]}>
        <Text style={styles.logoutText}>{signingOut ? 'A sair…' : 'Terminar sessão'}</Text>
      </Pressable>
    </View>
  </View>
}

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
          if (signedIn) ensureBackendReady().catch(() => {})
        })
        .catch(() => {
          if (!active || currentGeneration !== generation) return
          if (nextState.status !== 'signed-in') {
            setAuthState(nextState)
            setTenantStatus('ready')
            return
          }
          setTenantStatus('error')
        })
    }

    const unsubscribe = authSession.subscribe(update)
    authSession.start().then(update).catch(() => update({ status: 'signed-out', session: null }))
    return () => { active = false; generation += 1; unsubscribe() }
  }, [])

  if (authState.status === 'loading' || tenantStatus === 'loading') {
    return <View style={styles.loading}><Text style={styles.brand}>Obra<Text style={styles.blue}>Signal</Text></Text><ActivityIndicator size="small" color="#5F8DF7"/><Text style={styles.message}>A recuperar a sessão…</Text></View>
  }
  if (tenantStatus === 'error') {
    return <View style={styles.loading}><Text style={styles.brand}>Obra<Text style={styles.blue}>Signal</Text></Text><Text style={styles.error}>Não foi possível validar o armazenamento privado desta sessão.</Text></View>
  }
  if (authState.status !== 'signed-in') return <AuthScreen />

  return <BillingGate>
    {Platform.OS === 'web'
      ? <View style={styles.webShell}><WebSessionBar/><View style={styles.webContent}>{children}</View></View>
      : children}
  </BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, backgroundColor: '#07111C' },
  brand: { fontSize: 25, fontWeight: '800', letterSpacing: -0.8, color: '#F4F7FB' }, blue: { color: '#7FA2FF' },
  message: { color: '#9BAABD', fontSize: 12 }, error: { color: '#FF8998', fontSize: 12, textAlign: 'center', paddingHorizontal: 24 },
  webShell: { flex: 1, minHeight: 0, backgroundColor: '#07111C' }, webContent: { flex: 1, minHeight: 0 },
  sessionBar: { minHeight: 44, paddingHorizontal: 18, paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: '#182A3E', backgroundColor: '#091522', flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  dateTime: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 },
  date: { color: '#8497AD', fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  timePill: { borderWidth: 1, borderColor: '#263B56', backgroundColor: '#0D1B2B', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4 },
  time: { color: '#C7D2E1', fontSize: 10, fontWeight: '800', fontVariant: ['tabular-nums'] },
  translateArea: { minHeight: 28, flexDirection: 'row', alignItems: 'center', gap: 7, borderLeftWidth: 1, borderLeftColor: '#263B56', paddingLeft: 10 },
  translateButton: { borderWidth: 1, borderColor: '#263B56', backgroundColor: '#0D1B2B', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  translatePressed: { opacity: 0.75 }, translateButtonText: { color: '#C7D2E1', fontSize: 10, fontWeight: '800' },
  translateLabel: { color: '#8497AD', fontSize: 10, fontWeight: '800' }, translateWidget: { minWidth: 128, minHeight: 24, justifyContent: 'center' }, translateUnavailable: { color: '#8497AD', fontSize: 10, fontWeight: '700' },
  sessionActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 8 },
  sessionError: { color: '#FF9DAA', fontSize: 9, fontWeight: '700' },
  logoutButton: { minHeight: 30, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 999, borderWidth: 1, borderColor: '#5A3440', backgroundColor: '#1A1118' },
  logoutText: { color: '#FFB6C0', fontSize: 10, fontWeight: '800' }, disabled: { opacity: 0.55 },
})
