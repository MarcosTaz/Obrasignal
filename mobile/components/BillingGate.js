import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { supabase } from '../lib/supabase';
import { api } from '../src/api';
import {
  activeEntitlement,
  BILLING_RESTORE_SUPPORTED,
  billingConfigurationAvailable,
  configureBilling,
  getCurrentOffering,
  packagePriceString,
  proPackage,
  purchasePro,
  restoreBilling,
  webPurchaseLinkConfigurationAvailable,
  webPurchaseUrl,
} from '../src/billing';

const COLORS = { bg: '#07111C', panel: '#0D1A29', panel2: '#101F31', line: '#22364F', text: '#F4F7FB', muted: '#9BAABD', blue: '#5F8DF7', green: '#72DFA1', amber: '#EFCB78', red: '#FF8B9A' };
const SUPPORT_EMAIL = 'obrasignal.pt@gmail.com';
const SERVER_PLANS = new Set(['evaluation', 'pro', 'expired', 'pilot']);

export default function BillingGate({ children }) {
  const [billing, setBilling] = useState({ authority: 'loading', configured: false, appUserId: null, pro: false, plan: null, expiresAt: null, managementUrl: null, evaluation: null, metrics: null });
  const [modal, setModal] = useState(false);
  const [offering, setOffering] = useState(null);
  const [offeringLoading, setOfferingLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const refresh = async () => {
    setBilling(current => ({ ...current, authority: 'loading', pro: false }));
    setError('');
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.user?.id) {
      setBilling(current => ({ ...current, authority: 'unavailable', pro: false, plan: null }));
      setError('Não foi possível validar a tua sessão e o estado do plano.');
      return null;
    }
    try {
      // The server projection is the only access authority. RevenueCat/store
      // state is purchase UX metadata and never an access fallback.
      const server = await api.billingStatus();
      if (!server?.plan || !SERVER_PLANS.has(server.plan)) throw new Error('invalid_server_billing_state');

      let result = { configured: false, customerInfo: null };
      try { result = await configureBilling(session.user.id); } catch (_) {}
      const info = result.customerInfo;
      const entitlement = activeEntitlement(info);
      setBilling({
        authority: 'ready',
        configured: result.configured,
        appUserId: session.user.id,
        pro: server.plan === 'pro',
        plan: server.plan,
        expiresAt: server.expires_at || server.trial_ends_at || entitlement?.expirationDate || null,
        managementUrl: info?.managementURL || server.management_url || null,
        evaluation: server.evaluation || null,
        metrics: server.evaluation_metrics || null,
      });
      return server;
    } catch (_) {
      setBilling(current => ({ ...current, authority: 'unavailable', pro: false, plan: null }));
      setError('Não foi possível validar o estado atual do plano. O acesso fica protegido até o servidor responder.');
      return null;
    }
  };

  useEffect(() => { refresh(); }, []);

  const openPaywall = async () => {
    setError('');
    setOffering(null);
    setModal(true);
    if (!billing.configured || !billingConfigurationAvailable()) return;
    setOfferingLoading(true);
    try {
      const nextOffering = await getCurrentOffering();
      setOffering(nextOffering);
      if (!proPackage(nextOffering) && !webPurchaseLinkConfigurationAvailable()) setError('O plano ObraSignal Pro ainda não está publicado no checkout.');
    } catch (e) {
      if (!webPurchaseLinkConfigurationAvailable()) setError(e?.message || 'Não foi possível carregar o plano.');
    } finally {
      setOfferingLoading(false);
    }
  };

  const buy = async () => {
    setBusy(true);
    setError('');
    try {
      const sdkPackage = proPackage(offering);
      const hostedUrl = Platform.OS === 'web' ? webPurchaseUrl(billing.appUserId) : null;
      if (Platform.OS === 'web' && !sdkPackage && hostedUrl) {
        await Linking.openURL(hostedUrl);
        return;
      }
      await purchasePro();
      const server = await refresh();
      if (server?.plan === 'pro') setModal(false);
      else setError('A compra foi recebida, mas a ativação ainda está a sincronizar. Atualiza o estado dentro de alguns segundos.');
    } catch (e) {
      if (!e?.userCancelled) setError(e?.message || 'A compra não foi concluída.');
    } finally { setBusy(false); }
  };

  const restore = async () => {
    setBusy(true);
    setError('');
    try {
      await restoreBilling();
      const server = await refresh();
      if (server?.plan !== 'pro') setError('A restauração terminou, mas o servidor ainda não confirmou uma subscrição ativa.');
    } catch (e) {
      setError(e?.message || 'Não foi possível restaurar a subscrição.');
    } finally { setBusy(false); }
  };

  const selectedPackage = proPackage(offering);
  const web = Platform.OS === 'web';
  const hostedCheckoutReady = web && Boolean(webPurchaseUrl(billing.appUserId));
  const sdkCheckoutConfigured = billing.configured && billingConfigurationAvailable();
  const sdkCheckoutReady = sdkCheckoutConfigured && Boolean(selectedPackage);
  const checkoutConfigured = sdkCheckoutConfigured || hostedCheckoutReady;
  const checkoutReady = sdkCheckoutReady || hostedCheckoutReady;
  const packagePrice = packagePriceString(selectedPackage) || (hostedCheckoutReady ? 'Preço apresentado no checkout seguro' : 'Preço apresentado no checkout');
  const billingChannel = web ? 'checkout Web seguro (RevenueCat / Stripe)' : Platform.OS === 'android' ? 'Google Play' : 'App Store';

  if (billing.authority !== 'ready') {
    return <View style={styles.blocked}>
      <Text style={styles.blockedTitle}>{billing.authority === 'loading' ? 'A validar o acesso…' : 'Não foi possível validar o acesso'}</Text>
      <Text style={styles.blockedText}>{billing.authority === 'loading' ? 'Estamos a confirmar o estado atual da tua conta.' : 'Por segurança, o ObraSignal não mostra dados privados sem confirmação do servidor.'}</Text>
      {billing.authority === 'loading'
        ? <ActivityIndicator color={COLORS.blue}/>
        : <Pressable style={styles.primary} onPress={refresh}><Text style={styles.primaryText}>Tentar novamente</Text></Pressable>}
    </View>;
  }

  const expired = billing.plan === 'expired';
  const planLabel = billing.pro ? 'PRO' : billing.plan === 'evaluation' ? 'AVALIAÇÃO' : billing.plan === 'pilot' ? 'PILOT' : 'PLANO';

  return <View style={styles.shell}>
    {!expired ? <View style={styles.planBar}>
      <View style={styles.planBarCopy}><Text style={styles.planKicker}>PLANO</Text><Text style={styles.planSummary}>{billing.pro ? 'ObraSignal Pro ativo' : billing.plan === 'evaluation' ? 'Avaliação ObraSignal' : 'Estado da subscrição'}</Text></View>
      <Pressable style={styles.planButton} onPress={openPaywall} accessibilityRole="button" accessibilityLabel="Plano ObraSignal"><Text style={styles.planText}>{planLabel}</Text><Text style={styles.planArrow}>›</Text></Pressable>
    </View> : null}

    {expired
      ? <View style={styles.blocked}><Text style={styles.blockedTitle}>A avaliação terminou</Text><Text style={styles.blockedText}>Para continuar a receber oportunidades personalizadas, ativa o ObraSignal Pro.</Text><Pressable style={styles.primary} onPress={openPaywall}><Text style={styles.primaryText}>Ver subscrição</Text></Pressable></View>
      : <>{billing.plan === 'evaluation' && billing.evaluation ? <View style={styles.evalCard}>
          <View><Text style={styles.evalTitle}>AVALIAÇÃO OBRASIGNAL</Text><Text style={styles.evalText}>{billing.evaluation.status === 'EVALUATION_ACTIVE' ? `${billing.evaluation.days_remaining} dias restantes` : 'A janela de 21 dias ainda não começou'}</Text></View>
          <View style={styles.evalMetaWrap}><Text style={styles.evalMeta}>{billing.evaluation.activated_at ? `Começou em ${new Date(billing.evaluation.activated_at).toLocaleDateString('pt-PT')}` : 'Começa depois do perfil, dados de mercado e primeira shortlist relevante.'}</Text><Text style={styles.evalMeta}>{billing.metrics?.exposure_event_count || 0} exposições de valor registadas</Text></View>
        </View> : null}{children}</>}

    <Modal visible={modal} transparent animationType="slide" onRequestClose={() => !busy && setModal(false)}>
      <View style={styles.overlay}><View style={styles.sheet}>
        <View style={styles.sheetHandle}/><Text style={styles.eyebrow}>OBRASIGNAL PRO</Text>
        <Text style={styles.title}>O radar completo continua a trabalhar por ti.</Text>
        <Text style={styles.body}>A subscrição mantém o radar personalizado, scoring por empresa, alertas e workflow comercial.</Text>
        <View style={styles.priceBox}><Text style={styles.price}>{packagePrice}</Text><Text style={styles.priceNote}>Subscrição recorrente · cobrança através de {billingChannel}</Text></View>
        <Text style={styles.terms}>{web ? 'Na Web, o pagamento é iniciado apenas para o utilizador autenticado e a ativação continua a ser confirmada pelo servidor ObraSignal. O preço, período, impostos e renovação são mostrados no checkout antes da confirmação.' : 'A subscrição renova automaticamente até ser cancelada. O preço, período e condições apresentados pela loja aplicam-se à compra.'}</Text>
        {offeringLoading && !hostedCheckoutReady
          ? <View style={styles.loadingCheckout}><ActivityIndicator color={COLORS.text}/><Text style={styles.loadingCheckoutText}>A carregar o checkout…</Text></View>
          : checkoutReady
            ? <Pressable disabled={busy} style={styles.primary} onPress={buy}>{busy ? <ActivityIndicator color={COLORS.bg}/> : <Text style={styles.primaryText}>{hostedCheckoutReady && !sdkCheckoutReady ? 'Abrir checkout seguro' : 'Subscrever'}</Text>}</Pressable>
            : <View style={styles.setupBox}><Text style={styles.setupTitle}>{!checkoutConfigured ? 'Ativação assistida disponível' : 'Plano Pro ainda não publicado no checkout'}</Text><Text style={styles.setup}>{!checkoutConfigured ? 'O checkout automático ainda não está disponível neste canal. Durante a avaliação podes continuar a usar o produto; para ativação comercial, contacta a equipa ObraSignal.' : 'A configuração de pagamentos está ligada, mas o produto obrasignal_pro_monthly ainda não está disponível no offering atual. Nenhuma compra é permitida até o produto correto estar publicado.'}</Text><Pressable onPress={()=>Linking.openURL(`mailto:${SUPPORT_EMAIL}?subject=Ativar%20ObraSignal%20Pro`)} style={styles.contact}><Text style={styles.contactText}>Pedir ativação →</Text></Pressable></View>}
        {checkoutReady ? <Pressable disabled={busy} onPress={refresh} style={styles.secondary}><Text style={styles.secondaryText}>Já paguei · atualizar estado</Text></Pressable> : null}
        {BILLING_RESTORE_SUPPORTED ? <Pressable disabled={busy} onPress={restore} style={styles.secondary}><Text style={styles.secondaryText}>Restaurar compra</Text></Pressable> : null}
        {billing.pro && billing.managementUrl ? <Pressable onPress={()=>Linking.openURL(billing.managementUrl)} style={styles.secondary}><Text style={styles.secondaryText}>Gerir subscrição</Text></Pressable> : null}
        {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
        <Pressable disabled={busy} onPress={() => setModal(false)} style={styles.close}><Text style={styles.closeText}>Fechar</Text></Pressable>
      </View></View>
    </Modal>
  </View>;
}

const styles = StyleSheet.create({
  shell:{flex:1,backgroundColor:COLORS.bg},
  planBar:{minHeight:58,paddingHorizontal:18,paddingVertical:10,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:14,backgroundColor:'#091522',borderBottomWidth:1,borderBottomColor:'#1D2D43'},
  planBarCopy:{flex:1},planKicker:{fontSize:8,fontWeight:'900',letterSpacing:1.3,color:'#607795'},planSummary:{fontSize:12,fontWeight:'800',color:COLORS.text,marginTop:2},
  planButton:{flexDirection:'row',alignItems:'center',gap:7,paddingHorizontal:11,paddingVertical:7,borderRadius:999,backgroundColor:'#12233A',borderWidth:1,borderColor:'#29486D'},planText:{fontSize:9,fontWeight:'900',letterSpacing:1,color:'#B9CAFF'},planArrow:{fontSize:16,lineHeight:16,color:'#8EABFF'},
  evalCard:{marginHorizontal:18,marginTop:12,padding:14,borderRadius:14,backgroundColor:'#0D1B2E',borderWidth:1,borderColor:'#24466D',flexDirection:'row',flexWrap:'wrap',justifyContent:'space-between',gap:12},
  evalTitle:{fontSize:9,fontWeight:'900',letterSpacing:1.2,color:COLORS.blue},evalText:{fontSize:15,fontWeight:'900',color:COLORS.text,marginTop:4},evalMetaWrap:{flexShrink:1,maxWidth:520},evalMeta:{fontSize:10,lineHeight:15,color:COLORS.muted,marginTop:2},
  blocked:{flex:1,alignItems:'center',justifyContent:'center',padding:28,backgroundColor:COLORS.bg},blockedTitle:{fontSize:26,fontWeight:'900',color:COLORS.text,textAlign:'center'},blockedText:{fontSize:13,lineHeight:20,color:COLORS.muted,textAlign:'center',marginTop:8,marginBottom:20,maxWidth:460},
  overlay:{flex:1,justifyContent:'flex-end',backgroundColor:'#000000AA'},sheet:{width:'100%',maxWidth:680,alignSelf:'center',backgroundColor:COLORS.panel,borderTopLeftRadius:24,borderTopRightRadius:24,borderWidth:1,borderColor:COLORS.line,padding:24,paddingBottom:30},sheetHandle:{width:40,height:4,borderRadius:999,backgroundColor:'#334861',alignSelf:'center',marginBottom:20},
  eyebrow:{fontSize:10,fontWeight:'900',letterSpacing:1.3,color:COLORS.blue},title:{fontSize:26,fontWeight:'900',lineHeight:32,color:COLORS.text,marginTop:7},body:{fontSize:13,lineHeight:20,color:COLORS.muted,marginTop:9,maxWidth:560},
  priceBox:{marginTop:18,padding:16,borderRadius:14,backgroundColor:COLORS.panel2,borderWidth:1,borderColor:'#2A476C'},price:{fontSize:25,fontWeight:'900',color:COLORS.text},priceNote:{fontSize:10,lineHeight:16,color:COLORS.muted,marginTop:4},terms:{fontSize:10,lineHeight:16,color:COLORS.muted,marginTop:12},
  primary:{marginTop:16,minHeight:48,borderRadius:11,backgroundColor:COLORS.text,alignItems:'center',justifyContent:'center',paddingHorizontal:16},primaryText:{fontSize:13,fontWeight:'900',color:COLORS.bg},secondary:{marginTop:8,minHeight:42,alignItems:'center',justifyContent:'center'},secondaryText:{fontSize:12,fontWeight:'800',color:'#91ACFF'},
  loadingCheckout:{marginTop:16,minHeight:48,borderRadius:11,borderWidth:1,borderColor:COLORS.line,alignItems:'center',justifyContent:'center',flexDirection:'row',gap:9},loadingCheckoutText:{fontSize:12,fontWeight:'800',color:COLORS.text},
  setupBox:{marginTop:16,padding:14,borderRadius:12,backgroundColor:'#171D28',borderWidth:1,borderColor:'#51442A'},setupTitle:{fontSize:11,fontWeight:'900',color:COLORS.amber},setup:{fontSize:11,lineHeight:17,color:'#C8B989',marginTop:5},contact:{alignSelf:'flex-start',marginTop:10},contactText:{fontSize:11,fontWeight:'900',color:'#9DB4FF'},
  error:{fontSize:11,lineHeight:17,color:COLORS.red,marginTop:10},close:{marginTop:4,minHeight:38,alignItems:'center',justifyContent:'center'},closeText:{fontSize:12,fontWeight:'800',color:COLORS.muted},
});