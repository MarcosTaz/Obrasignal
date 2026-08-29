import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { supabase } from '../lib/supabase';
import { api } from '../src/api';
import {
  activeEntitlement,
  BILLING_SUPPORTED,
  configureBilling,
  getCurrentOffering,
  hasProEntitlement,
  openWebPurchase,
  purchasePro,
  restoreBilling,
  WEB_BILLING_SUPPORTED,
  webPurchaseConfigured,
} from '../src/billing';

const COLORS = { bg: '#070C18', panel: '#10182B', line: '#253553', text: '#F3F6FF', muted: '#9BA8C0', blue: '#5E8BFF', green: '#6FE39A', red: '#FF8998' };

export default function BillingGate({ children }) {
  const [billing, setBilling] = useState({ configured: false, pro: false, plan: 'evaluation', expiresAt: null, managementUrl: null, evaluation: null, metrics: null });
  const [modal, setModal] = useState(false);
  const [offering, setOffering] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const refresh = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.user?.id) return;
    try {
      const result = await configureBilling(session.user.id);
      const info = result.customerInfo;
      let server = null;
      try { server = await api.billingStatus(); } catch (_) {}
      const entitlement = activeEntitlement(info);
      setBilling({
        configured: result.configured,
        pro: Boolean(server?.entitled) || hasProEntitlement(info),
        plan: server?.plan || (hasProEntitlement(info) ? 'pro' : 'evaluation'),
        expiresAt: server?.expires_at || entitlement?.expirationDate || server?.trial_ends_at || null,
        managementUrl: info?.managementURL || null,
        evaluation: server?.evaluation || null,
        metrics: server?.evaluation_metrics || null,
      });
    } catch (e) {
      setError(e?.message || 'Não foi possível verificar a subscrição.');
    }
  };

  useEffect(() => { refresh(); }, []);

  const openPaywall = async () => {
    setError(''); setModal(true);
    if (WEB_BILLING_SUPPORTED) return;
    if (!billing.configured || !BILLING_SUPPORTED) return;
    try { setOffering(await getCurrentOffering()); } catch (e) { setError(e?.message || 'Não foi possível carregar o plano.'); }
  };

  const buy = async () => {
    setBusy(true); setError('');
    try {
      const info = await purchasePro();
      if (!hasProEntitlement(info)) throw new Error('subscription_not_active');
      await refresh();
      setModal(false);
    } catch (e) {
      if (!e?.userCancelled) setError(e?.message || 'A compra não foi concluída.');
    } finally { setBusy(false); }
  };

  const buyWeb = async () => {
    setBusy(true); setError('');
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.user?.id) throw new Error('authentication_required');
      await openWebPurchase(session.user.id, session.user.email || null);
      // The hosted checkout is authoritative. Entitlement is never granted here;
      // after RevenueCat/provider convergence, a new app load/refresh reads server truth.
    } catch (e) {
      setError(e?.message || 'Não foi possível abrir a compra Web.');
      setBusy(false);
    }
  };

  const restore = async () => {
    setBusy(true); setError('');
    try { await restoreBilling(); await refresh(); } catch (e) { setError(e?.message || 'Não foi possível restaurar a subscrição.'); }
    finally { setBusy(false); }
  };

  const signOut = async () => {
    setBusy(true); setError('');
    try {
      const { error: signOutError } = await supabase.auth.signOut();
      if (signOutError) throw signOutError;
    } catch (e) {
      setError(e?.message || 'Não foi possível terminar a sessão. Tenta novamente.');
    } finally { setBusy(false); }
  };

  const packagePrice = WEB_BILLING_SUPPORTED
    ? 'Preço apresentado no checkout RevenueCat'
    : offering?.availablePackages?.find(p => p?.product?.identifier === 'obrasignal_pro_monthly')?.product?.priceString
      || offering?.availablePackages?.[0]?.product?.priceString
      || 'Preço apresentado pelo Google Play/App Store';
  const expired = billing.plan === 'expired';
  const webConfigured = WEB_BILLING_SUPPORTED && webPurchaseConfigured();

  return <View style={{ flex: 1 }}>
    {expired ? <View style={styles.blocked}><Text style={styles.blockedTitle}>A avaliação terminou</Text><Text style={styles.blockedText}>Para continuar a receber oportunidades personalizadas, ativa o ObraSignal Pro.</Text><Pressable disabled={busy} style={styles.primary} onPress={openPaywall}><Text style={styles.primaryText}>Ver subscrição</Text></Pressable><Pressable disabled={busy} onPress={signOut} style={styles.secondary}><Text style={styles.secondaryText}>Terminar sessão ou trocar de conta</Text></Pressable>{error ? <Text style={styles.error}>{error}</Text> : null}</View> : <>{billing.plan === 'evaluation' && billing.evaluation ? <View style={styles.evalCard}>
      <Text style={styles.evalTitle}>AVALIAÇÃO OBRASIGNAL</Text>
      <Text style={styles.evalText}>{billing.evaluation.status === 'EVALUATION_ACTIVE' ? `${billing.evaluation.days_remaining} dias restantes` : 'A janela de 21 dias ainda não começou'}</Text>
      <Text style={styles.evalMeta}>{billing.evaluation.activated_at ? `Começou em ${new Date(billing.evaluation.activated_at).toLocaleDateString()}` : 'Começa quando o perfil estiver pronto, houver dados de mercado e a primeira shortlist relevante for gerada.'}</Text>
      <Text style={styles.evalMeta}>{billing.metrics?.exposure_event_count || 0} exposições de valor registadas · sem estimativas económicas inventadas</Text>
    </View> : null}{children}</>}
    {!expired && <Pressable style={styles.planPill} onPress={openPaywall} accessibilityRole="button" accessibilityLabel="Plano ObraSignal"><Text style={styles.planText}>{billing.pro ? 'PRO' : billing.plan === 'evaluation' ? 'AVALIAÇÃO' : billing.plan === 'pilot' ? 'PILOT LEGADO' : 'PLANO'}</Text></Pressable>}
    <Modal visible={modal} transparent animationType="slide" onRequestClose={() => !busy && setModal(false)}>
      <View style={styles.overlay}><View style={styles.sheet}>
        <Text style={styles.eyebrow}>OBRASIGNAL PRO</Text>
        <Text style={styles.title}>O radar completo continua a trabalhar por ti.</Text>
        <Text style={styles.body}>A subscrição desbloqueia o acesso contínuo ao radar personalizado, scoring por empresa, alertas e workflow comercial.</Text>
        <View style={styles.priceBox}><Text style={styles.price}>{packagePrice}</Text><Text style={styles.priceNote}>{WEB_BILLING_SUPPORTED ? 'Subscrição recorrente · checkout Web associado à tua conta ObraSignal' : `Subscrição recorrente · cobrança pela ${Platform.OS === 'android' ? 'Google Play' : 'App Store'}`}</Text></View>
        <Text style={styles.terms}>A subscrição renova automaticamente até ser cancelada. O preço, período e condições apresentados pelo sistema de compra aplicam-se à compra.</Text>
        {BILLING_SUPPORTED && billing.configured ? <Pressable disabled={busy} style={styles.primary} onPress={buy}>{busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryText}>Subscrever</Text>}</Pressable> : null}
        {webConfigured ? <Pressable disabled={busy} style={styles.primary} onPress={buyWeb}>{busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryText}>Continuar para checkout Web</Text>}</Pressable> : null}
        {!((BILLING_SUPPORTED && billing.configured) || webConfigured) ? <Text style={styles.setup}>{WEB_BILLING_SUPPORTED ? 'A compra Web ainda não está configurada neste ambiente. É necessário definir o Web Purchase Link RevenueCat de produção/sandbox apropriado.' : BILLING_SUPPORTED ? 'Billing ainda não está configurado neste build. Define a chave pública RevenueCat antes do teste real.' : 'A subscrição não está disponível neste ambiente.'}</Text> : null}
        {BILLING_SUPPORTED ? <Pressable disabled={busy} onPress={restore} style={styles.secondary}><Text style={styles.secondaryText}>Restaurar compra</Text></Pressable> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable disabled={busy} onPress={() => setModal(false)} style={styles.close}><Text style={styles.secondaryText}>Fechar</Text></Pressable>
      </View></View>
    </Modal>
  </View>;
}

