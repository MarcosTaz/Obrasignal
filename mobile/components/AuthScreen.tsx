import { useEffect, useState } from 'react'
import { Alert, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { supabase } from '../lib/supabase'

type AuthMode = 'signIn' | 'signUp' | 'forgot' | 'recovery'

export default function AuthScreen({ recoverySession = null }) {
  const [email, setEmail] = useState(recoverySession?.user?.email || '')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [mode, setMode] = useState<AuthMode>(recoverySession ? 'recovery' : 'signIn')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (recoverySession) {
      setMode('recovery')
      if (recoverySession?.user?.email) setEmail(recoverySession.user.email)
    }
  }, [recoverySession])

  function browserRedirectTo() {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return undefined
    return `${window.location.origin}${window.location.pathname}`
  }

  async function submitForgotPassword() {
    if (!email.trim()) {
      Alert.alert('Email em falta', 'Introduz o email da conta que queres recuperar.')
      return
    }
    setLoading(true)
    try {
      const redirectTo = browserRedirectTo()
      const { error } = await supabase.auth.resetPasswordForEmail(
        email.trim(),
        redirectTo ? { redirectTo } : undefined,
      )
      if (error) throw error
      Alert.alert(
        'Verifica o email',
        'Se existir uma conta com este email, receberás uma ligação para definires uma nova palavra-passe.',
      )
      setMode('signIn')
      setPassword('')
      setConfirmPassword('')
    } catch (error) {
      Alert.alert('Recuperação', error instanceof Error ? error.message : 'Não foi possível iniciar a recuperação.')
    } finally {
      setLoading(false)
    }
  }

  async function submitRecoveryPassword() {
    if (password.length < 6 || password !== confirmPassword) {
      Alert.alert('Palavra-passe inválida', 'Usa pelo menos 6 caracteres e confirma exatamente a mesma palavra-passe.')
      return
    }
    setLoading(true)
    try {
      const { error: updateError } = await supabase.auth.updateUser({ password })
      if (updateError) throw updateError

      const { error: signOutError } = await supabase.auth.signOut()
      if (signOutError) throw signOutError

      setPassword('')
      setConfirmPassword('')
      setMode('signIn')
      Alert.alert('Palavra-passe atualizada', 'A palavra-passe foi alterada. Inicia sessão novamente com a nova palavra-passe.')
    } catch (error) {
      Alert.alert('Recuperação', error instanceof Error ? error.message : 'Não foi possível atualizar a palavra-passe.')
    } finally {
      setLoading(false)
    }
  }

  async function submitCredentials() {
    if (!email.trim() || password.length < 6) {
      Alert.alert('Dados inválidos', 'Introduz um email válido e uma palavra-passe com pelo menos 6 caracteres.')
      return
    }

    setLoading(true)
    try {
      const redirectTo = browserRedirectTo()
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

  async function submit() {
    if (mode === 'forgot') return submitForgotPassword()
    if (mode === 'recovery') return submitRecoveryPassword()
    return submitCredentials()
  }

  const recoveryMode = mode === 'recovery'
  const forgotMode = mode === 'forgot'
  const title = recoveryMode
    ? 'Nova palavra-passe'
    : forgotMode
      ? 'Recuperar acesso'
      : mode === 'signIn'
        ? 'Entrar'
        : 'Criar conta'

  return (
    <View style={styles.container}>
      <Text style={styles.brand}>OBRASIGNAL</Text>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.subtitle}>
        {recoveryMode
          ? 'Define uma nova palavra-passe. Depois terás de iniciar sessão novamente.'
          : forgotMode
            ? 'Enviaremos uma ligação de recuperação para o email da tua conta.'
            : 'O teu radar comercial de contratação pública.'}
      </Text>

      {!recoveryMode && (
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
      )}

      {!forgotMode && (
        <TextInput
          secureTextEntry
          placeholder={recoveryMode ? 'Nova palavra-passe' : 'Palavra-passe'}
          placeholderTextColor="#7f8aa3"
          value={password}
          onChangeText={setPassword}
          style={styles.input}
        />
      )}

      {recoveryMode && (
        <TextInput
          secureTextEntry
          placeholder="Confirmar nova palavra-passe"
          placeholderTextColor="#7f8aa3"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          style={styles.input}
        />
      )}

      <Pressable disabled={loading} onPress={submit} style={({ pressed }) => [styles.primary, pressed && styles.pressed]}>
        <Text style={styles.primaryText}>
          {loading
            ? 'A processar…'
            : recoveryMode
              ? 'Guardar nova palavra-passe'
              : forgotMode
                ? 'Enviar ligação de recuperação'
                : mode === 'signIn'
                  ? 'Entrar'
                  : 'Criar conta'}
        </Text>
      </Pressable>

      {!recoveryMode && mode === 'signIn' && (
        <Pressable disabled={loading} onPress={() => { setMode('forgot'); setPassword(''); setConfirmPassword('') }}>
          <Text style={styles.switchText}>Esqueci-me da palavra-passe</Text>
        </Pressable>
      )}

      {!recoveryMode && forgotMode && (
        <Pressable disabled={loading} onPress={() => setMode('signIn')}>
          <Text style={styles.switchText}>Voltar a entrar</Text>
        </Pressable>
      )}

      {!recoveryMode && !forgotMode && (
        <Pressable disabled={loading} onPress={() => { setMode(mode === 'signIn' ? 'signUp' : 'signIn'); setPassword(''); setConfirmPassword('') }}>
          <Text style={styles.switchText}>
            {mode === 'signIn' ? 'Ainda não tens conta? Criar conta' : 'Já tens conta? Entrar'}
          </Text>
        </Pressable>
      )}
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
  switchText: { textAlign: 'center', color: '#315ea8', fontWeight: '600', marginBottom: 12 },
})
