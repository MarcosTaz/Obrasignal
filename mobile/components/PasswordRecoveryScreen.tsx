import { useState } from 'react'
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { supabase } from '../lib/supabase'
import { authSession } from '../src/authSession'

export default function PasswordRecoveryScreen() {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function updatePassword() {
    if (password.length < 6) {
      Alert.alert('Palavra-passe inválida', 'Escolhe uma palavra-passe com pelo menos 6 caracteres.')
      return
    }
    if (password !== confirmPassword) {
      Alert.alert('Confirmação inválida', 'As palavras-passe não coincidem.')
      return
    }

    setLoading(true)
    try {
      const { error } = await supabase.auth.updateUser({ password })
      if (error) throw error
      authSession.acknowledgeEvent()
      Alert.alert('Palavra-passe atualizada', 'A nova palavra-passe ficou guardada.')
    } catch (error) {
      Alert.alert('Recuperação', error instanceof Error ? error.message : 'Não foi possível atualizar a palavra-passe.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.brand}>OBRASIGNAL</Text>
      <Text style={styles.title}>Criar nova palavra-passe</Text>
      <Text style={styles.subtitle}>Define a nova palavra-passe para terminares a recuperação da conta.</Text>

      <TextInput
        secureTextEntry
        placeholder="Nova palavra-passe"
        placeholderTextColor="#7f8aa3"
        value={password}
        onChangeText={setPassword}
        style={styles.input}
      />
      <TextInput
        secureTextEntry
        placeholder="Confirmar nova palavra-passe"
        placeholderTextColor="#7f8aa3"
        value={confirmPassword}
        onChangeText={setConfirmPassword}
        style={styles.input}
      />

      <Pressable disabled={loading} onPress={updatePassword} style={({ pressed }) => [styles.primary, pressed && styles.pressed]}>
        <Text style={styles.primaryText}>{loading ? 'A atualizar…' : 'Atualizar palavra-passe'}</Text>
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#f8fbff' },
  brand: { fontSize: 13, fontWeight: '800', letterSpacing: 2.5, color: '#315ea8', marginBottom: 10 },
  title: { fontSize: 30, fontWeight: '800', color: '#17233a' },
  subtitle: { fontSize: 15, lineHeight: 22, color: '#64718a', marginTop: 8, marginBottom: 24 },
  input: { height: 50, borderWidth: 1, borderColor: '#d6deea', backgroundColor: '#fff', borderRadius: 12, paddingHorizontal: 14, color: '#17233a', marginBottom: 12 },
  primary: { height: 50, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#315ea8', marginTop: 4 },
  primaryText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  pressed: { opacity: 0.85 },
})
