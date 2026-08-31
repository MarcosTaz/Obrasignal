import { useMemo, useState } from 'react'
import { Alert, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions } from 'react-native'
import { supabase } from '../lib/supabase'

const COLORS = {
  bg: '#07101c',
  bgSoft: '#0b1626',
  panel: '#101d30',
  panelSoft: '#14243a',
  line: '#263955',
  text: '#f5f8ff',
  muted: '#9eb0c9',
  blue: '#6c92ff',
  blueSoft: '#182b55',
  green: '#74e3a1',
  amber: '#ffd978',
  white: '#ffffff',
}

type Mode = 'signIn' | 'signUp'

export default function AuthScreen() {
  const { width } = useWindowDimensions()
  const compact = width < 760
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<Mode>('signIn')
  const [loading, setLoading] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [showAuth, setShowAuth] = useState(Platform.OS !== 'web')

  const redirectTo = useMemo(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return undefined
    return `${window.location.origin}${window.location.pathname}`
  }, [])

  function openAuth(nextMode: Mode) {
    setMode(nextMode)
    setShowAuth(true)
  }

  async function submit() {
    if (!email.trim() || password.length < 6) {
      Alert.alert('Dados inválidos', 'Introduz um email válido e uma palavra-passe com pelo menos 6 caracteres.')
      return
    }

    setLoading(true)
    try {
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

  async function resetPassword() {
    if (!email.trim()) {
      Alert.alert('Email necessário', 'Introduz o teu email para receberes a ligação de recuperação.')
      return
    }
    setResetting(true)
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), redirectTo ? { redirectTo } : undefined)
      if (error) throw error
      Alert.alert('Verifica o email', 'Enviámos uma ligação para recuperares o acesso à tua conta.')
    } catch (error) {
      Alert.alert('Recuperação de acesso', error instanceof Error ? error.message : 'Não foi possível enviar a recuperação.')
    } finally {
      setResetting(false)
    }
  }

  if (showAuth) {
    return (
      <View style={styles.authPage}>
        <View style={[styles.authShell, compact && styles.authShellCompact]}>
          {Platform.OS === 'web' ? (
            <Pressable onPress={() => setShowAuth(false)} style={styles.backButton}>
              <Text style={styles.backButtonText}>← Voltar à ObraSignal</Text>
            </Pressable>
          ) : null}
          <View style={styles.authBrandRow}>
            <Brand />
            <View style={styles.livePill}><View style={styles.liveDot}/><Text style={styles.liveText}>Acesso antecipado</Text></View>
          </View>
          <Text style={styles.authTitle}>{mode === 'signIn' ? 'Bem-vindo de volta.' : 'Cria o teu radar.'}</Text>
          <Text style={styles.authSubtitle}>
            {mode === 'signIn'
              ? 'Entra para continuar a acompanhar oportunidades, decisões e próximos passos.'
              : 'Configura o perfil da tua empresa e recebe um radar comercial filtrado para o que realmente interessa.'}
          </Text>

          <Text style={styles.fieldLabel}>Email</Text>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            placeholder="nome@empresa.pt"
            placeholderTextColor="#7587a3"
            value={email}
            onChangeText={setEmail}
            style={styles.input}
          />
          <View style={styles.passwordLabelRow}>
            <Text style={styles.fieldLabel}>Palavra-passe</Text>
            {mode === 'signIn' ? (
              <Pressable disabled={resetting} onPress={resetPassword}>
                <Text style={styles.forgot}>{resetting ? 'A enviar…' : 'Recuperar acesso'}</Text>
              </Pressable>
            ) : null}
          </View>
          <TextInput
            secureTextEntry
            placeholder="Mínimo de 6 caracteres"
            placeholderTextColor="#7587a3"
            value={password}
            onChangeText={setPassword}
            style={styles.input}
          />

          <Pressable disabled={loading} onPress={submit} style={({ pressed }) => [styles.primary, pressed && styles.pressed, loading && styles.disabled]}>
            <Text style={styles.primaryText}>{loading ? 'A processar…' : mode === 'signIn' ? 'Entrar na ObraSignal' : 'Criar conta'}</Text>
          </Pressable>

          <Pressable onPress={() => setMode(mode === 'signIn' ? 'signUp' : 'signIn')}>
            <Text style={styles.switchText}>
              {mode === 'signIn' ? 'Ainda não tens conta? Criar conta →' : 'Já tens conta? Entrar →'}
            </Text>
          </Pressable>
          <Text style={styles.authTrust}>Dados de contratação pública com fonte e contexto. Confirma sempre os requisitos na publicação oficial.</Text>
        </View>
      </View>
    )
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.pageContent}>
      <View style={styles.siteShell}>
        <View style={[styles.nav, compact && styles.navCompact]}>
          <Brand />
          <View style={styles.navActions}>
            {!compact ? <Text style={styles.navHint}>Radar · Decisão · Acompanhamento</Text> : null}
            <Pressable onPress={() => openAuth('signIn')} style={styles.navLogin}><Text style={styles.navLoginText}>Entrar</Text></Pressable>
          </View>
        </View>

        <View style={[styles.hero, compact && styles.heroCompact]}>
          <View style={styles.heroCopy}>
            <View style={styles.eyebrow}><View style={styles.liveDot}/><Text style={styles.eyebrowText}>RADAR COMERCIAL PARA CONTRATAÇÃO PÚBLICA</Text></View>
            <Text style={[styles.heroTitle, compact && styles.heroTitleCompact]}>Encontra os concursos que merecem o teu tempo.</Text>
            <Text style={styles.heroSubtitle}>A ObraSignal filtra oportunidades públicas para o perfil da tua empresa, explica o encaixe e transforma pesquisa dispersa num processo comercial claro.</Text>
            <View style={[styles.heroActions, compact && styles.heroActionsCompact]}>
              <Pressable onPress={() => Linking.openURL('mailto:obrasignal.pt@gmail.com?subject=Quero%20uma%20amostra%20ObraSignal')} style={styles.heroPrimary}>
                <Text style={styles.heroPrimaryText}>Receber uma amostra</Text><Text style={styles.heroArrow}>↗</Text>
              </Pressable>
              <Pressable onPress={() => openAuth('signUp')} style={styles.heroSecondary}><Text style={styles.heroSecondaryText}>Criar conta</Text></Pressable>
            </View>
            <Text style={styles.microcopy}>Sem feed genérico. Poucas oportunidades, com razão de encaixe e fonte oficial.</Text>
          </View>

          <View style={styles.productFrame}>
            <View style={styles.windowTop}>
              <View style={styles.windowDots}><View style={styles.dot}/><View style={styles.dot}/><View style={styles.dot}/></View>
              <Text style={styles.windowLabel}>OBRASIGNAL / RADAR</Text>
              <Text style={styles.windowMeta}>EXEMPLO</Text>
            </View>
            <View style={styles.metricRow}>
              <Metric value="12" label="Oportunidades" />
              <Metric value="7" label="Abertas" />
              <Metric value="3" label="Alta relevância" />
            </View>
            <View style={styles.mockSearch}><Text style={styles.mockSearchIcon}>⌕</Text><Text style={styles.mockSearchText}>Instalações elétricas · Portugal</Text><View style={styles.filterChip}><Text style={styles.filterChipText}>75+</Text></View></View>
            <OpportunityMock score="92" title="Empreitada de instalações elétricas em edifício público" meta="Prazo: 14 dias · Fonte oficial disponível" reason="Boa correspondência com atividade, CPV e âmbito geográfico." />
            <OpportunityMock score="84" title="Reabilitação técnica e melhoria de infraestrutura" meta="Prazo: 21 dias · Documentos publicados" reason="Potencial encaixe; confirmar capacidade e requisitos específicos." />
          </View>
        </View>

        <View style={styles.signalBar}>
          {[
            ['01', 'Fontes oficiais', 'Cada oportunidade aponta para a origem.'],
            ['02', 'Encaixe explicado', 'O score vem acompanhado da razão.'],
            ['03', 'Próximo passo', 'Estado e notas ficam no mesmo fluxo.'],
            ['04', 'Menos ruído', 'Filtros focam a equipa no que merece análise.'],
          ].map(([n, title, copy]) => <TrustItem key={n} n={n} title={title} copy={copy} compact={compact} />)}
        </View>

        <SectionLabel index="01" label="COMO FUNCIONA" />
        <View style={[styles.sectionIntro, compact && styles.sectionIntroCompact]}>
          <Text style={styles.sectionTitle}>Da pesquisa à decisão, sem perder horas a separar ruído.</Text>
          <Text style={styles.sectionCopy}>A experiência foi desenhada como um workflow, não como uma lista infinita de anúncios.</Text>
        </View>
        <View style={[styles.steps, compact && styles.stepsCompact]}>
          <Step number="1" title="Define o perfil" copy="Atividade, interesses, CPVs, regiões e dimensão económica relevante para a empresa." />
          <Step number="2" title="Recebe o Radar" copy="A ObraSignal cruza o perfil com oportunidades e ordena o que merece atenção primeiro." />
          <Step number="3" title="Transforma sinal em ação" copy="Abre a fonte, regista decisão, nota o próximo passo e acompanha o estado comercial." />
        </View>

        <SectionLabel index="02" label="PRODUTO" />
        <View style={[styles.bento, compact && styles.bentoCompact]}>
          <View style={[styles.bentoCard, styles.bentoLarge]}>
            <Text style={styles.cardKicker}>RADAR</Text>
            <Text style={styles.bentoTitle}>Clareza primeiro. Volume depois.</Text>
            <Text style={styles.bentoCopy}>Em vez de despejar centenas de resultados, a interface destaca score, comprador, prazo, valor quando disponível e motivo de correspondência.</Text>
            <View style={styles.miniRadar}>
              <View style={styles.miniRadarRow}><Text style={styles.miniRadarTitle}>Oportunidade prioritária</Text><Text style={styles.goodScore}>91/100</Text></View>
              <Text style={styles.miniRadarMeta}>Correspondência forte · prazo confirmado</Text>
            </View>
          </View>
          <View style={styles.bentoCard}>
            <Text style={styles.cardKicker}>EXPLICABILIDADE</Text>
            <Text style={styles.bentoTitleSmall}>Sabes porque apareceu.</Text>
            <Text style={styles.bentoCopy}>O score não é uma caixa preta: a oportunidade inclui contexto suficiente para decidir se vale investigação.</Text>
          </View>
          <View style={styles.bentoCard}>
            <Text style={styles.cardKicker}>WORKFLOW</Text>
            <Text style={styles.bentoTitleSmall}>Do “novo” ao “ganho”.</Text>
            <View style={styles.statusRow}>{['Novo','Análise','Preparar','Enviado'].map((item, index) => <View key={item} style={[styles.statusChip, index === 1 && styles.statusChipOn]}><Text style={styles.statusChipText}>{item}</Text></View>)}</View>
          </View>
        </View>

        <SectionLabel index="03" label="CONFIANÇA" />
        <View style={[styles.trustPanel, compact && styles.trustPanelCompact]}>
          <View style={styles.trustCopyWrap}>
            <Text style={styles.trustBig}>A ObraSignal recomenda. A fonte oficial manda.</Text>
            <Text style={styles.trustCopy}>A decisão comercial continua nas mãos da empresa. O produto ajuda a priorizar e organizar; prazos, requisitos, documentos e contactos devem ser confirmados na publicação oficial.</Text>
          </View>
          <View style={styles.trustChecklist}>
            {['Origem visível', 'Prazo destacado', 'Razão de encaixe', 'Estado comercial', 'Notas internas'].map(item => <View style={styles.checkRow} key={item}><Text style={styles.check}>✓</Text><Text style={styles.checkText}>{item}</Text></View>)}
          </View>
        </View>

        <View style={[styles.finalCta, compact && styles.finalCtaCompact]}>
          <View style={styles.finalCtaCopy}>
            <Text style={styles.finalEyebrow}>VÊ O QUE A OBRASIGNAL ENCONTRA PARA A TUA EMPRESA</Text>
            <Text style={styles.finalTitle}>Começa por uma amostra pequena. Decide com dados reais.</Text>
          </View>
          <View style={styles.finalActions}>
            <Pressable onPress={() => Linking.openURL('mailto:obrasignal.pt@gmail.com?subject=Quero%20uma%20amostra%20ObraSignal')} style={styles.heroPrimary}><Text style={styles.heroPrimaryText}>Pedir amostra</Text><Text style={styles.heroArrow}>↗</Text></Pressable>
            <Pressable onPress={() => openAuth('signIn')} style={styles.footerLogin}><Text style={styles.footerLoginText}>Já sou cliente →</Text></Pressable>
          </View>
        </View>

        <View style={[styles.footer, compact && styles.footerCompact]}>
          <Brand />
          <Text style={styles.footerText}>Radar comercial para contratação pública · Portugal</Text>
          <Text style={styles.footerText}>obrasignal.pt@gmail.com</Text>
        </View>
      </View>
    </ScrollView>
  )
}

