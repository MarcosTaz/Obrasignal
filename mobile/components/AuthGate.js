import React, { useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Linking, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import AccountPrivacyControls from './AccountPrivacyControls'
import AuthScreen from './AuthScreen'
import BrandLogo from './BrandLogo';
import BillingGate from './BillingGate'
import PasswordRecovery from './PasswordRecovery'
import { supabase } from '../lib/supabase'
import { ensureBackendReady } from '../src/api'
import { trackTraffic } from '../src/analytics'
import { authSession } from '../src/authSession'
import { storage } from '../src/storage'
import { BRAND } from '../src/brand-palette.mjs'

const TRANSLATE_ELEMENT_ID = 'obrasignal-google-translate'
const TRANSLATE_SCRIPT_ID = 'obrasignal-google-translate-script'
const SUPPORT_EMAIL = 'obrasignal.pt@gmail.com'

const PRIVATE_TENANT_BIND_TIMEOUT_MS = 4500

function withTimeout(promise, ms, message) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(message)), ms)
    Promise.resolve(promise).then(
      value => { clearTimeout(timer); resolve(value) },
      error => { clearTimeout(timer); reject(error) },
    )
  })
}

const LEGAL_CONTENT = {
  privacy: {
    title: 'Privacidade',
    updated: 'Atualizado em 31 de agosto de 2026',
    sections: [
      ['Que dados tratamos', 'A conta usa o email e a identidade técnica do fornecedor de autenticação. O produto guarda, por conta, o perfil da empresa, preferências, decisões, estados de workflow, notas e outros dados necessários para prestar o serviço. Os anúncios e concursos provenientes de fontes públicas não são dados privados da conta.'],
      ['Para que usamos os dados', 'Usamos os dados da conta para autenticação, isolamento entre clientes, personalização do Radar, persistência do trabalho, suporte, segurança e, quando aplicável, ativação e gestão comercial do plano. Não apresentamos dados sintéticos como dados reais.'],
      ['Medição privada de acesso', 'Medimos de forma privada a utilização de obrasignal.com para perceber tráfego e desempenho comercial: página visitada, origem/referrer e campanha quando existam, dispositivo, idioma, fuso horário e, quando a infraestrutura a fornece, geografia aproximada como país, região ou cidade. Não guardamos o endereço IP bruto e não criamos cookie nem identificador em localStorage para esta medição. Os identificadores técnicos usados para estimar visitantes são HMAC rotativos e destinam-se apenas a métricas agregadas, segurança e melhoria do serviço. A contagem não é apresentada publicamente no site.'],
      ['Fornecedores e fronteiras externas', 'A autenticação é prestada através de Supabase. Quando a faturação automática estiver configurada, o estado de compra/subscrição pode ser processado através de RevenueCat e do respetivo canal de pagamento. O Google Translate só é carregado quando o utilizador ativa voluntariamente o tradutor na sessão Web.'],
      ['Exportação e eliminação', 'Depois de entrar, “Conta e privacidade” permite preparar uma exportação dos dados canónicos atuais do produto e pedir a eliminação dos dados privados. A aplicação não declara concluída a eliminação de identidade, sessões ou faturação externa sem confirmação desses fornecedores.'],
      ['Segurança e retenção', 'Aplicamos separação por conta e controlos de autenticação no serviço. Conservamos dados enquanto forem necessários para operar a conta, preservar integridade/auditoria do serviço e cumprir obrigações aplicáveis; pedidos de eliminação são tratados pelos controlos autenticados e pelo suporte. A telemetria de acesso é minimizada e não conserva IP bruto.'],
      ['Contacto', `Para questões de privacidade, correções ou suporte: ${SUPPORT_EMAIL}.`],
    ],
  },
  terms: {
    title: 'Termos de utilização',
    updated: 'Atualizado em 31 de agosto de 2026',
    sections: [
      ['O serviço', 'O ObraSignal é um radar comercial e ferramenta de apoio à decisão sobre oportunidades de contratação pública. Prioriza e organiza informação; não é uma entidade adjudicante, portal oficial de contratação nem substitui os documentos do procedimento.'],
      ['Fonte oficial e decisões', 'Prazos, requisitos, documentos, elegibilidade, contactos, valores e estado do procedimento devem ser confirmados na fonte oficial antes de qualquer decisão comercial. Sinais, normalizações ou inferências do ObraSignal não transformam informação desconhecida em facto.'],
      ['Conta e utilização', 'O utilizador é responsável por manter as credenciais seguras e por usar o serviço apenas de forma lícita. Não é permitido tentar aceder a dados de outra conta, contornar controlos de acesso, abusar da infraestrutura ou automatizar tráfego de forma prejudicial.'],
      ['Disponibilidade e fontes', 'A disponibilidade e atualidade podem ser afetadas por fontes públicas, rede, autenticação ou outros fornecedores externos. Uma indisponibilidade de fonte deve ser apresentada como tal e não como ausência válida de oportunidades.'],
      ['Avaliação, plano e faturação', 'O estado comercial apresentado dentro do produto é a referência operacional. O checkout automático só é oferecido quando o canal de pagamento correto estiver efetivamente configurado; caso contrário, a ativação é assistida e nenhum botão deve simular uma compra. Condições comerciais específicas acordadas por escrito prevalecem sobre esta descrição geral.'],
      ['Cancelamento e suporte', `Quando existir gestão automática de subscrição, o produto apresenta o respetivo caminho de gestão. Para ativação assistida, cancelamento, faturação, dados ou suporte, contacte ${SUPPORT_EMAIL}.`],
    ],
  },
}

