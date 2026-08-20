import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import WorkflowFunnel from './WorkflowFunnel';

const COLORS = {
  panel: '#10182B', line: '#253553', text: '#F3F6FF', muted: '#9BA8C0',
  blue: '#5E8BFF', green: '#6FE39A', amber: '#FFD66B', red: '#FF8998',
};

function toneForFactor(key) {
  if (key === 'economic_fit') return COLORS.green;
  if (key === 'geography' || key === 'capability') return COLORS.green;
  return COLORS.blue;
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
});
