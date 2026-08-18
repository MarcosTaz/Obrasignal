import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

const COLORS = {
  panel: '#10182B',
  line: '#253553',
  text: '#F3F6FF',
  muted: '#9BA8C0',
  blue: '#5E8BFF',
  green: '#6FE39A',
  amber: '#FFD66B',
  red: '#FF8998',
};

function Factor({ title, text, tone = COLORS.blue }) {
  if (!text) return null;
  return <View style={styles.row}>
    <View style={[styles.icon, { backgroundColor: `${tone}18` }]}><View style={[styles.dot, { backgroundColor: tone }]} /></View>
    <View style={styles.body}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.text}>{text}</Text>
    </View>
  </View>;
}

export default function OpportunityExplanation({ item }) {
  const blockers = item?.hard_capability_blockers || [];
  const economics = item?.economic_fit;
  const capability = item?.capability_evidence?.reason;
  const geography = item?.geography?.reason;
  const explanation = item?.decision_explanation;
  const hasStructured = item?.profile_score !== undefined || item?.lot_score !== undefined || geography || capability || economics?.reason;

  if (!hasStructured && !blockers.length) return null;

  return <View style={styles.card}>
    <Text style={styles.heading}>Porque esta oportunidade</Text>
    <Factor title="Perfil comercial" text={item?.profile_score != null ? `${item.profile_score}/100` : null} />
    <Factor title="Adequação do lote" text={item?.lot_score != null ? `${item.lot_score}/100` : null} />
    <Factor title="Geografia" text={geography} tone={COLORS.green} />
    <Factor title="Capacidade" text={capability} tone={COLORS.green} />
    <Factor title="Economic Fit" text={economics?.reason ? `${economics.status}: ${economics.reason}` : null} tone={economics?.status === 'UNFAVOURABLE' ? COLORS.red : COLORS.green} />
    {blockers.length ? <View style={styles.risk}>
      <Text style={styles.riskTitle}>Atenção</Text>
      {blockers.map((blocker, index) => <Text key={`${blocker}-${index}`} style={styles.riskText}>• {blocker}</Text>)}
    </View> : null}
    {explanation?.reason ? <Text style={styles.technical}>{explanation.reason}</Text> : null}
  </View>;
}

const styles = StyleSheet.create({
  card: { marginTop: 14, padding: 14, borderRadius: 14, borderWidth: 1, borderColor: COLORS.line, backgroundColor: COLORS.panel },
  heading: { color: COLORS.text, fontSize: 16, fontWeight: '900', marginBottom: 5 },
  row: { flexDirection: 'row', alignItems: 'flex-start', marginTop: 10 },
  icon: { width: 28, height: 28, borderRadius: 9, alignItems: 'center', justifyContent: 'center', marginRight: 10 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  body: { flex: 1 },
  title: { color: COLORS.text, fontSize: 12, fontWeight: '800' },
  text: { color: COLORS.muted, fontSize: 12, lineHeight: 17, marginTop: 2 },
  risk: { marginTop: 14, borderRadius: 10, borderWidth: 1, borderColor: '#5A4526', backgroundColor: '#241D10', padding: 10 },
  riskTitle: { color: COLORS.amber, fontSize: 10, fontWeight: '900', textTransform: 'uppercase', letterSpacing: 0.6 },
  riskText: { color: COLORS.text, fontSize: 12, lineHeight: 18, marginTop: 4 },
  technical: { color: '#7F8BA0', fontSize: 10, lineHeight: 15, marginTop: 12 },
});
