import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { supabase } from '../lib/supabase';
import { BRAND } from '../src/brand-palette.mjs';
import BrandLogo from './BrandLogo';

const COLORS = {
  bg:BRAND.paper,bgSoft:BRAND.fog,panel:'#FFFFFF',panelSoft:BRAND.fog,
  line:BRAND.fog,text:BRAND.ink,muted:BRAND.mineral,blue:BRAND.slate,
  blueSoft:BRAND.fog,green:'#21674A',red:'#A33131',copper:BRAND.copper,
};
const CONTACT = 'obrasignal.pt@gmail.com';

function Brand() {
  return <BrandLogo markSize={38} textSize={23}/>;
}

function Button({ children, onPress, secondary = false, disabled = false, compact = false }: any) {
  return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.button, secondary && styles.buttonSecondary, compact && styles.buttonCompact, pressed && styles.pressed, disabled && styles.disabled]}>
    <Text style={[styles.buttonText, secondary && styles.buttonSecondaryText]}>{children}</Text>
  </Pressable>;
}

function ProductPreview() {
  return <View style={styles.preview}>
    <View style={styles.previewTop}><View><Text style={styles.previewKicker}>RADAR</Text><Text style={styles.previewTitle}>Prioritised opportunities</Text></View><View style={styles.examplePill}><Text style={styles.exampleText}>ILLUSTRATION</Text></View></View>
    <View style={styles.metrics}>
      {[['12','open'],['7','relevant'],['3','priority']].map(([value,label]) => <View style={styles.metric} key={label}><Text style={styles.metricValue}>{value}</Text><Text style={styles.metricLabel}>{label}</Text></View>)}
    </View>
    <View style={styles.searchMock}><Text style={styles.searchIcon}>⌕</Text><Text style={styles.searchText}>Infrastructure · International</Text><View style={styles.filterPill}><Text style={styles.filterText}>75+</Text></View></View>
    <View style={styles.opportunity}>
      <View style={styles.opportunityTop}><Text style={styles.source}>OFFICIAL SOURCE</Text><Text style={styles.score}>92/100</Text></View>
      <Text style={styles.opportunityTitle}>Building renovation and technical installations</Text>
      <Text style={styles.opportunityMeta}>Published deadline · authority identified</Text>
      <Text style={styles.opportunityReason}>Matched to sector, location and typical project size.</Text>
      <Text style={styles.opportunityLink}>View opportunity →</Text>
    </View>
    <View style={styles.opportunityMuted}>
      <View style={styles.opportunityTop}><Text style={styles.source}>FONTE OFICIAL</Text><Text style={styles.scoreBlue}>84/100</Text></View>
      <Text style={styles.opportunityTitleSmall}>Facilities maintenance and technical systems</Text>
      <Text style={styles.opportunityMeta}>Transparent relevance · clear next step</Text>
    </View>
  </View>;
}