function PublicLegalBar() {
  const [legal, setLegal] = useState(null)
  const content = legal ? LEGAL_CONTENT[legal] : null
  return <>
    <View style={styles.publicLegalBar} accessibilityLabel="Privacidade, termos e suporte">
      <Text style={styles.publicLegalBrand}>ObraSignal</Text>
      <View style={styles.publicLegalActions}>
        <Pressable accessibilityRole="button" accessibilityLabel="Privacidade" onPress={() => setLegal('privacy')} style={styles.publicLegalButton}><Text style={styles.publicLegalText}>Privacidade</Text></Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Termos de utilização" onPress={() => setLegal('terms')} style={styles.publicLegalButton}><Text style={styles.publicLegalText}>Termos</Text></Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Contactar suporte" onPress={() => Linking.openURL(`mailto:${SUPPORT_EMAIL}?subject=Suporte%20ObraSignal`)} style={styles.publicLegalButton}><Text style={styles.publicLegalText}>Suporte</Text></Pressable>
      </View>
    </View>
    <Modal visible={Boolean(content)} transparent={false} animationType="slide" onRequestClose={() => setLegal(null)}>
      <View style={styles.legalModal}>
        <View style={styles.legalHeader}><View style={styles.legalHeaderCopy}><Text style={styles.legalTitle}>{content?.title}</Text><Text style={styles.legalUpdated}>{content?.updated}</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Fechar informação legal" onPress={() => setLegal(null)} style={styles.legalClose}><Text style={styles.legalCloseText}>Fechar</Text></Pressable></View>
        <ScrollView contentContainerStyle={styles.legalContent}>
          {content?.sections.map(([title, body]) => <View key={title} style={styles.legalSection}><Text style={styles.legalHeading}>{title}</Text><Text style={styles.legalBody}>{body}</Text></View>)}
          <Pressable accessibilityRole="button" accessibilityLabel="Contactar ObraSignal" onPress={() => Linking.openURL(`mailto:${SUPPORT_EMAIL}`)} style={styles.legalContact}><Text style={styles.legalContactText}>{SUPPORT_EMAIL}</Text></Pressable>
        </ScrollView>
      </View>
    </Modal>
  </>
}

