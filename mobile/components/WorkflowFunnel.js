import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { api } from '../src/api';

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

const STEPS = [
  ['NEW', 'Novo', COLORS.blue],
  ['REVIEWING', 'Em análise', COLORS.blue],
  ['PREPARING', 'A preparar', COLORS.amber],
  ['SUBMITTED', 'Enviada', COLORS.amber],
  ['WON', 'Ganho', COLORS.green],
  ['LOST', 'Perdido', COLORS.red],
];

export default function WorkflowFunnel() {
  const [counts, setCounts] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    api.workflowStats()
      .then((data) => { if (active) setCounts(data?.counts || {}); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);

  const totalActive = useMemo(() => {
    if (!counts) return 0;
    return ['NEW', 'REVIEWING', 'PREPARING', 'SUBMITTED'].reduce((sum, key) => sum + (counts[key] || 0), 0);
  }, [counts]);

  if (error) return null;

  return <View style={{ marginTop: 14, padding: 14, borderRadius: 14, borderWidth: 1, borderColor: COLORS.line, backgroundColor: COLORS.panel }}>
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
      <View style={{ flex: 1 }}>
        <Text style={{ color: COLORS.text, fontSize: 16, fontWeight: '900' }}>Funil comercial</Text>
        <Text style={{ color: COLORS.muted, fontSize: 11, marginTop: 3 }}>Onde estão as oportunidades da tua empresa.</Text>
      </View>
      {counts ? <Text style={{ color: COLORS.blue, fontSize: 12, fontWeight: '900' }}>{totalActive} activas</Text> : <ActivityIndicator color={COLORS.blue} size="small" />}
    </View>

    {counts ? <View style={{ marginTop: 12 }}>
      {STEPS.map(([key, label, tone]) => {
        const value = counts[key] || 0;
        const denominator = Math.max(totalActive, 1);
        const width = Math.max(value ? 8 : 0, Math.round((value / denominator) * 100));
        return <View key={key} style={{ marginTop: 8 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={{ color: COLORS.muted, fontSize: 11, fontWeight: '700' }}>{label}</Text>
            <Text style={{ color: tone, fontSize: 12, fontWeight: '900' }}>{value}</Text>
          </View>
          <View style={{ height: 7, borderRadius: 4, backgroundColor: '#1A263E', marginTop: 5, overflow: 'hidden' }}>
            <View style={{ width: `${width}%`, height: 7, borderRadius: 4, backgroundColor: tone }} />
          </View>
        </View>;
      })}
      <View style={{ flexDirection: 'row', marginTop: 12, gap: 16 }}>
        <Text style={{ color: COLORS.green, fontSize: 11, fontWeight: '800' }}>Ganhos: {counts.WON || 0}</Text>
        <Text style={{ color: COLORS.red, fontSize: 11, fontWeight: '800' }}>Perdidos: {counts.LOST || 0}</Text>
      </View>
    </View> : null}
  </View>;
}
