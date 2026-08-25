import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import WorkflowFunnel from './WorkflowFunnel';
import { api } from '../src/api';

const COLORS = {
  panel: '#10182B', line: '#253553', text: '#F3F6FF', muted: '#9BA8C0',
  blue: '#5E8BFF', green: '#6FE39A', amber: '#FFD66B', red: '#FF8998',
};

const READINESS_LABELS = {
  READY: 'Pronta para preparação',
  CONDITIONALLY_READY: 'Pronta com reservas',
  NOT_READY: 'Não pronta',
  UNKNOWN: 'Por verificar',
  BLOCKED: 'Bloqueado',
  WARNING: 'Atenção',
  NOT_APPLICABLE: 'Não aplicável',
};

function toneForFactor(key) {
  if (key === 'economic_fit') return COLORS.green;
  if (key === 'geography' || key === 'capability') return COLORS.green;
  return COLORS.blue;
}

function toneForStatus(status) {
  if (status === 'READY') return COLORS.green;
  if (status === 'NOT_READY' || status === 'BLOCKED') return COLORS.red;
  if (status === 'CONDITIONALLY_READY' || status === 'WARNING') return COLORS.amber;
  return COLORS.muted;
}

function Factor({ title, text, score, tone = COLORS.blue }) {
  if (!text && score == null) return null;
  return <View style={styles.row}>
    <View style={[styles.icon, { backgroundColor: `${tone}18` }]}><View style={[styles.dot, { backgroundColor: tone }]} /></View>
    <View style={styles.body}>
      <View style={styles.factorHeader}><Text style={styles.title}>{title}</Text>{score != null ? <Text style={[styles.factorScore, { color: tone }]}>{score}/100</Text> : null}</View>
      {text ? <Text style={styles.text}>{text}</Text> : null}
    </View>
  </View>;
}

