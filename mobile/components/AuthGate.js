import React, { useEffect, useState } from 'react'
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native'
import { supabase } from '../lib/supabase'
import AuthScreen from './AuthScreen'
import BillingGate from './BillingGate'

export default function AuthGate({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)


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

        const { data: listener } = supabase.auth.onAuthStateChange((_, nextSession) => {
          if (!mounted) return
          setSession(nextSession)
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
  }, [])

  if (loading) {
    return <View style={styles.loading}><Text style={styles.brand}>OBRA<Text style={styles.blue}>SIGNAL</Text></Text><ActivityIndicator size="small" color="#5E8BFF" /><Text style={styles.message}>A recuperar a sessão…</Text></View>
  }

  if (!session) return <AuthScreen />

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