function Landing({ onLogin }: { onLogin: () => void }) {
  const { width } = useWindowDimensions();
  const wide = width >= 980;
  const medium = width >= 720;
  const askSample = () => Linking.openURL(`mailto:${CONTACT}?subject=ObraSignal%20sample%20request`);
  const proof = [
    ['01','Official sources','Trace each opportunity to its original publication.'],
    ['02','Explainable fit','Know why each opportunity matches your business.'],
    ['03','Next action','Keep your commercial workflow connected to evidence.'],
    ['04','Less noise','Prioritise what deserves your attention.'],
  ];
  const steps = [
    ['01','Set your profile','Capabilities, target markets and typical contract values.'],
    ['02','Review your radar','See prioritised opportunities against your criteria.'],
    ['03','Take action','Evaluate, add notes and follow decisions.'],
  ];
  return <ScrollView style={styles.page} contentContainerStyle={styles.pageContent}>
    <View style={styles.shell}>
      <View style={styles.nav}><Brand/><Text style={[styles.navDescriptor, !medium && styles.hide]}>Discover · Evaluate · Act</Text><Pressable accessibilityRole="button" onPress={onLogin} style={styles.loginButton}><Text style={styles.loginText}>Sign in</Text></Pressable></View>

      <View style={[styles.hero, !wide && styles.heroStack]}>
        <View style={[styles.heroCopy, !wide && styles.fullWidth]}>
          <Text style={styles.eyebrow}>GLOBAL PROCUREMENT INTELLIGENCE</Text>
          <Text style={[styles.heroTitle, !medium && styles.heroTitleSmall]}>Find opportunities worth pursuing.</Text>
          <Text style={styles.heroBody}>ObraSignal helps organisations discover public tenders, understand their relevance and turn fragmented research into confident decisions.</Text>
          <View style={[styles.heroActions, !medium && styles.actionsStack]}><Button onPress={askSample}>Request a sample</Button><Button secondary onPress={() => Linking.openURL(`mailto:${CONTACT}?subject=ObraSignal%20access%20request`)}>Request access</Button></View>
          <Text style={styles.microcopy}>Official sources. Explainable relevance. Better decisions.</Text>
        </View>
        <View style={[styles.heroVisual, !wide && styles.fullWidth]}><ProductPreview/></View>
      </View>

      <View style={[styles.proofRow, !wide && styles.stack]}>{proof.map(([n,title,copy]) => <View style={styles.proofItem} key={n}><Text style={styles.proofNumber}>{n}</Text><View style={styles.proofCopy}><Text style={styles.proofTitle}>{title}</Text><Text style={styles.proofBody}>{copy}</Text></View></View>)}</View>

      <View style={styles.section}>
        <View style={styles.sectionLabel}><Text style={styles.sectionIndex}>01</Text><View style={styles.sectionLine}/><Text style={styles.sectionLabelText}>HOW IT WORKS</Text></View>
        <View style={[styles.sectionIntro, !wide && styles.stack]}><Text style={[styles.sectionTitle, !medium && styles.sectionTitleSmall]}>A decision workflow, not another tender directory.</Text><Text style={styles.sectionCopy}>Spend less time searching and keep each decision tied to original evidence.</Text></View>
        <View style={[styles.cardRow, !wide && styles.stack]}>{steps.map(([n,title,copy]) => <View style={styles.stepCard} key={n}><Text style={styles.stepNumber}>{n}</Text><Text style={styles.stepTitle}>{title}</Text><Text style={styles.stepCopy}>{copy}</Text></View>)}</View>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionLabel}><Text style={styles.sectionIndex}>02</Text><View style={styles.sectionLine}/><Text style={styles.sectionLabelText}>PLATFORM</Text></View>
        <View style={[styles.featureRow, !wide && styles.stack]}>
          <View style={styles.featureLarge}><Text style={styles.cardKicker}>RADAR</Text><Text style={styles.featureTitle}>Clarity before volume.</Text><Text style={styles.featureCopy}>Research, relevance and workflow in one place.</Text><View style={styles.miniRadar}><Text style={styles.miniTitle}>Municipal facilities renovation</Text><Text style={styles.goodScore}>91/100</Text></View></View>
          <View style={styles.featureCard}><Text style={styles.cardKicker}>EXPLAINABILITY</Text><Text style={styles.featureTitleSmall}>Know why it matters.</Text><Text style={styles.featureCopy}>A score supports your judgement; it does not replace it.</Text></View>
          <View style={styles.featureCard}><Text style={styles.cardKicker}>WORKFLOW</Text><Text style={styles.featureTitleSmall}>From discovery to outcome.</Text><Text style={styles.featureCopy}>Track status and notes alongside the opportunity.</Text><View style={styles.statuses}>{['New','Review','Prepare','Submitted'].map((x,i)=><View key={x} style={[styles.status, i===1 && styles.statusOn]}><Text style={styles.statusText}>{x}</Text></View>)}</View></View>
        </View>
      </View>

      <View style={[styles.trustPanel, !wide && styles.stack]}><View style={styles.trustCopy}><Text style={styles.trustTitle}>ObraSignal advises. Official sources prevail.</Text><Text style={styles.trustBody}>Always confirm deadlines, requirements, documents and contacts against the official notice.</Text></View><View style={styles.checklist}>{['Source traceability','Visible deadlines','Fit rationale','Workflow status','Internal notes'].map(x=><View style={styles.checkRow} key={x}><Text style={styles.check}>✓</Text><Text style={styles.checkText}>{x}</Text></View>)}</View></View>

      <View style={[styles.finalCta, !wide && styles.stack]}><View style={styles.finalCopy}><Text style={styles.finalEyebrow}>DISCOVER WHAT MATTERS TO YOUR BUSINESS</Text><Text style={[styles.finalTitle, !medium && styles.sectionTitleSmall]}>Start with a focused sample. Decide with evidence.</Text></View><View style={[styles.finalActions, !medium && styles.fullWidth]}><Button onPress={askSample}>Request a sample</Button><Button secondary onPress={onLogin}>Existing customer</Button></View></View>
      <View style={[styles.footer, !medium && styles.stack]}><Brand/><View style={styles.footerCopy}><Text style={styles.footerText}>International outlook · available markets depend on official sources</Text><Text style={styles.footerText}>After sign-in: private data export and privacy controls.</Text></View><Text style={styles.footerText}>{CONTACT}</Text></View>
    </View>
  </ScrollView>;
}

