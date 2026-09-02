import React from 'react'
import { StyleSheet, Text, View } from 'react-native'

const ITEMS = [
  ['HTTPS / TLS', 'Ativo no serviço Web publicado'],
  ['Privacidade', 'Exportação e pedido de eliminação de dados'],
  ['Testes de produção', 'Autenticação, privacidade e browser E2E verificados'],
  ['CSA STAR Level 1', 'Self-assessment em preparação — ainda não certificado'],
]

export default function SecurityTrustBar() {
  return <View style={styles.wrap} accessibilityLabel="Segurança e confiança ObraSignal">
    <View style={styles.heading}>
      <Text style={styles.kicker}>SEGURANÇA & CONFIANÇA</Text>
      <Text style={styles.note}>Mostramos apenas estados que conseguimos provar.</Text>
    </View>
    <View style={styles.items}>
      {ITEMS.map(([title, detail]) => <View key={title} style={styles.item}>
        <View style={styles.dot}/>
        <View style={styles.copy}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.detail}>{detail}</Text>
        </View>
      </View>)}
    </View>
  </View>
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: 18, paddingVertical: 12, borderTopWidth: 1, borderTopColor: '#182A3E', backgroundColor: '#091522', gap: 10 },
  heading: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 },
  kicker: { color: '#DCE6F3', fontSize: 10, fontWeight: '900', letterSpacing: 0.8 },
  note: { color: '#7489A5', fontSize: 9, fontWeight: '700' },
  items: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  item: { minWidth: 190, flexGrow: 1, flexBasis: 220, flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingHorizontal: 10, paddingVertical: 9, borderRadius: 10, borderWidth: 1, borderColor: '#22364F', backgroundColor: '#0D1A29' },
  dot: { width: 7, height: 7, borderRadius: 99, marginTop: 4, backgroundColor: '#72DFA1' },
  copy: { flex: 1 },
  title: { color: '#F4F7FB', fontSize: 10, fontWeight: '900' },
  detail: { color: '#9BAABD', fontSize: 9, lineHeight: 13, marginTop: 2, fontWeight: '600' },
})