function Brand() {
  return <Text style={styles.brand}>OBRA<Text style={styles.brandAccent}>SIGNAL</Text></Text>
}

function Metric({ value, label }: { value: string, label: string }) {
  return <View style={styles.metric}><Text style={styles.metricValue}>{value}</Text><Text style={styles.metricLabel}>{label}</Text></View>
}

function OpportunityMock({ score, title, meta, reason }: { score: string, title: string, meta: string, reason: string }) {
  return <View style={styles.opportunityMock}>
    <View style={styles.mockTop}><Text style={styles.mockSource}>TED / BASE</Text><Text style={styles.mockScore}>{score}/100</Text></View>
    <Text style={styles.mockTitle}>{title}</Text>
    <Text style={styles.mockMeta}>{meta}</Text>
    <Text style={styles.mockReason}>{reason}</Text>
    <Text style={styles.mockLink}>Ver oportunidade →</Text>
  </View>
}

function TrustItem({ n, title, copy, compact }: { n: string, title: string, copy: string, compact: boolean }) {
  return <View style={[styles.trustItem, compact && styles.trustItemCompact]}><Text style={styles.trustNumber}>{n}</Text><Text style={styles.trustItemTitle}>{title}</Text><Text style={styles.trustItemCopy}>{copy}</Text></View>
}

