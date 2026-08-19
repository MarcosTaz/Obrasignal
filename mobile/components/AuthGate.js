import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, AppState, Pressable, StyleSheet, Text, View } from 'react-native'
import { supabase } from '../lib/supabase'
import { api } from '../src/api'
import { syncUnreadOpportunityAlerts } from '../src/notifications'
import AuthScreen from './AuthScreen'
import ProfileOnboarding from './ProfileOnboarding'
import BillingGate from './BillingGate'

function needsOnboarding(profile) {
  if (!profile) return true
  return !profile.name || !profile.activity
}

export default function AuthGate({ children }) {
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState('')

  const loadProfile = useCallback(async () => {
    setProfileLoading(true)
    setProfileError('')
    try {
      try { await api.warmup() } catch (_) {}
      const result = await api.profile()
      setProfile(result?.profile || null)
      // Notification delivery is best-effort and must never block login.
      try { await syncUnreadOpportunityAlerts() } catch (_) {}
    } catch (error) {
      setProfileError(error?.message || 'Não foi possível carregar o perfil.')
    } finally {
      setProfileLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!session) return undefined
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        // Re-check unread events whenever the app returns to the foreground.
        syncUnreadOpportunityAlerts().catch(() => {})
      }
    })
    return () => subscription.remove()
  }, [session])

  useEffect(() => {
    let mounted = true
    let subscription = null

    const scheduleProfileLoad = () => {
      setTimeout(() => {
        if (mounted) loadProfile()
      }, 0)
    }

    const bootstrap = async () => {
      try {
        const { data, error } = await supabase.auth.getSession()
        if (!mounted) return
        if (error) throw error

        setSession(data.session)
        setLoading(false)
        if (data.session) scheduleProfileLoad()

        const { data: listener } = supabase.auth.onAuthStateChange((event, nextSession) => {
          if (!mounted) return
          setSession(nextSession)

          if (!nextSession) {
            setProfile(null)
            setProfileError('')
            setProfileLoading(false)
            return
          }

          if (event !== 'INITIAL_SESSION') scheduleProfileLoad()
        })
        subscription = listener?.subscription || null
      } catch (error) {
        if (!mounted) return
        setSession(null)
        setProfile(null)
        setProfileError(error?.message || 'Não foi possível iniciar a autenticação.')
        setLoading(false)
      }
    }

    bootstrap()

    return () => {
      mounted = false
      subscription?.unsubscribe()
    }
  }, [loadProfile])

  if (loading || (session && profileLoading)) {
    return <View style={styles.loading}><ActivityIndicator size="large" color="#315ea8" /></View>
  }

  if (!session) return <AuthScreen />

  if (profileError && !profile) {
    return (
      <View style={styles.errorScreen}>
        <Text style={styles.errorTitle}>Não foi possível ligar ao ObraSignal</Text>
        <Text style={styles.errorText}>{profileError}</Text>
        <Pressable onPress={loadProfile} style={styles.retryButton}>
          <Text style={styles.retryText}>Tentar novamente</Text>
        </Pressable>
        <Pressable onPress={() => supabase.auth.signOut()} style={styles.signOutButton}>
          <Text style={styles.signOutText}>Terminar sessão</Text>
        </Pressable>
      </View>
    )
  }

  if (needsOnboarding(profile)) {
    return <ProfileOnboarding initialProfile={profile || {}} onComplete={setProfile} />
  }

  return <BillingGate>{children}</BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fbff' },
  errorScreen: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28, backgroundColor: '#f8fbff' },
  errorTitle: { fontSize: 22, fontWeight: '800', color: '#17233a', textAlign: 'center' },
  errorText: { marginTop: 10, fontSize: 14, lineHeight: 21, color: '#64718a', textAlign: 'center' },
  retryButton: { marginTop: 22, minHeight: 48, paddingHorizontal: 22, borderRadius: 12, backgroundColor: '#315ea8', alignItems: 'center', justifyContent: 'center' },
  retryText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  signOutButton: { marginTop: 10, minHeight: 42, alignItems: 'center', justifyContent: 'center' },
  signOutText: { color: '#315ea8', fontSize: 13, fontWeight: '700' },
})
