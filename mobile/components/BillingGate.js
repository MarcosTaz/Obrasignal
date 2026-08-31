import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { supabase } from '../lib/supabase';
import { api } from '../src/api';
import {
  activeEntitlement,
  BILLING_PLATFORM_SUPPORTED,
  BILLING_RESTORE_SUPPORTED,
  billingConfigurationAvailable,
  configureBilling,
  getCurrentOffering,
  hasProEntitlement,
  purchasePro,
  restoreBilling,
} from '../src/billing';

const COLORS = { bg: '#07101c', panel: '#0d1929', panel2: '#101d30', line: '#263955', text: '#f5f8ff', muted: '#9eb0c9', blue: '#6c92ff', green: '#74e3a1', amber: '#f5ca72', red: '#ff8998' };
const SUPPORT_EMAIL = 'obrasignal.pt@gmail.com';

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
        pro: hasProEntitlement(info),
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
    if (!billing.configured || !billingConfigurationAvailable()) return;
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

  const restore = async () => {
    setBusy(true); setError('');
    try { await restoreBilling(); await refresh(); } catch (e) { setError(e?.message || 'Não foi possível restaurar a subscrição.'); }
    finally { setBusy(false); }
  };

  const packagePrice = offering?.availablePackages?.find(p => p?.product?.identifier === 'obrasignal_pro_monthly')?.product?.priceString
    || offering?.availablePackages?.[0]?.product?.priceString
    || 'Preço apresentado no checkout';
  const expired = billing.plan === 'expired';
  const web = Platform.OS === 'web';
  const checkoutReady = billing.configured && billingConfigurationAvailable();
  const billingChannel = web ? 'checkout Web seguro' : Platform.OS === 'android' ? 'Google Play' : 'App Store';
  const planLabel = billing.pro ? 'PRO' : billing.plan === 'evaluation' ? 'AVALIAÇÃO' : billing.plan === 'pilot' ? 'PILOT LEGADO' : 'PLANO';

  return <View style={styles.shell}>
    {!expired ? <View style={styles.planBar}>
      <View style={styles.planBarCopy}><Text style={styles.planKicker}>PLANO</Text><Text style={styles.planSummary}>{billing.pro ? 'ObraSignal Pro ativo' : billing.plan === 'evaluation' ? 'Avaliação ObraSignal' : 'Estado da subscrição'}</Text></View>
      <Pressable style={styles.planButton} onPress={openPaywall} accessibilityRole="button" accessibilityLabel="Plano ObraSignal"><Text style={styles.planText}>{planLabel}</Text><Text style={styles.planArrow}>›</Text></Pressable>
    </View> : null}
    {expired ? <View style={styles.blocked}><Text style={styles.blockedTitle}>A avaliação terminou</Text><Text style={styles.blockedText}>Para continuar a receber oportunidades personalizadas, ativa o ObraSignal Pro.</Text><Pressable style={styles.primary} onPress={openPaywall}><Text style={styles.primaryText}>Ver subscrição</Text></Pressable></View> : <>{billing.plan === 'evaluation' && billing.evaluation ? <View style={styles.evalCard}>
      <View><Text style={styles.evalTitle}>AVALIAÇÃO OBRASIGNAL</Text><Text style={styles.evalText}>{billing.evaluation.status === 'EVALUATION_ACTIVE' ? `${billing.evaluation.days_remaining} dias restantes` : 'A janela de 21 dias ainda não começou'}</Text></View>
      <View style={styles.evalMetaWrap}><Text style={styles.evalMeta}>{billing.evaluation.activated_at ? `Começou em ${new Date(billing.evaluation.activated_at).toLocaleDateString()}` : 'Começa depois do perfil, dados de mercado e primeira shortlist relevante.'}</Text><Text style={styles.evalMeta}>{billing.metrics?.exposure_event_count || 0} exposições de valor registadas</Text></View>
    </View> : null}{children}</>}
    <Modal visible={modal} transparent animationType="slide" onRequestClose={() => !busy && setModal(false)}>
      <View style={styles.overlay}><View style={styles.sheet}>
        <View style={styles.sheetHandle}/><Text style={styles.eyebrow}>OBRASIGNAL PRO</Text>
        <Text style={styles.title}>O radar completo continua a trabalhar por ti.</Text>
        <Text style={styles.body}>A subscrição mantém o radar personalizado, scoring por empresa, alertas e workflow comercial.</Text>
        <View style={styles.priceBox}><Text style={styles.price}>{packagePrice}</Text><Text style={styles.priceNote}>Subscrição recorrente · cobrança através de {billingChannel}</Text></View>
        <Text style={styles.terms}>{web ? 'Na Web, a compra usa RevenueCat Web Billing e o mesmo utilizador da tua conta para manter o acesso sincronizado entre plataformas.' : 'A subscrição renova automaticamente até ser cancelada. O preço, período e condições apresentados pela loja aplicam-se à compra.'}</Text>
        {checkoutReady ? <Pressable disabled={busy} style={styles.primary} onPress={buy}>{busy ? <ActivityIndicator color="#07101c" /> : <Text style={styles.primaryText}>Subscrever</Text>}</Pressable> : <View style={styles.setupBox}><Text style={styles.setupTitle}>{BILLING_PLATFORM_SUPPORTED ? 'Checkout ainda não configurado neste deployment' : 'Checkout indisponível nesta plataforma'}</Text><Text style={styles.setup}>O produto continua acessível durante a avaliação. Para ativação comercial imediata, fala connosco enquanto a configuração do checkout é concluída.</Text><Pressable onPress={()=>Linking.openURL(`mailto:${SUPPORT_EMAIL}?subject=Ativar%20ObraSignal%20Pro`)} style={styles.contact}><Text style={styles.contactText}>Pedir ativação →</Text></Pressable></View>}
        {BILLING_RESTORE_SUPPORTED ? <Pressable disabled={busy} onPress={restore} style={styles.secondary}><Text style={styles.secondaryText}>Restaurar compra</Text></Pressable> : null}
        {billing.pro && billing.managementUrl ? <Pressable onPress={()=>Linking.openURL(billing.managementUrl)} style={styles.secondary}><Text style={styles.secondaryText}>Gerir subscrição</Text></Pressable> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable disabled={busy} onPress={() => setModal(false)} style={styles.close}><Text style={styles.closeText}>Fechar</Text></Pressable>
      </View></View>
    </Modal>
  </View>;
}

