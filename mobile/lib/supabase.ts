import 'react-native-url-polyfill/auto'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { AppState, Platform } from 'react-native'
import { createClient, processLock } from '@supabase/supabase-js'

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL
const supabasePublishableKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY
const PUSH_TOKEN_STORAGE_KEY = '@obrasignal/push-token-v1'

if (!supabaseUrl || !supabasePublishableKey) {
  throw new Error('Supabase configuration is missing')
}

export const supabase = createClient(supabaseUrl, supabasePublishableKey, {
  auth: {
    ...(Platform.OS !== 'web' ? { storage: AsyncStorage } : {}),
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: Platform.OS === 'web',
    lock: processLock,
  },
})

if (Platform.OS !== 'web') {
  // Revoke only this physical device's push route before its auth token
  // disappears. Other devices belonging to the same account stay subscribed.
  const originalSignOut = supabase.auth.signOut.bind(supabase.auth)
  supabase.auth.signOut = async (...args) => {
    try {
      const [{ data }, pushToken] = await Promise.all([
        supabase.auth.getSession(),
        AsyncStorage.getItem(PUSH_TOKEN_STORAGE_KEY),
      ])
      const token = data?.session?.access_token
      if (token && pushToken) {
        const base = (process.env.EXPO_PUBLIC_API_URL || 'https://obrasignal.onrender.com/api/v1').replace(/\/$/, '')
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 5000)
        try {
          await fetch(`${base}/push/device`, {
            method: 'DELETE',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ token: pushToken }),
            signal: controller.signal,
          })
        } finally { clearTimeout(timer) }
      }
    } catch (_) {}
    await AsyncStorage.removeItem(PUSH_TOKEN_STORAGE_KEY).catch(() => {})
    return originalSignOut(...args)
  }

  AppState.addEventListener('change', (state) => {
    if (state === 'active') supabase.auth.startAutoRefresh()
    else supabase.auth.stopAutoRefresh()
  })
}