function AuthForm({ onBack }: { onBack: () => void }) {
  const { width } = useWindowDimensions();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const redirectTo = useMemo(() => Platform.OS === 'web' && typeof window !== 'undefined' ? window.location.origin + window.location.pathname : undefined, []);

  const submit = async () => {
    setError(''); setMessage('');
    const normalizedEmail=email.trim().toLowerCase();
    if (!normalizedEmail || !normalizedEmail.includes('@')) { setError('Enter a valid email address.'); return; }
    if (password.length < 6) { setError('Use at least six password characters.'); return; }
    setBusy(true);
    try {
      const {error:authError}=await supabase.auth.signInWithPassword({email:normalizedEmail,password});
      if(authError) throw authError;
    } catch (error: any) {
      setError('Sign-in was not completed. If the authentication service is unavailable, try again later.');
    }
    finally { setBusy(false); }
  };

  const reset = async () => {
    setError(''); setMessage('');
    const normalizedEmail=email.trim().toLowerCase();
    if (!normalizedEmail || !normalizedEmail.includes('@')) { setError('Enter a valid account email first.'); return; }
    setBusy(true);
    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(normalizedEmail, redirectTo ? { redirectTo } : undefined);
      if (resetError) throw resetError;
      setMessage('Recovery instructions requested. Check your email if the provider confirms delivery.');
    } catch (e: any) { setError(e?.message || 'Password recovery is unavailable.'); }
    finally { setBusy(false); }
  };

  return <View style={styles.authPage}><View style={[styles.authShell, width < 560 && styles.authShellSmall]}>
    {Platform.OS === 'web' ? <Pressable accessibilityRole="button" onPress={onBack} style={styles.backButton}><Text style={styles.backText}>← Back to website</Text></Pressable> : null}
    <View style={styles.authBrand}><Brand/><View style={styles.accessPill}><Text style={styles.accessText}>ACESSO</Text></View></View>
    <Text style={styles.authTitle}>Welcome back.</Text>
    <Text style={styles.authSubtitle}>Sign in with an existing account. New accounts are invitation-only.</Text>
    <Text style={styles.fieldLabel}>EMAIL</Text><TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" placeholder="name@company.com" placeholderTextColor="#607590" style={styles.input}/>
    <View style={styles.passwordRow}><Text style={styles.fieldLabel}>PASSWORD</Text><Pressable accessibilityRole="button" onPress={reset} disabled={busy}><Text style={styles.forgot}>Reset password</Text></Pressable></View>
    <TextInput value={password} onChangeText={setPassword} secureTextEntry autoComplete="current-password" placeholder="••••••••" placeholderTextColor="#607590" style={styles.input}/>
    {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}{message ? <Text style={styles.success}>{message}</Text> : null}
    <Pressable accessibilityRole="button" disabled={busy} onPress={submit} style={({pressed})=>[styles.authPrimary, pressed&&styles.pressed, busy&&styles.disabled]}>{busy ? <ActivityIndicator color={COLORS.bg}/> : <Text style={styles.authPrimaryText}>Sign in</Text>}</Pressable>
    <Pressable accessibilityRole="button" disabled={busy} onPress={()=>Linking.openURL(`mailto:${CONTACT}?subject=ObraSignal%20access%20request`)}><Text style={styles.switchText}>Need access? Request an invitation</Text></Pressable>
    <Text style={styles.authTrust}>Official tender documents remain authoritative. ObraSignal supports, but does not replace, your assessment.</Text>
  </View></View>;
}

