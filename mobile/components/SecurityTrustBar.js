import React from 'react'
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native'
import { BRAND } from '../src/brand-palette.mjs'

const ITEMS = [
  ['HTTPS / TLS','Transport encryption on the published website'],
  ['Privacy','Authenticated export and deletion controls'],
  ['Production validation','Authenticated end-to-end checks remain blocked by the identity provider'],
  ['CSA STAR Level 1','Self-assessment in preparation — certification not claimed'],

]

export default function SecurityTrustBar() {
  const { width } = useWindowDimensions()
  const compact = width < 560
  const items = ITEMS.map(([title, detail]) => <View key={title} style={[styles.item, compact && styles.itemCompact]}>
    <View style={styles.dot}/>
    <View style={styles.copy}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.detail}>{detail}</Text>
    </View>
  </View>)

  return <View style={[styles.wrap, compact && styles.wrapCompact]} accessibilityLabel="ObraSignal security and trust">
    <View style={styles.heading}>
      <Text style={styles.kicker}>SECURITY & TRUST</Text>
      <Text style={styles.note}>Only verified status is presented.</Text>
    </View>
    {compact
      ? <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.itemsScroller} contentContainerStyle={styles.itemsCompact}>{items}</ScrollView>
      : <View style={styles.items}>{items}</View>}
  </View>
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: 18, paddingVertical: 12, borderTopWidth: 1, borderTopColor: BRAND.fog, backgroundColor: BRAND.paper, gap: 10 },
  wrapCompact: { paddingVertical: 8, gap: 7 },
  heading: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 },
  kicker: { color: BRAND.ink, fontSize: 10, fontWeight: '900', letterSpacing: 0.8 },
  note: { color: BRAND.mineral, fontSize: 9, fontWeight: '700' },
  items: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  itemsScroller: { width: '100%' },
  itemsCompact: { flexDirection: 'row', gap: 8, paddingRight: 18 },
  item: { minWidth: 190, flexGrow: 1, flexBasis: 220, flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingHorizontal: 10, paddingVertical: 9, borderRadius: 10, borderWidth: 1, borderColor: BRAND.fog, backgroundColor: '#FFFFFF' },
  itemCompact: { width: 210, minWidth: 210, flexGrow: 0, flexBasis: 'auto' },
  dot: { width: 7, height: 7, borderRadius: 99, marginTop: 4, backgroundColor: '#C87D55' },
  copy: { flex: 1 },
  title: { color: BRAND.ink, fontSize: 10, fontWeight: '900' },
  detail: { color: BRAND.mineral, fontSize: 9, lineHeight: 13, marginTop: 2, fontWeight: '600' },
})