const styles = StyleSheet.create({
  shell:{flex:1,backgroundColor:COLORS.bg},
  planBar:{minHeight:58,paddingHorizontal:18,paddingVertical:10,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:14,backgroundColor:'#091522',borderBottomWidth:1,borderBottomColor:'#1d2d43'},
  planBarCopy:{flex:1},planKicker:{fontSize:8,fontWeight:'900',letterSpacing:1.3,color:'#607795'},planSummary:{fontSize:12,fontWeight:'800',color:COLORS.text,marginTop:2},
  planButton:{flexDirection:'row',alignItems:'center',gap:7,paddingHorizontal:11,paddingVertical:7,borderRadius:999,backgroundColor:'#12233a',borderWidth:1,borderColor:'#29486d'},planText:{fontSize:9,fontWeight:'900',letterSpacing:1,color:'#b9caff'},planArrow:{fontSize:16,lineHeight:16,color:'#8eabff'},
  evalCard:{marginHorizontal:18,marginTop:12,padding:14,borderRadius:14,backgroundColor:'#0d1b2e',borderWidth:1,borderColor:'#24466d',flexDirection:'row',flexWrap:'wrap',justifyContent:'space-between',gap:12},
  evalTitle:{fontSize:9,fontWeight:'900',letterSpacing:1.2,color:COLORS.blue},evalText:{fontSize:15,fontWeight:'900',color:COLORS.text,marginTop:4},evalMetaWrap:{flexShrink:1,maxWidth:520},evalMeta:{fontSize:10,lineHeight:15,color:COLORS.muted,marginTop:2},
  blocked:{flex:1,alignItems:'center',justifyContent:'center',padding:28,backgroundColor:COLORS.bg},blockedTitle:{fontSize:26,fontWeight:'900',color:COLORS.text,textAlign:'center'},blockedText:{fontSize:13,lineHeight:20,color:COLORS.muted,textAlign:'center',marginTop:8,marginBottom:20,maxWidth:460},
  overlay:{flex:1,justifyContent:'flex-end',backgroundColor:'#000000aa'},sheet:{width:'100%',maxWidth:680,alignSelf:'center',backgroundColor:COLORS.panel,borderTopLeftRadius:24,borderTopRightRadius:24,borderWidth:1,borderColor:COLORS.line,padding:24,paddingBottom:30},sheetHandle:{width:40,height:4,borderRadius:999,backgroundColor:'#334861',alignSelf:'center',marginBottom:20},
  eyebrow:{fontSize:10,fontWeight:'900',letterSpacing:1.3,color:COLORS.blue},title:{fontSize:26,fontWeight:'900',lineHeight:32,color:COLORS.text,marginTop:7},body:{fontSize:13,lineHeight:20,color:COLORS.muted,marginTop:9,maxWidth:560},
  priceBox:{marginTop:18,padding:16,borderRadius:14,backgroundColor:COLORS.panel2,borderWidth:1,borderColor:'#2a476c'},price:{fontSize:25,fontWeight:'900',color:COLORS.text},priceNote:{fontSize:10,lineHeight:16,color:COLORS.muted,marginTop:4},terms:{fontSize:10,lineHeight:16,color:COLORS.muted,marginTop:12},
  primary:{marginTop:16,minHeight:48,borderRadius:11,backgroundColor:COLORS.text,alignItems:'center',justifyContent:'center',paddingHorizontal:16},primaryText:{fontSize:13,fontWeight:'900',color:COLORS.bg},secondary:{marginTop:8,minHeight:42,alignItems:'center',justifyContent:'center'},secondaryText:{fontSize:12,fontWeight:'800',color:'#91acff'},
  setupBox:{marginTop:16,padding:14,borderRadius:12,backgroundColor:'#171d28',borderWidth:1,borderColor:'#51442a'},setupTitle:{fontSize:11,fontWeight:'900',color:COLORS.amber},setup:{fontSize:11,lineHeight:17,color:'#c8b989',marginTop:5},contact:{alignSelf:'flex-start',marginTop:10},contactText:{fontSize:11,fontWeight:'900',color:'#9db4ff'},
  error:{fontSize:11,lineHeight:17,color:COLORS.red,marginTop:10},close:{marginTop:4,minHeight:38,alignItems:'center',justifyContent:'center'},closeText:{fontSize:12,fontWeight:'800',color:COLORS.muted},
});
