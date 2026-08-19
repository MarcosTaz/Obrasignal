import React, { useEffect, useState } from 'react'
import { ActivityIndicator, StyleSheet, View } from 'react-native'
import { supabase } from '../lib/supabase'
import { api } from '../src/api'
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

  const loadProfile = async () => {
    setProfileLoading(true)
    setProfileError('')
    try {
      const result = await api.profile()
      setProfile(result?.profile || null)
    } catch (error) {
      setProfileError(error?.message || 'Não foi possível carregar o perfil.')
    } finally {
      setProfileLoading(false)
    }
  }

  useEffect(() => {
    let mounted = true
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return
      setSession(data.session)
      setLoading(false)
      if (data.session) loadProfile()
    })

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      if (nextSession) loadProfile()
      else setProfile(null)
      setLoading(false)
    })

    return () => {
      mounted = false
      subscription.subscription.unsubscribe()
    }
  }, [])

  if (loading || (session && profileLoading)) {
    return <View style={styles.loading}><ActivityIndicator size="large" color="#315ea8" /></View>
  }

  if (!session) return <AuthScreen />

  if (profileError && !profile) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color="#315ea8" />
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
})