function ReadinessChecklist({ opportunityId }) {
  const [assessment, setAssessment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api.readiness(opportunityId)
      .then((value) => { if (active) setAssessment(value); })
      .catch(() => { if (active) setError('Não foi possível verificar a preparação agora. O resto do detalhe continua disponível.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [opportunityId, reload]);

  if (!opportunityId) return null;
  if (loading) return <View style={styles.readinessCard} accessibilityLabel="A verificar preparação da oportunidade"><View style={styles.readinessLoading}><ActivityIndicator size="small" color={COLORS.blue} /><Text style={styles.text}>A verificar preparação para proposta…</Text></View></View>;
  if (error || !assessment) return <View style={styles.readinessCard}><Text style={styles.readinessHeading}>Preparação para proposta</Text><Text style={styles.text}>{error || 'Estado de preparação indisponível.'}</Text><Pressable accessibilityRole="button" onPress={() => setReload((value) => value + 1)} style={styles.retry}><Text style={styles.retryText}>Tentar novamente</Text></Pressable></View>;

  const status = assessment.overall_status || 'UNKNOWN';
  const tone = toneForStatus(status);
  const blockers = assessment.blocking_items || [];
  const warnings = assessment.warning_items || [];
  const unknowns = assessment.unknown_items || [];
  const ready = assessment.ready_items || [];
  const nextChecks = assessment.next_checks || [];

  const Item = ({ item, itemStatus }) => <View style={styles.readinessItem}>
    <Text style={[styles.readinessMarker, { color: toneForStatus(itemStatus) }]}>{itemStatus === 'READY' ? '✓' : itemStatus === 'BLOCKED' ? '×' : itemStatus === 'WARNING' ? '!' : '?'}</Text>
    <View style={styles.body}><Text style={styles.readinessItemTitle}>{item.dimension || 'CHECK'}</Text><Text style={styles.text}>{item.description}</Text></View>
  </View>;

  return <View style={styles.readinessCard} accessibilityLabel={`Preparação para proposta: ${READINESS_LABELS[status] || status}`}>
    <View style={styles.readinessHeader}>
      <View style={styles.body}><Text style={styles.readinessHeading}>Preparação para proposta</Text><Text style={styles.readinessSubtitle}>Estado operacional, não decisão BID / NO-BID.</Text></View>
      <Text style={[styles.readinessStatus, { color }]}>{READINESS_LABELS[status] || status}</Text>
    </View>
    {blockers.map((item, index) => <Item key={`blocked-${item.code}-${index}`} item={item} itemStatus="BLOCKED" />)}
    {unknowns.map((item, index) => <Item key={`unknown-${item.code}-${index}`} item={item} itemStatus="UNKNOWN" />)}
    {warnings.map((item, index) => <Item key={`warning-${item.code}-${index}`} item={item} itemStatus="WARNING" />)}
    {ready.map((item, index) => <Item key={`ready-${item.code}-${index}`} item={item} itemStatus="READY" />)}
    {nextChecks.length ? <View style={styles.nextChecks}><Text style={styles.nextChecksTitle}>Próximas verificações</Text>{nextChecks.slice(0, 4).map((check, index) => <Text key={`${check}-${index}`} style={styles.nextCheck}>• {check}</Text>)}</View> : null}
    <Text style={styles.readinessTrust}>“Por verificar” não significa bloqueado. “Pronta” só aparece quando os checks críticos avaliados estão positivamente sustentados.</Text>
  </View>;
}

export default function OpportunityExplanation({ item }) {
  const blockers = item?.hard_capability_blockers || [];
  const explanation = item?.explanation;
  const factors = explanation?.factors || [];
  const negativeFactors = explanation?.negative_factors || [];
  const fallbackFactors = [
    { key: 'profile', label: 'Perfil comercial', score: item?.profile_score, reason: 'Compatibilidade com o perfil da empresa' },
    { key: 'lot', label: 'Adequação do lote', score: item?.lot_score, reason: 'Compatibilidade do lote' },
    { key: 'geography', label: 'Geografia', score: null, reason: item?.geography?.reason },
    { key: 'capability', label: 'Capacidade', score: null, reason: item?.capability_evidence?.reason },
    { key: 'economic_fit', label: 'Economic Fit', score: item?.economic_fit?.score, reason: item?.economic_fit?.reason || item?.economic_fit?.status },
  ].filter((factor) => factor.reason || factor.score != null);
  const visibleFactors = factors.length ? factors : fallbackFactors;

  return <>
    <ReadinessChecklist opportunityId={item?.id} />
    {visibleFactors.length || blockers.length || negativeFactors.length ? <View style={styles.card}>
      <Text style={styles.heading}>Porque esta oportunidade</Text>
      {visibleFactors.map((factor) => <Factor key={factor.key} title={factor.label} text={factor.reason} score={factor.score} tone={toneForFactor(factor.key)} />)}
      {blockers.length ? <View style={styles.risk}><Text style={styles.riskTitle}>Atenção</Text>{blockers.map((blocker, index) => <Text key={`${blocker}-${index}`} style={styles.riskText}>• {blocker}</Text>)}</View> : null}
      {negativeFactors.length ? <View style={styles.risk}><Text style={styles.riskTitle}>Factores negativos</Text>{negativeFactors.map((factor, index) => <Text key={`${factor.reason}-${index}`} style={styles.riskText}>• {factor.reason}</Text>)}</View> : null}
    </View> : null}
    <WorkflowFunnel refreshKey={`${item?.id || ''}:${item?.workflow?.status || 'NEW'}:${item?.workflow?.updated_at || ''}`} />
  </>;
}

const styles = StyleSheet.create({
  card:{marginTop:14,padding:14,borderRadius:14,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},
  heading:{color:COLORS.text,fontSize:16,fontWeight:'900',marginBottom:5},row:{flexDirection:'row',alignItems:'flex-start',marginTop:10},icon:{width:28,height:28,borderRadius:9,alignItems:'center',justifyContent:'center',marginRight:10},dot:{width:8,height:8,borderRadius:4},body:{flex:1},factorHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:8},title:{color:COLORS.text,fontSize:12,fontWeight:'800'},factorScore:{fontSize:11,fontWeight:'900'},text:{color:COLORS.muted,fontSize:12,lineHeight:17,marginTop:2},risk:{marginTop:14,borderRadius:10,borderWidth:1,borderColor:'#5A4526',backgroundColor:'#241D10',padding:10},riskTitle:{color:COLORS.amber,fontSize:10,fontWeight:'900',textTransform:'uppercase',letterSpacing:.6},riskText:{color:COLORS.text,fontSize:12,lineHeight:18,marginTop:4},
  readinessCard:{marginTop:14,padding:14,borderRadius:14,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},readinessLoading:{flexDirection:'row',alignItems:'center',gap:9},readinessHeader:{flexDirection:'row',alignItems:'flex-start',justifyContent:'space-between',gap:12},readinessHeading:{color:COLORS.text,fontSize:16,fontWeight:'900'},readinessSubtitle:{color:COLORS.muted,fontSize:11,lineHeight:16,marginTop:2},readinessStatus:{fontSize:11,fontWeight:'900',textAlign:'right',maxWidth:120},readinessItem:{flexDirection:'row',alignItems:'flex-start',marginTop:11},readinessMarker:{width:22,fontSize:16,fontWeight:'900'},readinessItemTitle:{color:COLORS.text,fontSize:10,fontWeight:'900',letterSpacing:.5},nextChecks:{marginTop:13,paddingTop:11,borderTopWidth:1,borderTopColor:COLORS.line},nextChecksTitle:{color:COLORS.text,fontSize:11,fontWeight:'900'},nextCheck:{color:COLORS.muted,fontSize:12,lineHeight:18,marginTop:3},readinessTrust:{color:COLORS.muted,fontSize:10,lineHeight:15,marginTop:12},retry:{alignSelf:'flex-start',marginTop:9,paddingVertical:7,paddingHorizontal:10,borderRadius:8,borderWidth:1,borderColor:COLORS.line},retryText:{color:COLORS.blue,fontSize:11,fontWeight:'800'},
});