const styles = StyleSheet.create({
  evalCard:{margin:12,padding:12,borderRadius:12,backgroundColor:'#0D1B30',borderWidth:1,borderColor:'#355A8A'},
  evalTitle:{fontSize:10,fontWeight:'900',letterSpacing:1,color:COLORS.blue},
  evalText:{fontSize:15,fontWeight:'900',color:COLORS.text,marginTop:4},
  evalMeta:{fontSize:10,lineHeight:15,color:COLORS.muted,marginTop:3},
  planPill:{position:'absolute',right:72,top:14,paddingHorizontal:10,paddingVertical:6,borderRadius:999,backgroundColor:'#15295A',borderWidth:1,borderColor:'#315EA8'},
  planText:{fontSize:9,fontWeight:'900',letterSpacing:1,color:COLORS.text},
  blocked:{flex:1,alignItems:'center',justifyContent:'center',padding:28,backgroundColor:COLORS.bg},
  blockedTitle:{fontSize:24,fontWeight:'900',color:COLORS.text,textAlign:'center'},
  blockedText:{fontSize:13,lineHeight:20,color:COLORS.muted,textAlign:'center',marginTop:8,marginBottom:20},
  overlay:{flex:1,justifyContent:'flex-end',backgroundColor:'#00000099'},
  sheet:{backgroundColor:COLORS.panel,borderTopLeftRadius:24,borderTopRightRadius:24,borderWidth:1,borderColor:COLORS.line,padding:22,paddingBottom:30},
  eyebrow:{fontSize:10,fontWeight:'900',letterSpacing:1.2,color:COLORS.blue},
  title:{fontSize:24,fontWeight:'900',lineHeight:30,color:COLORS.text,marginTop:7},
  body:{fontSize:13,lineHeight:20,color:COLORS.muted,marginTop:8},
  priceBox:{marginTop:16,padding:14,borderRadius:14,backgroundColor:'#0D1B30',borderWidth:1,borderColor:'#355A8A'},
  price:{fontSize:25,fontWeight:'900',color:COLORS.text},
  priceNote:{fontSize:10,lineHeight:16,color:COLORS.muted,marginTop:4},
  terms:{fontSize:9,lineHeight:14,color:COLORS.muted,marginTop:10},
  primary:{marginTop:16,minHeight:46,borderRadius:11,backgroundColor:COLORS.blue,alignItems:'center',justifyContent:'center',paddingHorizontal:16},
  primaryText:{fontSize:13,fontWeight:'900',color:'#fff'},
  secondary:{marginTop:8,minHeight:42,alignItems:'center',justifyContent:'center'},
  secondaryText:{fontSize:12,fontWeight:'800',color:COLORS.blue},
  close:{marginTop:2,minHeight:36,alignItems:'center',justifyContent:'center'},
  setup:{fontSize:11,lineHeight:17,color:'#FFD66B',marginTop:12},
  error:{fontSize:11,lineHeight:17,color:COLORS.red,marginTop:10},
});
