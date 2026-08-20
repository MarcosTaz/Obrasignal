import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, AppState, StyleSheet, View } from 'react-native'
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
      try { await syncUnreadOpportunityAlerts() } catch (_) {}
    } catch (error) {
      // A temporary API outage must never lock an already authenticated user
      // outside the application. The app shell can open and retry API calls
      // independently while the backend recovers.
      setProfileError(error?.message || 'Não foi possível carregar o perfil.')
    } finally {
      setProfileLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!session) return undefined
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        syncUnreadOpportunityAlerts().catch(() => {})
        loadProfile()
      }
    })
    return () => subscription.remove()
  }, [session, loadProfile])

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

  if (loading) {
    return <View style={styles.loading}><ActivityIndicator size="large" color="#315ea8" /></View>
  }

  if (!session) return <AuthScreen />

  // Do not make the entire application depend on the API being awake.
  // Supabase has already authenticated the user, so let the app open even
  // when /profile is temporarily unreachable. Once the API recovers,
  // loadProfile() above will restore the normal profile flow automatically.
  if (profileError && !profile) {
    return <BillingGate>{children}</BillingGate>
  }

  if (profileLoading) {
    return <View style={styles.loading}><ActivityIndicator size="large" color="#315ea8" /></View>
  }

  if (needsOnboarding(profile)) {
    return <ProfileOnboarding initialProfile={profile || {}} onComplete={setProfile} />
  }

  return <BillingGate>{children}</BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fbff' },
})
