import { useState } from 'react'
import { Alert, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { supabase } from '../lib/supabase'

export default function AuthScreen() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signIn' | 'signUp'>('signIn')
  const [loading, setLoading] = useState(false)

  async function submit() {
    if (!email.trim() || password.length < 6) {
      Alert.alert('Dados inválidos', 'Introduz um email válido e uma palavra-passe com pelo menos 6 caracteres.')
      return
    }

    setLoading(true)
    try {
      const redirectTo = Platform.OS === 'web' && typeof window !== 'undefined'
        ? `${window.location.origin}${window.location.pathname}`
        : undefined
      const result = mode === 'signIn'
        ? await supabase.auth.signInWithPassword({ email: email.trim(), password })
        : await supabase.auth.signUp({
            email: email.trim(),
            password,
            options: redirectTo ? { emailRedirectTo: redirectTo } : undefined,
          })

      if (result.error) throw result.error
      if (mode === 'signUp' && !result.data.session) {
        Alert.alert('Confirma o email', 'Enviámos uma mensagem para confirmares a conta antes de iniciar sessão.')
      }
    } catch (error) {
      Alert.alert('Autenticação', error instanceof Error ? error.message : 'Não foi possível concluir a operação.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.brand}>OBRASIGNAL</Text>
      <Text style={styles.title}>{mode === 'signIn' ? 'Entrar' : 'Criar conta'}</Text>
      <Text style={styles.subtitle}>O teu radar comercial de contratação pública.</Text>

      <TextInput
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="email-address"
        placeholder="Email"
        placeholderTextColor="#7f8aa3"
        value={email}
        onChangeText={setEmail}
        style={styles.input}
      />
      <TextInput
        secureTextEntry
        placeholder="Palavra-passe"
        placeholderTextColor="#7f8aa3"
        value={password}
        onChangeText={setPassword}
        style={styles.input}
      />

      <Pressable disabled={loading} onPress={submit} style={({ pressed }) => [styles.primary, pressed && styles.pressed]}>
        <Text style={styles.primaryText}>{loading ? 'A processar…' : mode === 'signIn' ? 'Entrar' : 'Criar conta'}</Text>
      </Pressable>

      <Pressable onPress={() => setMode(mode === 'signIn' ? 'signUp' : 'signIn')}>
        <Text style={styles.switchText}>
          {mode === 'signIn' ? 'Ainda não tens conta? Criar conta' : 'Já tens conta? Entrar'}
        </Text>
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#f8fbff' },
  brand: { fontSize: 13, fontWeight: '800', letterSpacing: 2.5, color: '#315ea8', marginBottom: 10 },
  title: { fontSize: 32, fontWeight: '800', color: '#17233a' },
  subtitle: { fontSize: 15, lineHeight: 22, color: '#64718a', marginTop: 8, marginBottom: 28 },
  input: { height: 50, borderWidth: 1, borderColor: '#d6deea', backgroundColor: '#fff', borderRadius: 12, paddingHorizontal: 14, color: '#17233a', marginBottom: 12 },
  primary: { height: 50, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#315ea8', marginTop: 4, marginBottom: 18 },
  primaryText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  pressed: { opacity: 0.85 },
  switchText: { textAlign: 'center', color: '#315ea8', fontWeight: '600' },
})
