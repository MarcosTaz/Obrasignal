import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import WorkflowFunnel from './WorkflowFunnel';

const COLORS = {
  panel: '#10182B', line: '#253553', text: '#F3F6FF', muted: '#9BA8C0',
  blue: '#5E8BFF', green: '#6FE39A', amber: '#FFD66B', red: '#FF8998',
};

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

function confidenceLabel(value) {
  return { HIGH: 'Alta', MEDIUM: 'Média', LOW: 'Baixa', UNKNOWN: 'Por confirmar' }[value] || 'Por confirmar';
}

function fieldLabel(value) {
  return {
    title: 'Título', description: 'Descrição', buyer: 'Entidade', country: 'País',
    cpv: 'CPV', value: 'Valor', deadline: 'Prazo', procedure_type: 'Procedimento',
    source_freshness: 'Atualidade da fonte', material_support: 'Suporte material', claim_value: 'Valor da conclusão',
    company_specialization: 'Especialização da empresa',
  }[value] || value;
}

function EvidenceSummary({ evidence }) {
  if (!evidence) return null;
  if (evidence.state !== 'READY') {
    return <View style={styles.evidenceUnavailable}>
      <Text style={styles.evidenceTitle}>Evidência da decisão</Text>
      <Text style={styles.text}>Evidência indisponível para esta decisão. A ausência não é apresentada como confirmação.</Text>
    </View>;
  }

  const sources = evidence.sources || [];
  const missing = evidence.missing || [];
  return <View style={styles.evidenceBox}>
    <View style={styles.evidenceHeader}>
      <Text style={styles.evidenceTitle}>Evidência da decisão</Text>
      <Text style={styles.confidence}>Confiança {confidenceLabel(evidence.confidence)}</Text>
    </View>
    <Text style={styles.evidenceLead}>{sources.length} campo(s) suportado(s) por proveniência registada</Text>
    {sources.slice(0, 8).map((source, index) => {
      const reference = source.source_reference || source.external_id;
      return <View key={`${source.source}-${source.external_id}-${source.field_name}-${index}`} style={styles.sourceRow}>
        <View style={styles.sourceDot} />
        <Text style={styles.sourceText}><Text style={styles.sourceStrong}>{source.source || 'Fonte'}</Text>{reference ? ` · ${reference}` : ''}{source.field_name ? ` · ${fieldLabel(source.field_name)}` : ''}{source.stale === true ? ' · desatualizada' : source.stale == null ? ' · atualidade por confirmar' : ''}</Text>
      </View>;
    })}
    {missing.length ? <View style={styles.missingBox}>
      <Text style={styles.missingTitle}>Falta confirmar</Text>
      <Text style={styles.missingText}>{missing.map(fieldLabel).join(' · ')}</Text>
    </View> : null}
    {evidence.conflict_count > 0 ? <Text style={styles.conflictText}>Existem {evidence.conflict_count} conflito(s) de evidência por resolver.</Text> : null}
  </View>;
}

export default function OpportunityExplanation({ item }) {
  const blockers = item?.hard_capability_blockers || [];
  const explanation = item?.explanation;
  const evidence = explanation?.evidence;
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
    {visibleFactors.length || blockers.length || negativeFactors.length || evidence ? <View style={styles.card}>
      <Text style={styles.heading}>Porque esta oportunidade</Text>
      {visibleFactors.map((factor) => <Factor key={factor.key} title={factor.label} text={factor.reason} score={factor.score} />)}
      {blockers.length ? <View style={styles.risk}><Text style={styles.riskTitle}>Atenção</Text>{blockers.map((blocker, index) => <Text key={`${blocker}-${index}`} style={styles.riskText}>• {blocker}</Text>)}</View> : null}
      {negativeFactors.length ? <View style={styles.risk}><Text style={styles.riskTitle}>Factores negativos</Text>{negativeFactors.map((factor, index) => <Text key={`${factor.reason}-${index}`} style={styles.riskText}>• {factor.reason}</Text>)}</View> : null}
      <EvidenceSummary evidence={evidence} />
    </View> : null}
    <WorkflowFunnel refreshKey={`${item?.id || ''}:${item?.workflow?.status || 'NEW'}:${item?.workflow?.updated_at || ''}`} />
  </>;
}

const styles = StyleSheet.create({
  card:{marginTop:14,padding:14,borderRadius:14,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},
  heading:{color:COLORS.text,fontSize:16,fontWeight:'900',marginBottom:5},row:{flexDirection:'row',alignItems:'flex-start',marginTop:10},icon:{width:28,height:28,borderRadius:9,alignItems:'center',justifyContent:'center',marginRight:10},dot:{width:8,height:8,borderRadius:4},body:{flex:1},factorHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:8},title:{color:COLORS.text,fontSize:12,fontWeight:'800'},factorScore:{fontSize:11,fontWeight:'900'},text:{color:COLORS.muted,fontSize:12,lineHeight:17,marginTop:2},risk:{marginTop:14,borderRadius:10,borderWidth:1,borderColor:'#5A4526',backgroundColor:'#241D10',padding:10},riskTitle:{color:COLORS.amber,fontSize:10,fontWeight:'900',textTransform:'uppercase',letterSpacing:.6},riskText:{color:COLORS.text,fontSize:12,lineHeight:18,marginTop:4},
  evidenceBox:{marginTop:14,paddingTop:13,borderTopWidth:1,borderTopColor:COLORS.line},evidenceUnavailable:{marginTop:14,padding:11,borderRadius:10,borderWidth:1,borderColor:COLORS.line},evidenceHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:8},evidenceTitle:{color:COLORS.text,fontSize:12,fontWeight:'900'},confidence:{color:COLORS.green,fontSize:10,fontWeight:'900',textTransform:'uppercase',letterSpacing:.4},evidenceLead:{color:COLORS.muted,fontSize:11,lineHeight:16,marginTop:4,marginBottom:4},sourceRow:{flexDirection:'row',alignItems:'flex-start',marginTop:7},sourceDot:{width:5,height:5,borderRadius:3,backgroundColor:COLORS.blue,marginTop:6,marginRight:8},sourceText:{color:COLORS.muted,fontSize:11,lineHeight:16,flex:1},sourceStrong:{color:COLORS.text,fontWeight:'800'},missingBox:{marginTop:10,borderRadius:8,borderWidth:1,borderColor:'#5A4526',padding:8},missingTitle:{color:COLORS.amber,fontSize:9,fontWeight:'900',textTransform:'uppercase',letterSpacing:.5},missingText:{color:COLORS.text,fontSize:11,lineHeight:16,marginTop:3},conflictText:{color:COLORS.red,fontSize:11,lineHeight:16,marginTop:8,fontWeight:'700'},
});