function WebTranslator() {
  const [enabled, setEnabled] = useState(false)
  const [available, setAvailable] = useState(true)

  useEffect(() => {
    if (!enabled || typeof window === 'undefined' || typeof document === 'undefined') return undefined
    let active = true

    const mountTranslator = () => {
      if (!active) return
      const host = document.getElementById(TRANSLATE_ELEMENT_ID)
      const TranslateElement = window.google?.translate?.TranslateElement
      if (!host || !TranslateElement || host.querySelector('.goog-te-combo')) return
      try {
        new TranslateElement({ pageLanguage: 'pt', autoDisplay: false, multilanguagePage: true }, TRANSLATE_ELEMENT_ID)
        setAvailable(true)
      } catch (_) { setAvailable(false) }
    }

    window.obrasignalGoogleTranslateInit = mountTranslator
    if (window.google?.translate?.TranslateElement) {
      mountTranslator()
    } else if (!document.getElementById(TRANSLATE_SCRIPT_ID)) {
      const script = document.createElement('script')
      script.id = TRANSLATE_SCRIPT_ID
      script.async = true
      script.src = 'https://translate.google.com/translate_a/element.js?cb=obrasignalGoogleTranslateInit'
      script.onerror = () => { if (active) setAvailable(false) }
      document.head.appendChild(script)
    }
    return () => { active = false }
  }, [enabled])

  return <View style={styles.translateArea} accessibilityLabel="Tradutor da página">
    {!enabled
      ? <Pressable accessibilityRole="button" accessibilityLabel="Ativar tradutor" onPress={() => setEnabled(true)} style={({pressed}) => [styles.translateButton, pressed && styles.translatePressed]}><Text style={styles.translateButtonText}>Traduzir ▾</Text></Pressable>
      : <><Text style={styles.translateLabel}>Tradutor</Text>{available ? <View nativeID={TRANSLATE_ELEMENT_ID} style={styles.translateWidget}/> : <Text style={styles.translateUnavailable}>indisponível</Text>}</>}
  </View>
}

function WebSessionBar() {
  const [now, setNow] = useState(() => new Date())
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState('')

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const date = useMemo(() => new Intl.DateTimeFormat('pt-PT', {
    weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
  }).format(now), [now.getFullYear(), now.getMonth(), now.getDate()])
  const time = new Intl.DateTimeFormat('pt-PT', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(now)

  const signOut = async () => {
    if (signingOut) return
    setSigningOut(true)
    setSignOutError('')
    try {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    } catch (_) {
      setSignOutError('Não foi possível terminar a sessão. Tenta novamente.')
    } finally { setSigningOut(false) }
  }

  return <View style={styles.sessionBar} accessibilityLabel="Data, hora, tradutor e sessão">
    <View style={styles.dateTime}>
      <Text style={styles.date}>{date}</Text>
      <View style={styles.timePill}><Text style={styles.time}>{time}</Text></View>
      <WebTranslator/>
    </View>
    <View style={styles.sessionActions}>
      {signOutError ? <Text accessibilityRole="alert" style={styles.sessionError}>{signOutError}</Text> : null}
      <Pressable disabled={signingOut} accessibilityRole="button" accessibilityLabel="Terminar sessão" onPress={signOut} style={({pressed}) => [styles.logoutButton, pressed && styles.translatePressed, signingOut && styles.disabled]}>
        <Text style={styles.logoutText}>{signingOut ? 'A sair…' : 'Terminar sessão'}</Text>
      </Pressable>
    </View>
  </View>
}

function clearRecoveryUrl() {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || typeof document === 'undefined') return
  try { window.history.replaceState({}, document.title, window.location.pathname) } catch (_) {}
}

