import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { supabase } from '../lib/supabase';
import { api } from '../src/api';
import {
  activeEntitlement,
  BILLING_SUPPORTED,
  configureBilling,
  getCurrentOffering,
  purchasePro,
  restoreBilling,
} from '../src/billing';

const COLORS = { bg: '#070C18', panel: '#10182B', line: '#253553', text: '#F3F6FF', muted: '#9BA8C0', blue: '#5E8BFF', green: '#6FE39A', red: '#FF8998' };
const SERVER_PLANS = new Set(['evaluation', 'pro', 'expired', 'pilot']);

export default function BillingGate({ children }) {
  const [billing, setBilling] = useState({ authority: 'loading', configured: false, pro: false, plan: null, expiresAt: null, managementUrl: null, evaluation: null, metrics: null });
  const [modal, setModal] = useState(false);
  const [offering, setOffering] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const refresh = async () => {
    setBilling(current => ({ ...current, authority: 'loading', pro: false }));
    setError('');
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.user?.id) {
      setBilling(current => ({ ...current, authority: 'unavailable', pro: false, plan: null }));
      setError('Não foi possível validar o estado da subscrição.');
      return;
    }
    try {
      // Server projection is the access authority. Store/RevenueCat state is
      // purchase UX metadata only and must never become an access fallback.
      const server = await api.billingStatus();
      if (!server?.plan || !SERVER_PLANS.has(server.plan)) throw new Error('invalid_server_billing_state');

      let result = { configured: false, customerInfo: null };
      try {
        result = await configureBilling(session.user.id);
      } catch (_) {
        // Store availability must not weaken a valid server decision. Purchase
        // controls stay unavailable, while access remains server-authoritative.
      }
      const info = result.customerInfo;
      const entitlement = activeEntitlement(info);
      setBilling({
        authority: 'ready',
        configured: result.configured,
        pro: server.plan === 'pro',
        plan: server.plan,
        expiresAt: server.expires_at || server.trial_ends_at || entitlement?.expirationDate || null,
        managementUrl: info?.managementURL || null,
        evaluation: server.evaluation || null,
        metrics: server.evaluation_metrics || null,
      });
    } catch (e) {
      setBilling(current => ({ ...current, authority: 'unavailable', pro: false, plan: null }));
      setError('Não foi possível validar o estado da subscrição.');
    }
  };

  useEffect(() => { refresh(); }, []);

  const openPaywall = async () => {
    setError(''); setModal(true);
    if (!billing.configured || !BILLING_SUPPORTED) return;
    try { setOffering(await getCurrentOffering()); } catch (e) { setError(e?.message || 'Não foi possível carregar o plano.'); }
  };

  const buy = async () => {
    setBusy(true); setError('');
    try {
      await purchasePro();
      // A successful store purchase is not sufficient authority. Re-read the
      // server projection before changing access; webhook lag therefore fails safe.
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
    || 'Preço apresentado pelo Google Play/App Store';

  if (billing.authority !== 'ready') {
    return <View style={styles.blocked}>
      <Text style={styles.blockedTitle}>{billing.authority === 'loading' ? 'A validar a subscrição…' : 'Subscrição não validada'}</Text>
      <Text style={styles.blockedText}>{billing.authority === 'loading' ? 'Estamos a confirmar o estado atual da tua conta.' : 'Não foi possível validar o estado da subscrição. O acesso fica protegido até o servidor confirmar o estado atual.'}</Text>
      {billing.authority === 'loading' ? <ActivityIndicator color={COLORS.blue} /> : <Pressable style={styles.primary} onPress={refresh}><Text style={styles.primaryText}>Tentar novamente</Text></Pressable>}
    </View>;
  }

  const expired = billing.plan === 'expired';

  return <View style={{ flex: 1 }}>
    {expired ? <View style={styles.blocked}><Text style={styles.blockedTitle}>A avaliação terminou</Text><Text style={styles.blockedText}>Para continuar a receber oportunidades personalizadas, ativa o ObraSignal Pro.</Text><Pressable style={styles.primary} onPress={openPaywall}><Text style={styles.primaryText}>Ver subscrição</Text></Pressable></View> : <>{billing.plan === 'evaluation' && billing.evaluation ? <View style={styles.evalCard}>
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
        <View style={styles.priceBox}><Text style={styles.price}>{packagePrice}</Text><Text style={styles.priceNote}>Subscrição recorrente · cobrança pela {Platform.OS === 'android' ? 'Google Play' : 'App Store'}</Text></View>
        <Text style={styles.terms}>A subscrição renova automaticamente até ser cancelada. O preço, período e condições apresentados pelo sistema de compra da loja aplicam-se à compra. Podes gerir ou cancelar a subscrição na loja.</Text>
        {BILLING_SUPPORTED && billing.configured ? <Pressable disabled={busy} style={styles.primary} onPress={buy}>{busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryText}>Subscrever</Text>}</Pressable> : <Text style={styles.setup}>{BILLING_SUPPORTED ? 'Billing ainda não está configurado neste build. Define a chave pública RevenueCat antes do teste real.' : 'A subscrição é activada através da Google Play/App Store na aplicação nativa. A versão Web permite consultar o estado do plano, mas não processa compras.'}</Text>}
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
