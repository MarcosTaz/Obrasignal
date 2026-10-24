import React, { useEffect, useMemo, useRef, useState } from 'react'
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
import {contactLink,getContact,CONTACT_UNVERIFIED_MESSAGE} from '../src/public-contacts.mjs'
import {FONT_BODY,FONT_DISPLAY} from '../src/typography.mjs'
import {isRecoveryReturn} from '../src/auth-recovery-boundary.mjs'

const TRANSLATE_ELEMENT_ID = 'obrasignal-google-translate'
const TRANSLATE_SCRIPT_ID = 'obrasignal-google-translate-script'
const SUPPORT_EMAIL=getContact('support')
const PRIVACY_EMAIL=getContact('privacy')
const LEGAL_EMAIL=getContact('legal')
const openContact=(role,subject)=>{const link=contactLink(role,subject);if(link)Linking.openURL(link)}

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

const LEGAL_CONTENT={
 privacy:{
  title:'Privacy & data protection',updated:'Policy under review · 23 October 2026',
  sections:[
   ['Account data','The service processes the email and identity reference supplied by the authentication provider, company profiles, preferences, commercial decisions, workflow statuses and private account notes. Public tender notices originate from external official sources.'],
   ['Purposes','Account data is used for identity verification, tenant isolation, opportunity relevance, workflow persistence, support, security and applicable commercial account administration.'],
   ['Private visitor measurement','The public website may measure page visits, referrers or campaigns, device characteristics, language, time zone and approximate location supplied by infrastructure. Raw IP addresses are not stored for this purpose; rotating technical tokens are used for aggregated traffic metrics.'],
   ['External providers','The deployed application currently uses Supabase for identity; its availability is independently monitored. Where configured, RevenueCat and payment providers may process billing status. Google Translate is loaded only after the visitor explicitly enables it.'],
   ['Export and deletion','Authenticated account privacy controls allow a request for export of canonical private account data and deletion. Identity sessions and external billing deletion are not claimed complete without third-party confirmation.'],
   ['Security and retention','Account records are retained according to operational, security, audit and legal requirements. Service access is separated by account and company; retention and applicable rights require independent legal review.'],
   ['Privacy contact',PRIVACY_EMAIL||CONTACT_UNVERIFIED_MESSAGE],
  ],
 },
 terms:{
  title:'Terms of use',updated:'Terms under review · 23 October 2026',
  sections:[
   ['Purpose','ObraSignal is a procurement intelligence and commercial decision-support service. It is not a contracting authority or official procurement portal.'],
   ['Authority of original notices','Always verify deadlines, requirements, documents, eligibility, contacts and tender status with the original authority. Scoring and derived insights are advisory only.'],
   ['Accounts and acceptable use','Users must keep credentials confidential and may not access another customer’s data, bypass protections, automate harmful traffic or misuse the service.'],
   ['Availability','Official sources, networks, authentication providers and other dependencies may become unavailable. An unavailable source must not be interpreted as no available tenders.'],
   ['Subscriptions','Automatic checkout is offered only if its payment channel is genuinely configured. Product operational billing statuses must not be mistaken for proof of external payment settlement.'],
   ['Service contact',LEGAL_EMAIL||SUPPORT_EMAIL||CONTACT_UNVERIFIED_MESSAGE],
  ],
 },
}

