import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { api } from '../src/api';

const COLORS = {
  bg: '#F7FAFF',
  card: '#FFFFFF',
  line: '#DCE5F2',
  text: '#15253D',
  muted: '#6C7A91',
  blue: '#315EA8',
  blueSoft: '#EAF1FF',
  red: '#B53A4A',
};

function parseList(value) {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function readiness(profile) {
  let done = 0;
  if (profile.name) done += 1;
  if (profile.activity) done += 1;
  if (profile.keywords?.length || profile.cpv_prefixes?.length) done += 1;
  if (profile.countries?.length || profile.regions?.length) done += 1;
  if (profile.min_value != null || profile.max_value != null || profile.economic_min_score != null) done += 1;
  return Math.round((done / 5) * 100);
}

export default function ProfileOnboarding({ initialProfile, onComplete }) {
  const [name, setName] = useState(initialProfile?.name || '');
  const [activity, setActivity] = useState(initialProfile?.activity || '');
  const [cpv, setCpv] = useState((initialProfile?.cpv_prefixes || []).join(', '));
  const [regions, setRegions] = useState((initialProfile?.regions || []).join(', '));
  const [minValue, setMinValue] = useState(initialProfile?.min_value == null ? '' : String(initialProfile.min_value));
  const [maxValue, setMaxValue] = useState(initialProfile?.max_value == null ? '' : String(initialProfile.max_value));
  const [economicMinScore, setEconomicMinScore] = useState(initialProfile?.economic_min_score == null ? '' : String(initialProfile.economic_min_score));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const draft = useMemo(() => ({
    ...initialProfile,
    name: name.trim(),
    activity: activity.trim(),
    cpv_prefixes: parseList(cpv),
    regions: parseList(regions),
    min_value: minValue === '' ? initialProfile?.min_value : Number(minValue),
    max_value: maxValue === '' ? initialProfile?.max_value : Number(maxValue),
    economic_min_score: economicMinScore === '' ? initialProfile?.economic_min_score : Number(economicMinScore),
  }), [initialProfile, name, activity, cpv, regions, minValue, maxValue, economicMinScore]);

  const save = async () => {
    if (!draft.name || !draft.activity) {
      setError('Indica o nome e a actividade principal da empresa.');
      return;
    }
    if ([draft.min_value, draft.max_value, draft.economic_min_score].some((value) => value != null && !Number.isFinite(value))) {
      setError('Revê os valores numéricos indicados.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await api.saveProfile(draft);
      onComplete(result.profile || draft);
    } catch (err) {
      setError(err?.message || 'Não foi possível guardar o perfil.');
    } finally {
      setSaving(false);
    }
  };

  const score = readiness(draft);

  return (
    <ScrollView style={styles.safe} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.hero}>
        <Text style={styles.eyebrow}>PRIMEIRO PASSO</Text>
        <Text style={styles.title}>Vamos ensinar o ObraSignal sobre a tua empresa.</Text>
        <Text style={styles.subtitle}>Estas regras determinam quais oportunidades entram no teu radar. Nada é inventado.</Text>
        <View style={styles.readiness}><Text style={styles.readinessLabel}>Perfil inicial</Text><Text style={styles.readinessValue}>{score}%</Text></View>
      </View>

      <View style={styles.card}>
        <Text style={styles.section}>Empresa</Text>
        <TextInput value={name} onChangeText={setName} placeholder="Nome da empresa" placeholderTextColor={COLORS.muted} style={styles.input} />
        <TextInput value={activity} onChangeText={setActivity} placeholder="Actividade principal (ex.: metalomecânica)" placeholderTextColor={COLORS.muted} style={styles.input} />

        <Text style={styles.section}>O que procurar</Text>
        <TextInput value={cpv} onChangeText={setCpv} placeholder="CPVs / famílias, separados por vírgula" placeholderTextColor={COLORS.muted} style={styles.input} />
        <TextInput value={regions} onChangeText={setRegions} placeholder="Regiões / cidades prioritárias" placeholderTextColor={COLORS.muted} style={styles.input} />

        <Text style={styles.section}>Regras económicas</Text>
        <View style={styles.row}>
          <TextInput value={minValue} onChangeText={setMinValue} placeholder="Valor mín." keyboardType="numeric" placeholderTextColor={COLORS.muted} style={[styles.input, styles.half]} />
          <TextInput value={maxValue} onChangeText={setMaxValue} placeholder="Valor máx." keyboardType="numeric" placeholderTextColor={COLORS.muted} style={[styles.input, styles.half]} />
        </View>
        <TextInput value={economicMinScore} onChangeText={setEconomicMinScore} placeholder="Economic Fit mínimo (0–100)" keyboardType="numeric" placeholderTextColor={COLORS.muted} style={styles.input} />

        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable onPress={save} disabled={saving} style={({ pressed }) => [styles.button, pressed && { opacity: 0.86 }, saving && { opacity: 0.6 }]}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Guardar e abrir o Radar</Text>}
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 20, paddingBottom: 44 },
  hero: { marginBottom: 18, paddingTop: 12 },
  eyebrow: { color: COLORS.blue, fontSize: 12, fontWeight: '800', letterSpacing: 1.1 },
  title: { color: COLORS.text, fontSize: 28, fontWeight: '900', lineHeight: 34, marginTop: 6 },
  subtitle: { color: COLORS.muted, fontSize: 14, lineHeight: 20, marginTop: 8 },
  readiness: { marginTop: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14, backgroundColor: COLORS.blueSoft, borderRadius: 12 },
  readinessLabel: { color: COLORS.text, fontWeight: '700' },
  readinessValue: { color: COLORS.blue, fontWeight: '900', fontSize: 22 },
  card: { backgroundColor: COLORS.card, borderRadius: 18, padding: 18, borderWidth: 1, borderColor: COLORS.line },
  section: { color: COLORS.text, fontSize: 15, fontWeight: '800', marginTop: 10, marginBottom: 8 },
  input: { borderWidth: 1, borderColor: COLORS.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, color: COLORS.text, backgroundColor: '#FBFCFF', marginBottom: 10 },
  row: { flexDirection: 'row', gap: 10 },
  half: { flex: 1 },
  error: { color: COLORS.red, marginVertical: 4, lineHeight: 18 },
  button: { minHeight: 50, borderRadius: 14, backgroundColor: COLORS.blue, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  buttonText: { color: '#fff', fontWeight: '900', fontSize: 15 },
});
