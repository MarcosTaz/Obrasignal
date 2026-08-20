import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, AppState, StyleSheet, View } from 'react-native'
import { supabase } from '../lib/supabase'
import { api } from '../src/api'
import { syncUnreadOpportunityAlerts } from '../src/notifications'
import AuthScreen from './AuthScreen'
import BillingGate from './BillingGate'

export default function AuthGate({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadProfileInBackground = useCallback(async () => {
    try {
      try { await api.warmup() } catch (_) {}
      await api.profile()
      try { await syncUnreadOpportunityAlerts() } catch (_) {}
    } catch (_) {
      // Authentication is independent from the API. A temporary API outage
      // must never prevent the authenticated application shell from opening.
    }
  }, [])

  useEffect(() => {
    if (!session) return undefined
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') loadProfileInBackground()
    })
    return () => subscription.remove()
  }, [session, loadProfileInBackground])

  useEffect(() => {
    let mounted = true
    let subscription = null

    const bootstrap = async () => {
      try {
        const { data, error } = await supabase.auth.getSession()
        if (!mounted) return
        if (error) throw error

        setSession(data.session)
        setLoading(false)
        if (data.session) setTimeout(() => mounted && loadProfileInBackground(), 0)

        const { data: listener } = supabase.auth.onAuthStateChange((_, nextSession) => {
          if (!mounted) return
          setSession(nextSession)
          if (nextSession) setTimeout(() => mounted && loadProfileInBackground(), 0)
        })
        subscription = listener?.subscription || null
      } catch (_) {
        if (!mounted) return
        setSession(null)
        setLoading(false)
      }
    }

    bootstrap()
    return () => {
      mounted = false
      subscription?.unsubscribe()
    }
  }, [loadProfileInBackground])

  if (loading) {
    return <View style={styles.loading}><ActivityIndicator size="large" color="#315ea8" /></View>
  }

  if (!session) return <AuthScreen />

  // Hard rule: once Supabase has authenticated the user, the application
  // shell opens immediately. Profile, billing and API availability are
  // background concerns and cannot gate the first authenticated render.
  return <BillingGate>{children}</BillingGate>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fbff' },
})
