import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native'
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

  const loadProfile = useCallback(async () => {
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
  }, [])

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