function SectionLabel({ index, label }: { index: string, label: string }) {
  return <View style={styles.sectionLabel}><Text style={styles.sectionIndex}>{index}</Text><View style={styles.sectionLine}/><Text style={styles.sectionLabelText}>{label}</Text></View>
}

function Step({ number, title, copy }: { number: string, title: string, copy: string }) {
  return <View style={styles.step}><Text style={styles.stepNumber}>{number}</Text><Text style={styles.stepTitle}>{title}</Text><Text style={styles.stepCopy}>{copy}</Text></View>
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: COLORS.bg },
  pageContent: { backgroundColor: COLORS.bg },
  siteShell: { width: '100%', maxWidth: 1240, alignSelf: 'center', paddingHorizontal: 24 },
  nav: { minHeight: 82, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: '#1d2c42' },
  navCompact: { minHeight: 68 },
  brand: { color: COLORS.white, fontSize: 16, fontWeight: '900', letterSpacing: 2.2 },
  brandAccent: { color: COLORS.blue },
  navActions: { flexDirection: 'row', alignItems: 'center', gap: 18 },
  navHint: { color: '#70839f', fontSize: 12 },
  navLogin: { borderWidth: 1, borderColor: '#365078', borderRadius: 999, paddingHorizontal: 17, paddingVertical: 10 },
  navLoginText: { color: COLORS.text, fontWeight: '700', fontSize: 13 },
  hero: { minHeight: 650, flexDirection: 'row', gap: 52, alignItems: 'center', paddingVertical: 76 },
  heroCompact: { flexDirection: 'column', alignItems: 'stretch', gap: 38, paddingTop: 54, paddingBottom: 58 },
  heroCopy: { flex: 1, minWidth: 0 },
  eyebrow: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 11, paddingVertical: 7, borderRadius: 999, backgroundColor: '#0f2036', borderWidth: 1, borderColor: '#223a5c', marginBottom: 24 },
  eyebrowText: { color: '#adc0dd', fontSize: 10, fontWeight: '800', letterSpacing: 1.35 },
  liveDot: { width: 7, height: 7, borderRadius: 99, backgroundColor: COLORS.green },
  heroTitle: { color: COLORS.text, fontSize: 58, lineHeight: 62, fontWeight: '900', letterSpacing: -2.3, maxWidth: 620 },
  heroTitleCompact: { fontSize: 42, lineHeight: 46, letterSpacing: -1.5 },
  heroSubtitle: { color: '#a7b7cc', fontSize: 18, lineHeight: 29, maxWidth: 600, marginTop: 24 },
  heroActions: { flexDirection: 'row', gap: 12, marginTop: 32, alignItems: 'center' },
  heroActionsCompact: { flexDirection: 'column', alignItems: 'stretch' },
  heroPrimary: { minHeight: 52, borderRadius: 12, backgroundColor: COLORS.text, paddingHorizontal: 20, flexDirection: 'row', gap: 12, alignItems: 'center', justifyContent: 'center' },
  heroPrimaryText: { color: COLORS.bg, fontSize: 15, fontWeight: '800' },
  heroArrow: { color: COLORS.bg, fontSize: 16, fontWeight: '800' },
  heroSecondary: { minHeight: 52, borderRadius: 12, borderWidth: 1, borderColor: '#304665', paddingHorizontal: 20, alignItems: 'center', justifyContent: 'center' },
  heroSecondaryText: { color: COLORS.text, fontSize: 15, fontWeight: '700' },
  microcopy: { color: '#6f819a', marginTop: 16, fontSize: 12, lineHeight: 18 },
  productFrame: { flex: 1, minWidth: 0, borderRadius: 20, borderWidth: 1, borderColor: '#2a3f5e', backgroundColor: '#0b1524', padding: 16, shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 35, shadowOffset: { width: 0, height: 20 } },
  windowTop: { flexDirection: 'row', alignItems: 'center', paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: '#1b2b42' },
  windowDots: { flexDirection: 'row', gap: 5, marginRight: 10 },
  dot: { width: 7, height: 7, borderRadius: 99, backgroundColor: '#344761' },
  windowLabel: { color: '#8ea2bf', fontSize: 10, fontWeight: '800', letterSpacing: 1.2, flex: 1 },
  windowMeta: { color: '#596d88', fontSize: 9, fontWeight: '800' },
  metricRow: { flexDirection: 'row', gap: 8, paddingVertical: 14 },
  metric: { flex: 1, backgroundColor: '#101d30', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#1e304a' },
  metricValue: { color: COLORS.text, fontSize: 20, fontWeight: '900' },
  metricLabel: { color: '#7287a3', fontSize: 9, marginTop: 3 },
  mockSearch: { height: 42, flexDirection: 'row', alignItems: 'center', borderRadius: 10, borderWidth: 1, borderColor: '#233754', backgroundColor: '#0e1a2b', paddingHorizontal: 12, marginBottom: 10 },
  mockSearchIcon: { color: COLORS.blue, marginRight: 7, fontSize: 15 },
  mockSearchText: { color: '#93a6c0', fontSize: 11, flex: 1 },
  filterChip: { backgroundColor: COLORS.blueSoft, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 999 },
  filterChipText: { color: '#9db7ff', fontSize: 9, fontWeight: '800' },
  opportunityMock: { backgroundColor: '#101d30', borderWidth: 1, borderColor: '#20334f', borderRadius: 12, padding: 14, marginTop: 9 },
  mockTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  mockSource: { color: '#69809e', fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  mockScore: { color: COLORS.green, fontSize: 12, fontWeight: '900' },
  mockTitle: { color: COLORS.text, fontSize: 14, lineHeight: 19, fontWeight: '800', marginTop: 9 },
  mockMeta: { color: '#7f93ae', fontSize: 10, marginTop: 7 },
  mockReason: { color: '#a9b9cd', fontSize: 10, lineHeight: 15, marginTop: 8 },
  mockLink: { color: '#89a6ff', fontSize: 10, fontWeight: '800', marginTop: 10 },
  signalBar: { flexDirection: 'row', flexWrap: 'wrap', borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#1d2c42', paddingVertical: 6, marginBottom: 110 },
  trustItem: { width: '25%', minWidth: 210, paddingVertical: 25, paddingHorizontal: 18, borderRightWidth: 1, borderRightColor: '#1d2c42' },
  trustItemCompact: { width: '50%', minWidth: 0, borderRightWidth: 0 },
  trustNumber: { color: '#536b8d', fontSize: 10, fontWeight: '900', marginBottom: 12 },
  trustItemTitle: { color: COLORS.text, fontWeight: '800', fontSize: 14 },
  trustItemCopy: { color: '#7f93ad', fontSize: 11, lineHeight: 17, marginTop: 7 },
  sectionLabel: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 24 },
  sectionIndex: { color: COLORS.blue, fontSize: 10, fontWeight: '900' },
  sectionLine: { width: 28, height: 1, backgroundColor: '#365175' },
  sectionLabelText: { color: '#7186a3', fontSize: 10, fontWeight: '900', letterSpacing: 1.4 },
  sectionIntro: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', gap: 36, marginBottom: 42 },
  sectionIntroCompact: { flexDirection: 'column', alignItems: 'flex-start', gap: 14 },
  sectionTitle: { flex: 1, color: COLORS.text, fontSize: 38, lineHeight: 43, letterSpacing: -1.25, fontWeight: '900', maxWidth: 690 },
  sectionCopy: { color: '#8397b2', fontSize: 14, lineHeight: 22, maxWidth: 380 },
  steps: { flexDirection: 'row', gap: 14, marginBottom: 120 },
  stepsCompact: { flexDirection: 'column' },
  step: { flex: 1, backgroundColor: COLORS.bgSoft, borderWidth: 1, borderColor: '#1f314b', borderRadius: 16, padding: 24, minHeight: 210 },
  stepNumber: { color: COLORS.blue, fontSize: 12, fontWeight: '900' },
  stepTitle: { color: COLORS.text, fontSize: 20, fontWeight: '900', marginTop: 34 },
  stepCopy: { color: '#879ab4', fontSize: 13, lineHeight: 20, marginTop: 12 },
  bento: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginBottom: 120 },
  bentoCompact: { flexDirection: 'column' },
  bentoCard: { flexGrow: 1, flexBasis: 300, backgroundColor: COLORS.bgSoft, borderWidth: 1, borderColor: '#20334e', borderRadius: 18, padding: 26, minHeight: 260 },
  bentoLarge: { flexBasis: 560 },
  cardKicker: { color: '#647b9a', fontSize: 10, fontWeight: '900', letterSpacing: 1.3 },
  bentoTitle: { color: COLORS.text, fontSize: 30, lineHeight: 35, fontWeight: '900', letterSpacing: -0.8, marginTop: 24, maxWidth: 500 },
  bentoTitleSmall: { color: COLORS.text, fontSize: 23, lineHeight: 29, fontWeight: '900', letterSpacing: -0.4, marginTop: 24 },
  bentoCopy: { color: '#879ab4', fontSize: 13, lineHeight: 21, marginTop: 14, maxWidth: 570 },
  miniRadar: { borderWidth: 1, borderColor: '#263b59', backgroundColor: '#0d1929', borderRadius: 12, padding: 15, marginTop: 28 },
  miniRadarRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  miniRadarTitle: { color: '#c9d4e5', fontSize: 12, fontWeight: '700', flex: 1 },
  miniRadarMeta: { color: '#7086a3', fontSize: 10, marginTop: 7 },
  goodScore: { color: COLORS.green, fontWeight: '900', fontSize: 12 },
  statusRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, marginTop: 28 },
  statusChip: { borderWidth: 1, borderColor: '#314763', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 999 },
  statusChipOn: { backgroundColor: COLORS.blueSoft, borderColor: '#456ac7' },
  statusChipText: { color: '#9eb0c8', fontSize: 9, fontWeight: '800' },
  trustPanel: { flexDirection: 'row', alignItems: 'center', gap: 48, backgroundColor: '#0e1a2b', borderWidth: 1, borderColor: '#223650', borderRadius: 20, padding: 40, marginBottom: 120 },
  trustPanelCompact: { flexDirection: 'column', alignItems: 'stretch', padding: 26 },
  trustCopyWrap: { flex: 1 },
  trustBig: { color: COLORS.text, fontSize: 32, lineHeight: 38, fontWeight: '900', letterSpacing: -0.8 },
  trustCopy: { color: '#8da0ba', fontSize: 13, lineHeight: 21, marginTop: 17, maxWidth: 640 },
  trustChecklist: { minWidth: 250, gap: 11 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  check: { color: COLORS.green, fontSize: 14, fontWeight: '900' },
  checkText: { color: '#bdc9d9', fontSize: 12, fontWeight: '700' },
  finalCta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 40, borderTopWidth: 1, borderBottomWidth: 1, borderColor: '#263852', paddingVertical: 58 },
  finalCtaCompact: { flexDirection: 'column', alignItems: 'stretch', paddingVertical: 42 },
  finalCtaCopy: { flex: 1 },
  finalEyebrow: { color: '#6f85a3', fontSize: 10, fontWeight: '900', letterSpacing: 1.2 },
  finalTitle: { color: COLORS.text, fontSize: 34, lineHeight: 40, fontWeight: '900', letterSpacing: -0.9, marginTop: 14, maxWidth: 660 },
  finalActions: { gap: 10, minWidth: 210 },
  footerLogin: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  footerLoginText: { color: '#9ab2d3', fontSize: 13, fontWeight: '700' },
  footer: { minHeight: 120, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 20 },
  footerCompact: { flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center', paddingVertical: 30 },
  footerText: { color: '#627691', fontSize: 11 },

  authPage: { flex: 1, minHeight: '100%', backgroundColor: COLORS.bg, alignItems: 'center', justifyContent: 'center', padding: 24 },
  authShell: { width: '100%', maxWidth: 500, backgroundColor: '#0d1929', borderWidth: 1, borderColor: '#273c58', borderRadius: 20, padding: 34, shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 30, shadowOffset: { width: 0, height: 16 } },
  authShellCompact: { padding: 24 },
  backButton: { alignSelf: 'flex-start', marginBottom: 28 },
  backButtonText: { color: '#8da4c4', fontSize: 12, fontWeight: '700' },
  authBrandRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 14 },
  livePill: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#24425a', backgroundColor: '#102131', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6 },
  liveText: { color: '#8fb2c8', fontSize: 9, fontWeight: '800' },
  authTitle: { color: COLORS.text, fontSize: 34, lineHeight: 40, fontWeight: '900', letterSpacing: -0.8, marginTop: 34 },
  authSubtitle: { color: '#8fa2bc', fontSize: 14, lineHeight: 22, marginTop: 11, marginBottom: 30 },
  fieldLabel: { color: '#a9b8cb', fontSize: 11, fontWeight: '800', marginBottom: 8 },
  passwordLabelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  forgot: { color: '#84a4ff', fontSize: 10, fontWeight: '700', marginBottom: 8 },
  input: { height: 52, borderWidth: 1, borderColor: '#2a3e5b', backgroundColor: '#091421', borderRadius: 11, paddingHorizontal: 14, color: COLORS.text, marginBottom: 16 },
  primary: { height: 52, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.text, marginTop: 4, marginBottom: 18 },
  primaryText: { color: COLORS.bg, fontSize: 14, fontWeight: '900' },
  pressed: { opacity: 0.84 },
  disabled: { opacity: 0.6 },
  switchText: { textAlign: 'center', color: '#89a7ff', fontWeight: '700', fontSize: 12 },
  authTrust: { textAlign: 'center', color: '#5e738f', fontSize: 10, lineHeight: 16, marginTop: 26 },
})