export default function AuthGate({ children }) {
  const [authState, setAuthState] = useState(authSession.getState())
  const [tenantStatus, setTenantStatus] = useState('loading')
  const [passwordRecovery, setPasswordRecovery] = useState(() => Platform.OS === 'web' && typeof window !== 'undefined' && /(?:[?#&])type=recovery(?:[&#]|$)/.test(window.location.href))

  useEffect(() => {
    let active = true
    let generation = 0
    let trackedAccountId = null
    let bindingQueue = Promise.resolve()

    const update = (nextState) => {
      if (!active) return
      const currentGeneration = ++generation
      setTenantStatus('loading')
      bindingQueue = bindingQueue
        .catch(() => {})
        .then(async () => {
          const signedIn = nextState.status === 'signed-in'
          const accountId = signedIn ? nextState.session?.user?.id : null
          if (signedIn && !accountId) throw new Error('Authenticated session is missing user.id')
          await withTimeout(storage.bindPrivateTenant(accountId), PRIVATE_TENANT_BIND_TIMEOUT_MS, 'Private tenant binding timed out')
          if (!active || currentGeneration !== generation) return
          setAuthState(nextState)
          setTenantStatus('ready')
          if (signedIn) {
            ensureBackendReady().catch(() => {})
            if (accountId !== trackedAccountId) {
              trackedAccountId = accountId
              trackTraffic('authenticated_session').catch(() => {})
            }
          } else {
            trackedAccountId = null
          }
        })
        .catch(() => {
          if (!active || currentGeneration !== generation) return
          if (nextState.status !== 'signed-in') {
            setAuthState(nextState)
            setTenantStatus('ready')
            return
          }
          setTenantStatus('error')
        })
    }

    const unsubscribe = authSession.subscribe(update)
    authSession.start().then(update).catch(() => update({ status: 'signed-out', session: null }))
    return () => { active = false; generation += 1; unsubscribe() }
  }, [])

  useEffect(() => {
    // Supabase emits PASSWORD_RECOVERY after exchanging a valid recovery link.
    // Keep this listener independent from the generic session coordinator so a
    // temporary recovery session never falls through into private product data.
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') setPasswordRecovery(true)
    })
    return () => data?.subscription?.unsubscribe()
  }, [])

  if (authState.status === 'loading' || tenantStatus === 'loading') {
    return <View style={styles.loading}><BrandLogo markSize={42} textSize={25}/><ActivityIndicator size="small" color={BRAND.slate}/><Text style={styles.message}>A recuperar a sessão…</Text></View>
  }
  if (tenantStatus === 'error') {
    return <View style={styles.loading}><BrandLogo markSize={42} textSize={25}/><Text style={styles.error}>Não foi possível validar o armazenamento privado desta sessão.</Text></View>
  }
  if (authState.status !== 'signed-in') {
    if (Platform.OS !== 'web') return <AuthScreen />
    return <View style={styles.publicShell}><View style={styles.publicContent}><AuthScreen /></View><PublicLegalBar /></View>
  }

  if (passwordRecovery) {
    return <PasswordRecovery
      onComplete={() => { clearRecoveryUrl(); setPasswordRecovery(false) }}
      onCancel={() => { clearRecoveryUrl(); setPasswordRecovery(false) }}
    />
  }

  // Privacy ownership deliberately sits outside billing: a customer can inspect,
  // export or request deletion of account data even when evaluation access expires.
  return <AccountPrivacyControls>
    <BillingGate>
      {Platform.OS === 'web'
        ? <View style={styles.webShell}><WebSessionBar/><View style={styles.webContent}>{children}</View></View>
        : children}
    </BillingGate>
  </AccountPrivacyControls>
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, backgroundColor: BRAND.paper },
  brand: { fontSize: 25, fontWeight: '800', letterSpacing: -0.8, color: BRAND.ink }, blue: { color: BRAND.mineral },
  message: { color: BRAND.mineral, fontSize: 12 }, error: { color: '#A33131', fontSize: 12, textAlign: 'center', paddingHorizontal: 24 },
  publicShell: { flex: 1, minHeight: 0, backgroundColor: BRAND.paper }, publicContent: { flex: 1, minHeight: 0 },
  publicLegalBar: { minHeight: 42, paddingHorizontal: 18, paddingVertical: 7, borderTopWidth: 1, borderTopColor: BRAND.fog, backgroundColor: BRAND.paper, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  publicLegalBrand: { color: BRAND.mineral, fontSize: 10, fontWeight: '900', letterSpacing: 0.4 }, publicLegalActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  publicLegalButton: { minHeight: 28, justifyContent: 'center', paddingHorizontal: 9, borderRadius: 999, borderWidth: 1, borderColor: BRAND.fog, backgroundColor: BRAND.fog }, publicLegalText: { color: BRAND.slate, fontSize: 9, fontWeight: '800' },
  legalModal: { flex: 1, backgroundColor: BRAND.paper }, legalHeader: { paddingHorizontal: 20, paddingVertical: 17, borderBottomWidth: 1, borderBottomColor: BRAND.fog, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 14 }, legalHeaderCopy: { flex: 1 }, legalTitle: { color: BRAND.ink, fontSize: 25, fontWeight: '900' }, legalUpdated: { color: BRAND.mineral, fontSize: 10, marginTop: 4 }, legalClose: { minHeight: 36, justifyContent: 'center', paddingHorizontal: 12, borderRadius: 9, borderWidth: 1, borderColor: BRAND.mineral }, legalCloseText: { color: BRAND.ink, fontSize: 10, fontWeight: '800' },
  legalContent: { width: '100%', maxWidth: 860, alignSelf: 'center', padding: 22, paddingBottom: 60, gap: 14 }, legalSection: { padding: 17, borderRadius: 13, borderWidth: 1, borderColor: BRAND.fog, backgroundColor: '#FFFFFF' }, legalHeading: { color: BRAND.ink, fontSize: 14, fontWeight: '900' }, legalBody: { color: BRAND.slate, fontSize: 12, lineHeight: 19, marginTop: 7 }, legalContact: { alignSelf: 'flex-start', marginTop: 4, paddingHorizontal: 13, paddingVertical: 10, borderRadius: 9, backgroundColor: BRAND.fog }, legalContactText: { color: BRAND.slate, fontSize: 11, fontWeight: '900' },
  webShell: { flex: 1, minHeight: 0, backgroundColor: BRAND.paper }, webContent: { flex: 1, minHeight: 0 },
  sessionBar: { minHeight: 44, paddingHorizontal: 18, paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: BRAND.fog, backgroundColor: BRAND.paper, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  dateTime: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 },
  date: { color: BRAND.mineral, fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  timePill: { borderWidth: 1, borderColor: BRAND.fog, backgroundColor: BRAND.fog, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4 },
  time: { color: BRAND.ink, fontSize: 10, fontWeight: '800', fontVariant: ['tabular-nums'] },
  translateArea: { minHeight: 28, flexDirection: 'row', alignItems: 'center', gap: 7, borderLeftWidth: 1, borderLeftColor: BRAND.fog, paddingLeft: 10 },
  translateButton: { borderWidth: 1, borderColor: BRAND.fog, backgroundColor: BRAND.fog, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  translatePressed: { opacity: 0.75 }, translateButtonText: { color: BRAND.ink, fontSize: 10, fontWeight: '800' },
  translateLabel: { color: BRAND.mineral, fontSize: 10, fontWeight: '800' }, translateWidget: { minWidth: 128, minHeight: 24, justifyContent: 'center' }, translateUnavailable: { color: BRAND.mineral, fontSize: 10, fontWeight: '700' },
  sessionActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 8 },
  sessionError: { color: '#A33131', fontSize: 9, fontWeight: '700' },
  logoutButton: { minHeight: 30, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 999, borderWidth: 1, borderColor: '#A33131', backgroundColor: '#FFF0F1' },
  logoutText: { color: '#A33131', fontSize: 10, fontWeight: '800' }, disabled: { opacity: 0.55 },
})