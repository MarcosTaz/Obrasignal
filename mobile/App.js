import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Linking,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';

const API = 'https://obrasignal.onrender.com/api/v1';
const SAVED_KEY = '@obrasignal/saved';

const COLORS = {
  bg: '#070C18',
  panel: '#10182B',
  panel2: '#151F36',
  line: '#253553',
  text: '#F3F6FF',
  muted: '#9BA8C0',
  blue: '#5E8BFF',
  green: '#6FE39A',
  amber: '#FFD66B',
  red: '#FF8998',
};

function deadlineTone(state) {
  if (state === 'closed') return COLORS.red;
  if (state === 'urgent') return COLORS.amber;
  if (state === 'open') return COLORS.green;
  return COLORS.muted;
}

function Deadline({ item, large = false }) {
  const d = item?.deadline_status;
  const tone = deadlineTone(d?.state);
  const text = d?.state === 'closed'
    ? `TERMINADO · há ${Math.max(1, Math.abs(d.days_remaining || 1))} dias`
    : d?.state === 'urgent'
      ? `${d.label.toUpperCase()} · ${d.days_remaining ?? 0} dias`
      : d?.state === 'open'
        ? `ABERTO · ${d.days_remaining} dias restantes`
        : 'PRAZO NÃO INDICADO';
  return (
    <View style={[styles.deadline, { borderColor: `${tone}55`, backgroundColor: `${tone}12` }]}>
      <View style={[styles.dot, { backgroundColor: tone }]} />
      <Text style={[styles.deadlineText, { color: tone, fontSize: large ? 14 : 11 }]}>{text}</Text>
    </View>
  );
}

function Score({ value }) {
  const tone = value >= 80 ? COLORS.green : value >= 60 ? COLORS.blue : COLORS.muted;
  return <Text style={[styles.score, { color: tone }]}>{value}/100</Text>;
}

function OpportunityCard({ item, onPress, saved, onSave }) {
  return (
    <Pressable onPress={() => onPress(item)} style={({ pressed }) => [styles.card, pressed && { opacity: 0.86 }]}>
      <View style={styles.cardTop}>
        <View style={styles.sourcePill}><Text style={styles.sourceText}>{item.source}</Text></View>
        <Score value={item.score || 0} />
      </View>
      <Text style={styles.cardTitle} numberOfLines={4}>{item.title || 'Sem título'}</Text>
      <Text style={styles.buyer} numberOfLines={2}>{item.buyer || 'Entidade não identificada'}</Text>
      <Deadline item={item} />
      {item.value ? <Text style={styles.meta}>Valor: {item.value}</Text> : null}
      <Text style={styles.reason} numberOfLines={2}>{item.match_reason || 'Correspondência com obra'}</Text>
      <View style={styles.cardBottom}>
        <Text style={styles.openText}>Ver oportunidade →</Text>
        <Pressable hitSlop={12} onPress={(e) => { e.stopPropagation?.(); onSave(item.id); }}>
          <Text style={[styles.saveIcon, saved && { color: COLORS.amber }]}>{saved ? '★' : '☆'}</Text>
        </Pressable>
      </View>
    </Pressable>
  );
}

function Detail({ item, saved, onBack, onSave }) {
  if (!item) return null;
  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.detailWrap}>
        <View style={styles.detailHeader}>
          <Pressable onPress={onBack} style={styles.backButton}><Text style={styles.backText}>‹  Voltar</Text></Pressable>
          <Pressable onPress={() => onSave(item.id)}><Text style={[styles.saveIcon, saved && { color: COLORS.amber }]}>{saved ? '★' : '☆'}</Text></Pressable>
        </View>
        <View style={styles.detailSourceRow}>
          <View style={styles.sourcePill}><Text style={styles.sourceText}>{item.source}</Text></View>
          <Score value={item.score || 0} />
        </View>
        <Text style={styles.detailTitle}>{item.title || 'Sem título'}</Text>
        <Text style={styles.detailBuyer}>{item.buyer || 'Entidade não identificada'}</Text>
        <Deadline item={item} large />

        <View style={styles.infoGrid}>
          <Info label="PUBLICAÇÃO" value={item.publication_date || '—'} />
          <Info label="VALOR" value={item.value || 'Não indicado'} />
          <Info label="PAÍS" value={item.country || 'PRT'} />
          <Info label="CPV" value={item.cpv || '—'} />
        </View>

        {item.match_reason ? (
          <View style={styles.highlight}>
            <Text style={styles.highlightLabel}>{item.priority_label || 'RELEVÂNCIA'}</Text>
            <Text style={styles.highlightText}>{item.match_reason}</Text>
          </View>
        ) : null}

        <Section title="Objeto">
          <Text style={styles.bodyText}>{item.description || 'Descrição não disponível.'}</Text>
        </Section>

        <Section title="Fonte oficial">
          <Text style={styles.bodyText}>O ObraSignal apresenta os dados dentro da aplicação. A fonte original permanece disponível para validação documental.</Text>
          <Pressable style={styles.sourceButton} onPress={() => item.url && Linking.openURL(item.url)}>
            <Text style={styles.sourceButtonText}>Abrir fonte oficial</Text>
          </Pressable>
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