function PublicLegalBar() {
  const [legal, setLegal] = useState(null)
  const content = legal ? LEGAL_CONTENT[legal] : null
  return <>
    <View style={styles.publicLegalBar} accessibilityLabel="Privacy, terms and support">
      <BrandLogo inverse markSize={24} textSize={15}/>
      <View style={styles.publicLegalActions}>
        <Pressable accessibilityRole="button" accessibilityLabel="Privacy" onPress={() => setLegal('privacy')} style={styles.publicLegalButton}><Text style={styles.publicLegalText}>Privacy</Text></Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Terms of use" onPress={() => setLegal('terms')} style={styles.publicLegalButton}><Text style={styles.publicLegalText}>Terms</Text></Pressable>
        {SUPPORT_EMAIL?<Pressable accessibilityRole="button" accessibilityLabel="Contact support" onPress={() => openContact('support','ObraSignal support')} style={styles.publicLegalButton}><Text style={styles.publicLegalText}>Support</Text></Pressable>:<Text style={styles.publicLegalText}>Support contact pending verification</Text>}
      </View>
    </View>
    <Modal visible={Boolean(content)} transparent={false} animationType="slide" onRequestClose={() => setLegal(null)}>
      <View style={styles.legalModal}>
        <View style={styles.legalHeader}><View style={styles.legalHeaderCopy}><Text style={styles.legalTitle}>{content?.title}</Text><Text style={styles.legalUpdated}>{content?.updated}</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Close legal information" onPress={() => setLegal(null)} style={styles.legalClose}><Text style={styles.legalCloseText}>Close</Text></Pressable></View>
        <ScrollView contentContainerStyle={styles.legalContent}>
          {content?.sections.map(([title, body]) => <View key={title} style={styles.legalSection}><Text style={styles.legalHeading}>{title}</Text><Text style={styles.legalBody}>{body}</Text></View>)}
          {SUPPORT_EMAIL?<Pressable accessibilityRole="button" accessibilityLabel="Contact ObraSignal" onPress={() => openContact('support','ObraSignal support')} style={styles.legalContact}><Text style={styles.legalContactText}>{SUPPORT_EMAIL}</Text></Pressable>:<Text style={styles.legalBody}>{CONTACT_UNVERIFIED_MESSAGE}</Text>}
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
        new TranslateElement({ pageLanguage: 'en', autoDisplay: false, multilanguagePage: true }, TRANSLATE_ELEMENT_ID)
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

  return <View style={styles.translateArea} accessibilityLabel="Page translation">
    {!enabled
      ? <Pressable accessibilityRole="button" accessibilityLabel="Enable translation" onPress={() => setEnabled(true)} style={({pressed}) => [styles.translateButton, pressed && styles.translatePressed]}><Text style={styles.translateButtonText}>Translate ▾</Text></Pressable>
      : <><Text style={styles.translateLabel}>Translator</Text>{available ? <View nativeID={TRANSLATE_ELEMENT_ID} style={styles.translateWidget}/> : <Text style={styles.translateUnavailable}>unavailable</Text>}</>}
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

  const date = useMemo(() => new Intl.DateTimeFormat('en-GB', {
    weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
  }).format(now), [now.getFullYear(), now.getMonth(), now.getDate()])
  const time = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(now)

  const signOut = async () => {
    if (signingOut) return
    setSigningOut(true)
    setSignOutError('')
    try {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    } catch (_) {
      setSignOutError('Unable to sign out safely. Please retry.')
    } finally { setSigningOut(false) }
  }

  return <View style={styles.sessionBar} accessibilityLabel="Date, time, translation and session">
    <View style={styles.dateTime}>
      <Text style={styles.date}>{date}</Text>
      <View style={styles.timePill}><Text style={styles.time}>{time}</Text></View>
      <WebTranslator/>
    </View>
    <View style={styles.sessionActions}>
      {signOutError ? <Text accessibilityRole="alert" style={styles.sessionError}>{signOutError}</Text> : null}
      <Pressable disabled={signingOut} accessibilityRole="button" accessibilityLabel="Sign out" onPress={signOut} style={({pressed}) => [styles.logoutButton, pressed && styles.translatePressed, signingOut && styles.disabled]}>
        <Text style={styles.logoutText}>{signingOut ? 'Signing out…' : 'Sign out'}</Text>
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
  const [passwordRecovery, setPasswordRecovery] = useState(() => Platform.OS === 'web' && typeof window !== 'undefined' && isRecoveryReturn(window.location.href))
  const recoveryRef = useRef(passwordRecovery)
  const finishRecovery = () => { recoveryRef.current=false; clearRecoveryUrl(); setPasswordRecovery(false) }

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
          // A recovery JWT is NOT a customer-workspace login. Quarantine all
          // account-scoped caches and skip private tenant binding and backend reads.
          if (signedIn && recoveryRef.current) {
            await withTimeout(storage.bindPrivateTenant(null), PRIVATE_TENANT_BIND_TIMEOUT_MS, 'Recovery cache quarantine timed out')
            if (!active || currentGeneration !== generation) return
            setAuthState(nextState)
            setTenantStatus('ready')
            return
          }
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
      if (event === 'PASSWORD_RECOVERY') { recoveryRef.current=true; setPasswordRecovery(true) }
    })
    return () => data?.subscription?.unsubscribe()
  }, [])

  if (authState.status === 'loading' || tenantStatus === 'loading') {
    return <View style={styles.loading}><BrandLogo markSize={42} textSize={25}/><ActivityIndicator size="small" color={BRAND.slate}/><Text style={styles.message}>Restoring your session…</Text></View>
  }
  if (tenantStatus === 'error') {
    return <View style={styles.loading}><BrandLogo markSize={42} textSize={25}/><Text style={styles.error}>Unable to verify private session storage.</Text></View>
  }
  if (passwordRecovery && authState.status !== 'signed-in') {
    // Never offer updateUser without an actual provider-issued recovery session.
    return <View style={styles.loading}><BrandLogo inverse markSize={50} textSize={29}/>
      <Text style={styles.message}>This recovery link is expired, invalid or the identity provider is unavailable. No private workspace has been opened.</Text>
      <Pressable accessibilityRole="button" onPress={finishRecovery} style={styles.legalContact}><Text style={styles.legalContactText}>Return to sign in</Text></Pressable>
    </View>
  }
  if (authState.status !== 'signed-in') {
    if (Platform.OS !== 'web') return <AuthScreen />
    return <View style={styles.publicShell}><View style={styles.publicContent}><AuthScreen /></View><PublicLegalBar /></View>
  }

  if (passwordRecovery) {
    return <PasswordRecovery
      onComplete={finishRecovery}
      onCancel={finishRecovery}
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
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, backgroundColor: '#06111D' },
  brand: { fontFamily:FONT_BODY,fontSize: 25, fontWeight: '800', letterSpacing: -0.8, color: '#F3F8FE' }, blue: { color: '#A4C0D5' },
  message: { color: '#A4C0D5', fontFamily:FONT_BODY,fontSize: 12 }, error: { color: '#A33131', fontFamily:FONT_BODY,fontSize: 12, textAlign: 'center', paddingHorizontal: 24 },
  publicShell: { flex: 1, minHeight: 0, backgroundColor: '#06111D' }, publicContent: { flex: 1, minHeight: 0 },
  publicLegalBar: { minHeight: 42, paddingHorizontal: 18, paddingVertical: 7, borderTopWidth: 1, borderTopColor: '#284761', backgroundColor: '#06111D', flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  publicLegalBrand: { color: '#A4C0D5', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '900', letterSpacing: 0.4 }, publicLegalActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  publicLegalButton: { minHeight: 28, justifyContent: 'center', paddingHorizontal: 9, borderRadius: 999, borderWidth: 1, borderColor: '#284761', backgroundColor: '#152F47' }, publicLegalText: { color: '#DFEAF3', fontFamily:FONT_BODY,fontSize: 9, fontWeight: '800' },
  legalModal: { flex: 1, backgroundColor: '#06111D' }, legalHeader: { paddingHorizontal: 20, paddingVertical: 17, borderBottomWidth: 1, borderBottomColor: '#284761', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 14 }, legalHeaderCopy: { flex: 1 }, legalTitle: { color: '#F3F8FE', fontFamily:FONT_DISPLAY,fontSize: 25, fontWeight: '900' }, legalUpdated: { color: '#A4C0D5', fontFamily:FONT_BODY,fontSize: 10, marginTop: 4 }, legalClose: { minHeight: 36, justifyContent: 'center', paddingHorizontal: 12, borderRadius: 9, borderWidth: 1, borderColor: BRAND.mineral }, legalCloseText: { color: '#F3F8FE', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '800' },
  legalContent: { width: '100%', maxWidth: 860, alignSelf: 'center', padding: 22, paddingBottom: 60, gap: 14 }, legalSection: { padding: 17, borderRadius: 13, borderWidth: 1, borderColor: '#284761', backgroundColor: '#10263A' }, legalHeading: { color: '#F3F8FE', fontFamily:FONT_BODY,fontSize: 14, fontWeight: '900' }, legalBody: { color: '#DFEAF3', fontFamily:FONT_BODY,fontSize: 12, lineHeight: 19, marginTop: 7 }, legalContact: { alignSelf: 'flex-start', marginTop: 4, paddingHorizontal: 13, paddingVertical: 10, borderRadius: 9, backgroundColor: '#152F47' }, legalContactText: { color: '#DFEAF3', fontFamily:FONT_BODY,fontSize: 11, fontWeight: '900' },
  webShell: { flex: 1, minHeight: 0, backgroundColor: '#06111D' }, webContent: { flex: 1, minHeight: 0 },
  sessionBar: { minHeight: 44, paddingHorizontal: 18, paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: '#284761', backgroundColor: '#06111D', flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  dateTime: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 },
  date: { color: '#A4C0D5', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  timePill: { borderWidth: 1, borderColor: '#284761', backgroundColor: '#152F47', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4 },
  time: { color: '#F3F8FE', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '800', fontVariant: ['tabular-nums'] },
  translateArea: { minHeight: 28, flexDirection: 'row', alignItems: 'center', gap: 7, borderLeftWidth: 1, borderLeftColor: '#284761', paddingLeft: 10 },
  translateButton: { borderWidth: 1, borderColor: '#284761', backgroundColor: '#152F47', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  translatePressed: { opacity: 0.75 }, translateButtonText: { color: '#F3F8FE', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '800' },
  translateLabel: { color: '#A4C0D5', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '800' }, translateWidget: { minWidth: 128, minHeight: 24, justifyContent: 'center' }, translateUnavailable: { color: '#A4C0D5', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '700' },
  sessionActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 8 },
  sessionError: { color: '#A33131', fontFamily:FONT_BODY,fontSize: 9, fontWeight: '700' },
  logoutButton: { minHeight: 30, justifyContent: 'center', paddingHorizontal: 11, borderRadius: 999, borderWidth: 1, borderColor: '#A33131', backgroundColor: '#FFF0F1' },
  logoutText: { color: '#A33131', fontFamily:FONT_BODY,fontSize: 10, fontWeight: '800' }, disabled: { opacity: 0.55 },
})