export default function AuthScreen() {
  const [showAuth, setShowAuth] = useState(Platform.OS !== 'web');
  if (!showAuth) return <Landing onLogin={()=>setShowAuth(true)}/>;
  return <AuthForm onBack={()=>setShowAuth(false)}/>;
}

const styles = StyleSheet.create({
  page:{flex:1,backgroundColor:COLORS.bg},pageContent:{flexGrow:1},shell:{width:'100%',maxWidth:1680,alignSelf:'center',paddingHorizontal:24},fullWidth:{width:'100%'},stack:{flexDirection:'column'},hide:{display:'none'},
  nav:{minHeight:78,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:18,borderBottomWidth:1,borderBottomColor:COLORS.line},brand:{color:COLORS.text,fontSize:20,fontWeight:'800',letterSpacing:-.7},brandAccent:{color:BRAND.mineral},navDescriptor:{color:COLORS.muted,fontSize:10,fontWeight:'800',letterSpacing:1.1},loginButton:{minHeight:38,justifyContent:'center',paddingHorizontal:13},loginText:{color:COLORS.text,fontSize:12,fontWeight:'800'},
  hero:{flexDirection:'row',alignItems:'center',gap:52,paddingVertical:74},heroStack:{flexDirection:'column',alignItems:'stretch',gap:38,paddingVertical:48},heroCopy:{flex:1},heroVisual:{flex:1},eyebrow:{color:BRAND.mineral,fontSize:10,fontWeight:'900',letterSpacing:1.5},heroTitle:{color:COLORS.text,fontSize:58,lineHeight:62,fontWeight:'900',letterSpacing:-2.1,marginTop:20,maxWidth:620},heroTitleSmall:{fontSize:40,lineHeight:44,letterSpacing:-1.3},heroBody:{color:COLORS.muted,fontSize:16,lineHeight:26,maxWidth:590,marginTop:24},heroActions:{flexDirection:'row',alignItems:'center',gap:10,marginTop:30},actionsStack:{flexDirection:'column',alignItems:'stretch'},button:{minHeight:48,paddingHorizontal:18,borderRadius:10,backgroundColor:COLORS.copper,borderWidth:1,borderColor:COLORS.copper,alignItems:'center',justifyContent:'center'},buttonCompact:{minHeight:40,paddingHorizontal:13},buttonSecondary:{backgroundColor:'transparent',borderColor:BRAND.mineral},buttonText:{color:COLORS.text,fontSize:12,fontWeight:'900'},buttonSecondaryText:{color:COLORS.text},pressed:{opacity:.84},disabled:{opacity:.58},microcopy:{color:COLORS.muted,fontSize:10,lineHeight:16,marginTop:17},
  preview:{width:'100%',backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:18,padding:18},previewTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:12},previewKicker:{color:COLORS.muted,fontSize:9,fontWeight:'900',letterSpacing:1.5},previewTitle:{color:COLORS.text,fontSize:16,fontWeight:'900',marginTop:4},examplePill:{paddingHorizontal:8,paddingVertical:5,borderRadius:999,borderWidth:1,borderColor:COLORS.line},exampleText:{color:COLORS.muted,fontSize:8,fontWeight:'900'},metrics:{flexDirection:'row',gap:8,paddingVertical:14},metric:{flex:1,minWidth:0,backgroundColor:COLORS.panel,borderRadius:10,padding:12,borderWidth:1,borderColor:COLORS.line},metricValue:{color:COLORS.text,fontSize:20,fontWeight:'900'},metricLabel:{color:COLORS.muted,fontSize:9,marginTop:3},searchMock:{minHeight:42,flexDirection:'row',alignItems:'center',borderRadius:10,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.bgSoft,paddingHorizontal:12,marginBottom:10,gap:7},searchIcon:{color:COLORS.blue,fontSize:15},searchText:{color:COLORS.muted,fontSize:11,flex:1},filterPill:{backgroundColor:COLORS.blueSoft,paddingHorizontal:8,paddingVertical:4,borderRadius:999},filterText:{color:COLORS.text,fontSize:9,fontWeight:'800'},opportunity:{backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:12,padding:14,marginTop:9},opportunityMuted:{backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:12,padding:14,marginTop:9},opportunityTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:10},source:{color:COLORS.muted,fontSize:9,fontWeight:'800',letterSpacing:1},score:{color:COLORS.green,fontSize:12,fontWeight:'900'},scoreBlue:{color:COLORS.blue,fontSize:12,fontWeight:'900'},opportunityTitle:{color:COLORS.text,fontSize:14,lineHeight:19,fontWeight:'800',marginTop:9},opportunityTitleSmall:{color:COLORS.text,fontSize:12,lineHeight:17,fontWeight:'800',marginTop:8},opportunityMeta:{color:COLORS.muted,fontSize:10,marginTop:7},opportunityReason:{color:COLORS.muted,fontSize:10,lineHeight:15,marginTop:8},opportunityLink:{color:COLORS.blue,fontSize:10,fontWeight:'800',marginTop:10},
  proofRow:{flexDirection:'row',gap:12,borderTopWidth:1,borderBottomWidth:1,borderColor:COLORS.line,paddingVertical:18},proofItem:{flex:1,minWidth:0,flexDirection:'row',gap:12,padding:12},proofNumber:{color:COLORS.muted,fontSize:10,fontWeight:'900'},proofCopy:{flex:1},proofTitle:{color:COLORS.text,fontWeight:'800',fontSize:13},proofBody:{color:COLORS.muted,fontSize:10,lineHeight:16,marginTop:5},
  section:{paddingTop:96},sectionLabel:{flexDirection:'row',alignItems:'center',gap:10,marginBottom:24},sectionIndex:{color:COLORS.blue,fontSize:10,fontWeight:'900'},sectionLine:{width:28,height:1,backgroundColor:COLORS.line},sectionLabelText:{color:COLORS.muted,fontSize:10,fontWeight:'900',letterSpacing:1.4},sectionIntro:{flexDirection:'row',justifyContent:'space-between',alignItems:'flex-end',gap:36,marginBottom:36},sectionTitle:{flex:1,color:COLORS.text,fontSize:38,lineHeight:43,letterSpacing:-1.25,fontWeight:'900',maxWidth:690},sectionTitleSmall:{fontSize:30,lineHeight:35,letterSpacing:-.8},sectionCopy:{color:COLORS.muted,fontSize:13,lineHeight:21,maxWidth:390},cardRow:{flexDirection:'row',gap:14},stepCard:{flex:1,minWidth:0,backgroundColor:COLORS.bgSoft,borderWidth:1,borderColor:COLORS.line,borderRadius:16,padding:24,minHeight:210},stepNumber:{color:COLORS.blue,fontSize:11,fontWeight:'900'},stepTitle:{color:COLORS.text,fontSize:20,fontWeight:'900',marginTop:30},stepCopy:{color:COLORS.muted,fontSize:13,lineHeight:20,marginTop:12},
  featureRow:{flexDirection:'row',gap:14,alignItems:'stretch'},featureLarge:{flex:1.5,minWidth:0,backgroundColor:COLORS.bgSoft,borderWidth:1,borderColor:COLORS.line,borderRadius:18,padding:26},featureCard:{flex:1,minWidth:0,backgroundColor:COLORS.bgSoft,borderWidth:1,borderColor:COLORS.line,borderRadius:18,padding:26},cardKicker:{color:COLORS.muted,fontSize:10,fontWeight:'900',letterSpacing:1.3},featureTitle:{color:COLORS.text,fontSize:30,lineHeight:35,fontWeight:'900',letterSpacing:-.8,marginTop:24},featureTitleSmall:{color:COLORS.text,fontSize:22,lineHeight:28,fontWeight:'900',letterSpacing:-.4,marginTop:24},featureCopy:{color:COLORS.muted,fontSize:13,lineHeight:21,marginTop:14},miniRadar:{flexDirection:'row',justifyContent:'space-between',gap:10,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel,borderRadius:12,padding:15,marginTop:28},miniTitle:{color:COLORS.text,fontSize:11,fontWeight:'700',flex:1},goodScore:{color:COLORS.green,fontWeight:'900',fontSize:12},statuses:{flexDirection:'row',flexWrap:'wrap',gap:7,marginTop:28},status:{borderWidth:1,borderColor:COLORS.line,paddingHorizontal:9,paddingVertical:6,borderRadius:999},statusOn:{backgroundColor:COLORS.blueSoft,borderColor:COLORS.blue},statusText:{color:COLORS.muted,fontSize:9,fontWeight:'800'},
  trustPanel:{marginTop:96,flexDirection:'row',alignItems:'center',gap:48,backgroundColor:COLORS.bgSoft,borderWidth:1,borderColor:COLORS.line,borderRadius:20,padding:40},trustCopy:{flex:1},trustTitle:{color:COLORS.text,fontSize:32,lineHeight:38,fontWeight:'900',letterSpacing:-.8},trustBody:{color:COLORS.muted,fontSize:13,lineHeight:21,marginTop:17,maxWidth:640},checklist:{flex:1,gap:11},checkRow:{flexDirection:'row',alignItems:'center',gap:10},check:{color:COLORS.green,fontSize:14,fontWeight:'900'},checkText:{color:COLORS.text,fontSize:12,fontWeight:'700'},
  finalCta:{marginTop:96,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:40,borderTopWidth:1,borderBottomWidth:1,borderColor:COLORS.line,paddingVertical:58},finalCopy:{flex:1},finalEyebrow:{color:COLORS.muted,fontSize:10,fontWeight:'900',letterSpacing:1.2},finalTitle:{color:COLORS.text,fontSize:34,lineHeight:40,fontWeight:'900',letterSpacing:-.9,marginTop:14,maxWidth:660},finalActions:{gap:10,minWidth:210},footer:{minHeight:120,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:20},footerCopy:{flex:1,alignItems:'center',gap:4},footerText:{color:COLORS.muted,fontSize:10,lineHeight:15,textAlign:'center'},
  authPage:{flex:1,minHeight:'100%',backgroundColor:COLORS.bg,alignItems:'center',justifyContent:'center',padding:24},authShell:{width:'100%',maxWidth:500,backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:20,padding:34},authShellSmall:{padding:22},backButton:{alignSelf:'flex-start',marginBottom:28},backText:{color:COLORS.muted,fontSize:12,fontWeight:'700'},authBrand:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:14},accessPill:{borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.bgSoft,borderRadius:999,paddingHorizontal:10,paddingVertical:6},accessText:{color:COLORS.muted,fontSize:9,fontWeight:'800'},authTitle:{color:COLORS.text,fontSize:34,lineHeight:40,fontWeight:'900',letterSpacing:-.8,marginTop:34},authSubtitle:{color:COLORS.muted,fontSize:14,lineHeight:22,marginTop:11,marginBottom:30},fieldLabel:{color:COLORS.text,fontSize:10,fontWeight:'900',marginBottom:8,letterSpacing:.8},passwordRow:{flexDirection:'row',justifyContent:'space-between',alignItems:'center'},forgot:{color:COLORS.blue,fontSize:10,fontWeight:'700',marginBottom:8},input:{height:52,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel,borderRadius:11,paddingHorizontal:14,color:COLORS.text,marginBottom:16},error:{color:COLORS.red,fontSize:11,lineHeight:17,marginBottom:10},success:{color:COLORS.green,fontSize:11,lineHeight:17,marginBottom:10},authPrimary:{height:52,borderRadius:11,alignItems:'center',justifyContent:'center',backgroundColor:COLORS.copper,marginTop:4,marginBottom:18},authPrimaryText:{color:COLORS.text,fontSize:14,fontWeight:'900'},switchText:{textAlign:'center',color:COLORS.blue,fontWeight:'700',fontSize:12},authTrust:{textAlign:'center',color:COLORS.muted,fontSize:10,lineHeight:16,marginTop:26},
});