function Info({ label, value }) {
  return <View style={styles.infoBox}><Text style={styles.infoLabel}>{label}</Text><Text style={styles.infoValue} numberOfLines={3}>{value}</Text></View>;
}

function Section({ title, children }) {
  return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>;
}

export default function App() {
  const { width } = useWindowDimensions();
  const columns = width >= 760 ? 2 : 1;
  const [tab, setTab] = useState('radar');
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState({ total: 0, high: 0, new24: 0 });
  const [search, setSearch] = useState('');
  const [minscore, setMinscore] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [saved, setSaved] = useState([]);

  useEffect(() => {
    AsyncStorage.getItem(SAVED_KEY).then(raw => raw && setSaved(JSON.parse(raw))).catch(() => {});
  }, []);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ limit: '60', minscore: String(minscore) });
      if (search.trim()) params.set('q', search.trim());
      const [opRes, statRes] = await Promise.all([
        fetch(`${API}/opportunities?${params.toString()}`),
        fetch(`${API}/stats`),
      ]);
      if (!opRes.ok || !statRes.ok) throw new Error('API indisponível');
      const op = await opRes.json();
      const st = await statRes.json();
      setItems(op.items || []);
      setStats(st);
    } catch (e) {
      setError('Não foi possível atualizar agora. O servidor pode estar a acordar — tenta novamente em alguns segundos.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [minscore, search]);

  useEffect(() => { load(); }, [load]);

  const toggleSave = useCallback(async (id) => {
    setSaved(prev => {
      const next = prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id];
      AsyncStorage.setItem(SAVED_KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const visible = useMemo(() => tab === 'saved' ? items.filter(x => saved.includes(x.id)) : items, [items, saved, tab]);

  if (selected) {
    return <Detail item={selected} saved={saved.includes(selected.id)} onBack={() => setSelected(null)} onSave={toggleSave} />;
  }

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="light" />
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.logo}>OBRA<Text style={styles.logoAccent}>SIGNAL</Text></Text>
            <Text style={styles.subtitle}>O radar de obras que trabalha por ti.</Text>
          </View>
          <Pressable onPress={() => load()} style={styles.refresh}><Text style={styles.refreshText}>↻</Text></Pressable>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsRow}>
          <Stat label="Oportunidades" value={stats.total} />
          <Stat label="Novas 24h" value={stats.new24} />
          <Stat label="Alta relevância" value={stats.high} />
        </ScrollView>

        <View style={styles.searchBox}>
          <Text style={styles.searchIcon}>⌕</Text>
          <TextInput
            value={search}
            onChangeText={setSearch}
            onSubmitEditing={() => load()}
            placeholder="Pesquisar obras, metalomecânica, aço..."
            placeholderTextColor={COLORS.muted}
            style={styles.input}
            returnKeyType="search"
          />
          {search ? <Pressable onPress={() => setSearch('')}><Text style={styles.clear}>×</Text></Pressable> : null}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
          {[0, 60, 75, 90].map(v => (
            <Pressable key={v} onPress={() => setMinscore(v)} style={[styles.filter, minscore === v && styles.filterActive]}>
              <Text style={[styles.filterText, minscore === v && styles.filterTextActive]}>{v === 0 ? 'Todas' : `${v}+ relevância`}</Text>
            </Pressable>
          ))}
        </ScrollView>

        {error ? <View style={styles.error}><Text style={styles.errorText}>{error}</Text><Pressable onPress={() => load()}><Text style={styles.retry}>Tentar novamente</Text></Pressable></View> : null}

        {loading ? (
          <View style={styles.loading}><ActivityIndicator color={COLORS.blue} size="large" /><Text style={styles.loadingText}>A procurar oportunidades...</Text></View>
        ) : (
          <FlatList
            key={columns}
            data={visible}
            keyExtractor={x => String(x.id)}
            numColumns={columns}
            columnWrapperStyle={columns > 1 ? styles.column : undefined}
            contentContainerStyle={styles.list}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={COLORS.blue} />}
            ListHeaderComponent={<View style={styles.listHeader}><Text style={styles.listTitle}>{tab === 'saved' ? 'Guardadas' : 'Oportunidades que merecem atenção'}</Text><Text style={styles.listCount}>{visible.length}</Text></View>}
            ListEmptyComponent={<View style={styles.empty}><Text style={styles.emptyTitle}>Nada guardado ainda</Text><Text style={styles.emptyText}>Guarda as oportunidades importantes para as encontrares rapidamente.</Text></View>}
            renderItem={({ item }) => <View style={columns > 1 ? styles.columnItem : undefined}><OpportunityCard item={item} onPress={setSelected} saved={saved.includes(item.id)} onSave={toggleSave} /></View>}
          />
        )}

        <View style={styles.nav}>
          <NavButton icon="⌂" label="Radar" active={tab === 'radar'} onPress={() => setTab('radar')} />
          <NavButton icon="★" label="Guardadas" active={tab === 'saved'} onPress={() => setTab('saved')} />
          <NavButton icon="⚙" label="Perfil" active={tab === 'profile'} onPress={() => setTab('profile')} />
        </View>
      </View>
    </SafeAreaView>
  );
}

function Stat({ label, value }) {
  return <View style={styles.stat}><Text style={styles.statLabel}>{label}</Text><Text style={styles.statValue}>{value ?? '—'}</Text></View>;
}

function NavButton({ icon, label, active, onPress }) {
  return <Pressable onPress={onPress} style={styles.navButton}><Text style={[styles.navIcon, active && { color: COLORS.blue }]}>{icon}</Text><Text style={[styles.navLabel, active && { color: COLORS.blue }]}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  logo: { color: COLORS.text, fontSize: 25, fontWeight: '900', letterSpacing: 1.3 },
  logoAccent: { color: COLORS.blue },
  subtitle: { color: COLORS.muted, fontSize: 12, marginTop: 4 },
  refresh: { width: 42, height: 42, borderRadius: 21, backgroundColor: COLORS.panel2, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: COLORS.line },
  refreshText: { color: COLORS.text, fontSize: 25 },
  statsRow: { paddingHorizontal: 20, gap: 10, paddingVertical: 10 },
  stat: { width: 125, backgroundColor: COLORS.panel, borderWidth: 1, borderColor: COLORS.line, borderRadius: 14, padding: 12 },
  statLabel: { color: COLORS.muted, fontSize: 11 },
  statValue: { color: COLORS.text, fontSize: 22, fontWeight: '800', marginTop: 3 },
  searchBox: { marginHorizontal: 20, height: 48, borderRadius: 14, backgroundColor: COLORS.panel, borderWidth: 1, borderColor: COLORS.line, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 13 },
  searchIcon: { color: COLORS.muted, fontSize: 23, marginRight: 7 },
  input: { flex: 1, color: COLORS.text, fontSize: 14 },
  clear: { color: COLORS.muted, fontSize: 24, paddingLeft: 8 },
  filters: { paddingHorizontal: 20, paddingVertical: 10, gap: 8 },
  filter: { paddingHorizontal: 13, paddingVertical: 8, borderRadius: 999, borderWidth: 1, borderColor: COLORS.line, backgroundColor: COLORS.panel },
  filterActive: { borderColor: COLORS.blue, backgroundColor: '#17294D' },
  filterText: { color: COLORS.muted, fontSize: 12, fontWeight: '600' },
  filterTextActive: { color: COLORS.text },
  list: { paddingHorizontal: 20, paddingBottom: 105 },
  column: { gap: 12 },
  columnItem: { flex: 1 },
  listHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 5, marginBottom: 4 },
  listTitle: { color: COLORS.text, fontSize: 19, fontWeight: '800', flex: 1 },
  listCount: { color: COLORS.blue, fontWeight: '800' },
  card: { backgroundColor: COLORS.panel, borderWidth: 1, borderColor: COLORS.line, borderRadius: 17, padding: 16, marginTop: 12 },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  sourcePill: { backgroundColor: '#202D49', paddingHorizontal: 9, paddingVertical: 5, borderRadius: 999 },
  sourceText: { color: '#B8C7E5', fontSize: 10, fontWeight: '800', letterSpacing: .6 },
  score: { fontSize: 19, fontWeight: '900' },
  cardTitle: { color: COLORS.text, fontSize: 17, fontWeight: '800', lineHeight: 22, marginTop: 12 },
  buyer: { color: '#D1D8E8', fontSize: 13, marginTop: 7, lineHeight: 18 },
  deadline: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 5, marginTop: 11 },
  dot: { width: 6, height: 6, borderRadius: 3, marginRight: 6 },
  deadlineText: { fontWeight: '800', letterSpacing: .2 },
  meta: { color: COLORS.muted, fontSize: 11, marginTop: 9 },
  reason: { color: '#AAB7D0', backgroundColor: '#0C1425', borderRadius: 10, padding: 9, fontSize: 11, lineHeight: 16, marginTop: 10 },
  cardBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 },
  openText: { color: '#91B3FF', fontWeight: '700', fontSize: 12 },
  saveIcon: { color: COLORS.muted, fontSize: 25 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadingText: { color: COLORS.muted },
  error: { margin: 20, padding: 14, borderRadius: 13, backgroundColor: '#301A24', borderWidth: 1, borderColor: '#5B2835' },
  errorText: { color: '#FFC2CA', fontSize: 12, lineHeight: 18 },
  retry: { color: COLORS.blue, fontWeight: '800', marginTop: 9 },
  empty: { padding: 35, alignItems: 'center' },
  emptyTitle: { color: COLORS.text, fontWeight: '800', fontSize: 18 },
  emptyText: { color: COLORS.muted, textAlign: 'center', marginTop: 7, lineHeight: 19 },
  nav: { position: 'absolute', left: 12, right: 12, bottom: 12, height: 68, borderRadius: 20, backgroundColor: '#111A2E', borderWidth: 1, borderColor: COLORS.line, flexDirection: 'row', justifyContent: 'space-around', alignItems: 'center' },
  navButton: { alignItems: 'center', justifyContent: 'center', minWidth: 80 },
  navIcon: { color: COLORS.muted, fontSize: 20 },
  navLabel: { color: COLORS.muted, fontSize: 10, fontWeight: '700', marginTop: 3 },
  detailWrap: { padding: 20, paddingBottom: 50 },
  detailHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 },
  backButton: { paddingVertical: 6 },
  backText: { color: COLORS.blue, fontSize: 15, fontWeight: '700' },
  detailSourceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  detailTitle: { color: COLORS.text, fontSize: 27, lineHeight: 34, fontWeight: '900', marginTop: 13 },
  detailBuyer: { color: '#CDD6E8', fontSize: 15, lineHeight: 21, marginTop: 8 },
  infoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 18 },
  infoBox: { flexGrow: 1, flexBasis: '45%', backgroundColor: COLORS.panel, borderWidth: 1, borderColor: COLORS.line, borderRadius: 13, padding: 11 },
  infoLabel: { color: COLORS.muted, fontSize: 9, fontWeight: '800', letterSpacing: .8 },
  infoValue: { color: COLORS.text, fontSize: 12, fontWeight: '700', marginTop: 5, lineHeight: 17 },
  highlight: { marginTop: 14, backgroundColor: '#10203B', borderWidth: 1, borderColor: '#2B4E89', borderRadius: 14, padding: 13 },
  highlightLabel: { color: COLORS.green, fontSize: 10, fontWeight: '900', letterSpacing: .8 },
  highlightText: { color: '#C7D5EF', fontSize: 12, lineHeight: 18, marginTop: 5 },
  section: { marginTop: 22 },
  sectionTitle: { color: COLORS.text, fontSize: 18, fontWeight: '800', marginBottom: 8 },
  bodyText: { color: '#B5C0D4', fontSize: 14, lineHeight: 22 },
  sourceButton: { marginTop: 12, backgroundColor: COLORS.blue, borderRadius: 12, paddingVertical: 13, alignItems: 'center' },
  sourceButtonText: { color: '#fff', fontWeight: '800' },
});
