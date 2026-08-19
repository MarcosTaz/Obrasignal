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
  Switch,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import AuthGate from './components/AuthGate';
import OpportunityExplanation from './components/OpportunityExplanation';
import { api } from './src/api';
import { DEFAULT_SETTINGS, storage } from './src/storage';
import { configureNotifications } from './src/notifications';

const COLORS = {
  bg: '#070C18', panel: '#10182B', panel2: '#151F36', line: '#253553',
  text: '#F3F6FF', muted: '#9BA8C0', blue: '#5E8BFF', green: '#6FE39A',
  amber: '#FFD66B', red: '#FF8998',
};

const WORKFLOW_OPTIONS = [
  ['NEW', 'Novo'],
  ['REVIEWING', 'Em análise'],
  ['PREPARING', 'A preparar'],
  ['SUBMITTED', 'Proposta enviada'],
  ['WON', 'Ganho'],
  ['LOST', 'Perdido'],
];

function AppContent() {
  const { width } = useWindowDimensions();
  const columns = width >= 760 ? 2 : 1;
  const [tab, setTab] = useState('radar');
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState({ total: 0, high: 0, new24: 0, open: 0 });
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [saved, setSaved] = useState([]);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [notificationBusy, setNotificationBusy] = useState(false);

  useEffect(() => { (async () => {
    const [s, prefs, cache] = await Promise.all([storage.getSaved(), storage.getSettings(), storage.getCache()]);
    setSaved(s); setSettings(prefs);
    if (cache?.items?.length) { setItems(cache.items); setStats(cache.stats || stats); setLoading(false); }
  })(); }, []);

  useEffect(() => { storage.setSettings(settings).catch(() => {}); }, [settings]);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true); setError('');
    try {
      const [op, st] = await Promise.all([
        api.opportunities({ q: search, minscore: tab === 'saved' ? 0 : settings.minScore, openOnly: tab === 'saved' ? false : settings.openOnly, limit: 80 }),
        api.stats(),
      ]);
      const nextItems = op?.items || [];
      setItems(nextItems); setStats(st || {});
      await storage.setCache({ items: nextItems, stats: st || {} });
    } catch (e) {
      if (!items.length) setError('Não foi possível atualizar. O servidor pode estar a acordar — tenta novamente em alguns segundos.');
    } finally { setLoading(false); setRefreshing(false); }
  }, [search, settings.minScore, settings.openOnly, tab]);

  useEffect(() => { load(); }, [load]);

  const toggleSave = useCallback(async (id) => {
    setSaved(prev => { const next = prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]; storage.setSaved(next).catch(() => {}); return next; });
  }, []);

  const visible = useMemo(() => tab === 'saved' ? items.filter(x => saved.includes(x.id)) : items, [items, saved, tab]);

  if (selected) return <Detail initialItem={selected} saved={saved.includes(selected.id)} onBack={() => setSelected(null)} onSave={toggleSave} />;

  return <SafeAreaView style={styles.safe}><StatusBar style="light" /><View style={styles.container}>
    <View style={styles.header}><View><Text style={styles.logo}>OBRA<Text style={styles.logoAccent}>SIGNAL</Text></Text><Text style={styles.subtitle}>O radar de obras que trabalha por ti.</Text></View>
      <Pressable onPress={() => load()} style={styles.refresh}><Text style={styles.refreshText}>↻</Text></Pressable></View>

    {tab !== 'profile' ? <>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsRow}>
        <Stat label="Oportunidades" value={stats.total} /><Stat label="Abertas" value={stats.open} /><Stat label="Novas 24h" value={stats.new24} /><Stat label="Alta relevância" value={stats.high} />
      </ScrollView>
      <View style={styles.searchBox}><Text style={styles.searchIcon}>⌕</Text><TextInput value={search} onChangeText={setSearch} onSubmitEditing={() => load()} placeholder="Pesquisar obras, aço, metalomecânica…" placeholderTextColor={COLORS.muted} style={styles.input} returnKeyType="search" />{search ? <Pressable onPress={() => setSearch('')}><Text style={styles.clear}>×</Text></Pressable> : null}</View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>{[60, 75, 90].map(v => <Pressable key={v} onPress={() => setSettings(s => ({ ...s, minScore: v }))} style={[styles.filter, settings.minScore === v && styles.filterActive]}><Text style={[styles.filterText, settings.minScore === v && styles.filterTextActive]}>{v}+ relevância</Text></Pressable>)}</ScrollView>
      {error ? <View style={styles.error}><Text style={styles.errorText}>{error}</Text><Pressable onPress={() => load()}><Text style={styles.retry}>Tentar novamente</Text></Pressable></View> : null}
      {loading && !items.length ? <View style={styles.loading}><ActivityIndicator color={COLORS.blue} size="large" /><Text style={styles.loadingText}>A procurar oportunidades…</Text></View> : <FlatList key={columns} data={visible} keyExtractor={x => String(x.id)} numColumns={columns} columnWrapperStyle={columns > 1 ? styles.column : undefined} contentContainerStyle={styles.list} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={COLORS.blue} />} ListHeaderComponent={<View style={styles.listHeader}><Text style={styles.listTitle}>{tab === 'saved' ? 'Guardadas' : 'Oportunidades que merecem atenção'}</Text><Text style={styles.listCount}>{visible.length}</Text></View>} ListEmptyComponent={<View style={styles.empty}><Text style={styles.emptyTitle}>{tab === 'saved' ? 'Nada guardado ainda' : 'Nenhuma oportunidade encontrada'}</Text><Text style={styles.emptyText}>{tab === 'saved' ? 'Guarda as oportunidades importantes para as encontrares rapidamente.' : 'Experimenta reduzir o nível de relevância ou alterar a pesquisa.'}</Text></View>} renderItem={({ item }) => <View style={columns > 1 ? styles.columnItem : undefined}><OpportunityCard item={item} onOpen={setSelected} saved={saved.includes(item.id)} onSave={toggleSave} /></View>} />}
    </> : <Profile settings={settings} setSettings={setSettings} notificationBusy={notificationBusy} />}

    <View style={styles.nav}><NavButton icon="⌂" label="Radar" active={tab === 'radar'} onPress={() => setTab('radar')} /><NavButton icon="★" label="Guardadas" active={tab === 'saved'} onPress={() => setTab('saved')} /><NavButton icon="⚙" label="Perfil" active={tab === 'profile'} onPress={() => setTab('profile')} /></View>
  </View></SafeAreaView>;
}

export default function App() {
  return <AuthGate><AppContent /></AuthGate>;
}

function deadlineTone(state) {
  if (state === 'closed') return COLORS.red;
  if (state === 'urgent') return COLORS.amber;
  if (state === 'open') return COLORS.green;
  return COLORS.muted;
}

function Deadline({ item, large = false }) {
  const d = item?.deadline_status || {};
  const tone = deadlineTone(d.state);
  let text = 'PRAZO NÃO INDICADO';
  if (d.state === 'closed') text = 'TERMINADO';
  if (d.state === 'urgent') text = `${String(d.label || 'PRAZO CURTO').toUpperCase()} · ${d.days_remaining ?? 0} DIAS`;
  if (d.state === 'open') text = `ABERTO · ${d.days_remaining} DIAS RESTANTES`;
  return <View style={[styles.deadline, { borderColor: `${tone}55`, backgroundColor: `${tone}12` }]}>
    <View style={[styles.dot, { backgroundColor: tone }]} />
    <Text style={[styles.deadlineText, { color: tone, fontSize: large ? 14 : 11 }]}>{text}</Text>
  </View>;
}

function Score({ value }) {
  const tone = value >= 80 ? COLORS.green : value >= 60 ? COLORS.blue : COLORS.muted;
  return <Text style={[styles.score, { color: tone }]}>{value}/100</Text>;
}

function OpportunityCard({ item, saved, onOpen, onSave }) {
  const accountScore = item?.decision_score;
  const displayScore = accountScore != null ? accountScore : (item?.score || 0);
  return <Pressable onPress={() => onOpen(item)} style={({ pressed }) => [styles.card, pressed && { opacity: 0.86 }]}>
    <View style={styles.cardTop}><View style={styles.sourcePill}><Text style={styles.sourceText}>{item.source}</Text></View><Score value={displayScore} /></View>
    <Text style={styles.cardTitle} numberOfLines={4}>{item.title || 'Sem título'}</Text>
    <Text style={styles.buyer} numberOfLines={2}>{item.buyer || 'Entidade não identificada'}</Text>
    <Deadline item={item} />
    {item.value ? <Text style={styles.meta}>Valor: {item.value}</Text> : null}
    <Text style={styles.reason} numberOfLines={2}>{item.decision_reason || item.match_reason || 'Correspondência com obra'}</Text>
    <View style={styles.cardBottom}><Text style={styles.openText}>Ver oportunidade →</Text>
      <Pressable hitSlop={12} onPress={(e) => { e.stopPropagation?.(); onSave(item.id); }}><Text style={[styles.saveIcon, saved && { color: COLORS.amber }]}>{saved ? '★' : '☆'}</Text></Pressable>
    </View>
  </Pressable>;
}

function WorkflowPanel({ item, onItemChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const current = item?.workflow?.status || 'NEW';

  const update = async (status) => {
    if (status === current || busy) return;
    setBusy(true); setError('');
    try {
      const response = await api.setWorkflow(item.id, status, item?.workflow?.note || null);
      const next = response?.workflow;
      onItemChange?.({ ...item, workflow: next });
    } catch (e) {
      setError('Não foi possível guardar o estado. Tenta novamente.');
    } finally { setBusy(false); }
  };

  return <View style={styles.workflowCard}>
    <View style={styles.workflowHeader}><View><Text style={styles.workflowEyebrow}>AÇÃO COMERCIAL</Text><Text style={styles.workflowTitle}>Estado desta oportunidade</Text></View>{busy ? <ActivityIndicator color={COLORS.blue} size="small" /> : null}</View>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.workflowOptions}>
      {WORKFLOW_OPTIONS.map(([status, label]) => <Pressable key={status} disabled={busy} onPress={() => update(status)} style={[styles.workflowOption, current === status && styles.workflowOptionActive, (status === 'WON' && current === status) && styles.workflowWon, (status === 'LOST' && current === status) && styles.workflowLost]}>
        <Text style={[styles.workflowOptionText, current === status && styles.workflowOptionTextActive]}>{label}</Text>
      </Pressable>)}
    </ScrollView>
    {item?.workflow?.updated_at ? <Text style={styles.workflowMeta}>Atualizado: {item.workflow.updated_at}</Text> : null}
    {error ? <Text style={styles.workflowError}>{error}</Text> : null}
  </View>;
}

function Detail({ initialItem, saved, onBack, onSave }) {
  const [item, setItem] = useState(initialItem);
  const displayScore = item?.decision_score != null ? item.decision_score : (item?.score || 0);
  return <SafeAreaView style={styles.safe}><StatusBar style="light" /><ScrollView contentContainerStyle={styles.detailWrap}>
    <View style={styles.detailHeader}><Pressable onPress={onBack} style={styles.backButton}><Text style={styles.backText}>‹  Voltar</Text></Pressable>
      <Pressable onPress={() => onSave(item.id)}><Text style={[styles.saveIcon, saved && { color: COLORS.amber }]}>{saved ? '★' : '☆'}</Text></Pressable>
    </View>
    <View style={styles.cardTop}><View style={styles.sourcePill}><Text style={styles.sourceText}>{item.source}</Text></View><Score value={displayScore} /></View>
    <Text style={styles.detailTitle}>{item.title || 'Sem título'}</Text>
    <Text style={styles.detailBuyer}>{item.buyer || 'Entidade não identificada'}</Text>
    <Deadline item={item} large />
    <View style={styles.infoGrid}>
      <Info label="PUBLICAÇÃO" value={item.publication_date || '—'} /><Info label="VALOR" value={item.value || 'Não indicado'} />
      <Info label="PAÍS" value={item.country || 'PRT'} /><Info label="CPV" value={item.cpv || '—'} />
    </View>
    <WorkflowPanel item={item} onItemChange={setItem} />
    {item.match_reason ? <View style={styles.highlight}><Text style={styles.highlightLabel}>{item.priority_label || 'RELEVÂNCIA'}</Text><Text style={styles.highlightText}>{item.decision_reason || item.match_reason}</Text></View> : null}
    <OpportunityExplanation item={item} />
    <Section title="Objeto"><Text style={styles.bodyText}>{item.description || 'Descrição não disponível.'}</Text></Section>
    <Section title="Fonte oficial"><Text style={styles.bodyText}>Os dados são apresentados dentro do ObraSignal. A fonte oficial permanece disponível para confirmação documental.</Text>
      <Pressable style={styles.sourceButton} onPress={() => item.url && Linking.openURL(item.url)}><Text style={styles.sourceButtonText}>Abrir fonte oficial</Text></Pressable>
    </Section>
  </ScrollView></SafeAreaView>;
}

function Info({ label, value }) { return <View style={styles.infoBox}><Text style={styles.infoLabel}>{label}</Text><Text style={styles.infoValue} numberOfLines={3}>{value}</Text></View>; }
function Section({ title, children }) { return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>; }

function Profile({ settings, setSettings, notificationBusy }) {
  const set = (patch) => setSettings(prev => ({ ...prev, ...patch }));
  const enableNotifications = async (value) => {
    if (!value) { set({ notifications: false }); return; }
    const granted = await configureNotifications();
    set({ notifications: granted });
  };
  return <ScrollView contentContainerStyle={styles.profileWrap}>
    <Text style={styles.profileTitle}>Perfil</Text>
    <Text style={styles.profileSubtitle}>Controla o que o ObraSignal procura e quando te chama.</Text>
    <View style={styles.settingsCard}>
      <SettingRow title="Só oportunidades abertas" subtitle="Esconde concursos cujo prazo já terminou." value={settings.openOnly} onValueChange={v => set({ openOnly: v })} />
      <View style={styles.settingDivider} />
      <SettingRow title="Notificações" subtitle={notificationBusy ? 'A configurar…' : 'Recebe alertas quando houver oportunidades relevantes.'} value={settings.notifications} onValueChange={enableNotifications} />
    </View>
    <Text style={styles.settingSection}>RELEVÂNCIA MÍNIMA</Text>
    <View style={styles.scoreChoices}>{[60, 75, 90].map(v => <Pressable key={v} onPress={() => set({ minScore: v })} style={[styles.choice, settings.minScore === v && styles.choiceActive]}><Text style={[styles.choiceText, settings.minScore === v && styles.choiceTextActive]}>{v}+</Text></Pressable>)}</View>
    <View style={styles.aboutCard}><Text style={styles.aboutTitle}>ObraSignal</Text><Text style={styles.aboutText}>Radar de concursos e oportunidades de obra. A app comunica diretamente com a API ObraSignal e não depende do dashboard web para funcionar.</Text></View>
  </ScrollView>;
}

function SettingRow({ title, subtitle, value, onValueChange }) {
  return <View style={styles.settingRow}><View style={{ flex: 1 }}><Text style={styles.settingTitle}>{title}</Text><Text style={styles.settingSubtitle}>{subtitle}</Text></View><Switch value={value} onValueChange={onValueChange} trackColor={{ false: '#26324A', true: '#345FC5' }} thumbColor={value ? '#F3F6FF' : '#AAB4C7'} />
  </View>;
}

function Stat({ label, value }) { return <View style={styles.stat}><Text style={styles.statLabel}>{label}</Text><Text style={styles.statValue}>{value ?? '—'}</Text></View>; }
function NavButton({ icon, label, active, onPress }) { return <Pressable onPress={onPress} style={styles.navButton}><Text style={[styles.navIcon, active && { color: COLORS.blue }]}>{icon}</Text><Text style={[styles.navLabel, active && { color: COLORS.blue }]}>{label}</Text></Pressable>; }

const styles = StyleSheet.create({
  safe:{flex:1,backgroundColor:COLORS.bg},container:{flex:1,backgroundColor:COLORS.bg},header:{paddingHorizontal:20,paddingTop:12,paddingBottom:8,flexDirection:'row',justifyContent:'space-between',alignItems:'center'},logo:{color:COLORS.text,fontSize:25,fontWeight:'900',letterSpacing:1.3},logoAccent:{color:COLORS.blue},subtitle:{color:COLORS.muted,fontSize:12,marginTop:4},refresh:{width:42,height:42,borderRadius:21,backgroundColor:COLORS.panel2,alignItems:'center',justifyContent:'center',borderWidth:1,borderColor:COLORS.line},refreshText:{color:COLORS.text,fontSize:25},statsRow:{paddingHorizontal:20,gap:10,paddingVertical:10},stat:{width:125,backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:12,padding:12},statLabel:{fontSize:10,color:COLORS.muted,letterSpacing:.5},statValue:{fontSize:21,fontWeight:'800',color:COLORS.text,marginTop:3},searchBox:{marginHorizontal:20,marginTop:4,backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:12,height:50,flexDirection:'row',alignItems:'center',paddingHorizontal:12},searchIcon:{fontSize:24,color:COLORS.muted,marginRight:8},input:{flex:1,color:COLORS.text,fontSize:14},clear:{fontSize:24,color:COLORS.muted,paddingHorizontal:5},filters:{paddingHorizontal:20,paddingVertical:10,gap:8},filter:{paddingHorizontal:12,paddingVertical:8,borderRadius:9,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},filterActive:{backgroundColor:'#15295A',borderColor:'#345FC5'},filterText:{fontSize:11,color:COLORS.muted},filterTextActive:{color:COLORS.text},list:{paddingHorizontal:20,paddingBottom:110},listHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',paddingVertical:8},listTitle:{fontSize:15,fontWeight:'700',color:COLORS.text},listCount:{fontSize:11,color:COLORS.muted},column:{gap:10},columnItem:{flex:1},card:{backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:14,padding:14,marginBottom:10},cardTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center'},sourcePill:{backgroundColor:COLORS.panel2,borderRadius:999,paddingHorizontal:8,paddingVertical:5},sourceText:{fontSize:10,fontWeight:'700',color:COLORS.muted},score:{fontSize:18,fontWeight:'800'},cardTitle:{fontSize:16,fontWeight:'800',color:COLORS.text,lineHeight:22,marginTop:10},buyer:{fontSize:12,color:COLORS.muted,marginTop:6,lineHeight:17},deadline:{flexDirection:'row',alignItems:'center',alignSelf:'flex-start',borderWidth:1,borderRadius:999,paddingHorizontal:8,paddingVertical:5,marginTop:10},dot:{width:6,height:6,borderRadius:3,marginRight:6},deadlineText:{fontWeight:'800',letterSpacing:.3},meta:{fontSize:11,color:COLORS.muted,marginTop:8},reason:{fontSize:11,color:'#B9C6DF',lineHeight:17,marginTop:9},cardBottom:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginTop:12},openText:{fontSize:11,color:COLORS.blue,fontWeight:'700'},saveIcon:{fontSize:25,color:COLORS.muted},detailWrap:{paddingHorizontal:20,paddingBottom:30},detailHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',paddingVertical:12},backButton:{paddingVertical:8},backText:{color:COLORS.blue,fontWeight:'700'},detailTitle:{fontSize:25,fontWeight:'900',color:COLORS.text,lineHeight:32,marginTop:12},detailBuyer:{fontSize:13,color:COLORS.muted,marginTop:7,lineHeight:20},infoGrid:{flexDirection:'row',flexWrap:'wrap',gap:8,marginTop:14},infoBox:{flexGrow:1,width:'47%',padding:10,borderRadius:10,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},infoLabel:{fontSize:9,color:COLORS.muted,letterSpacing:.7},infoValue:{fontSize:12,fontWeight:'700',color:COLORS.text,marginTop:4},workflowCard:{marginTop:16,padding:14,borderRadius:16,borderWidth:1,borderColor:'#355A8A',backgroundColor:'#0D1B30'},workflowHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center'},workflowEyebrow:{fontSize:9,fontWeight:'900',letterSpacing:1,color:COLORS.blue},workflowTitle:{fontSize:15,fontWeight:'900',color:COLORS.text,marginTop:3},workflowOptions:{gap:8,paddingTop:12,paddingBottom:3},workflowOption:{borderWidth:1,borderColor:COLORS.line,borderRadius:10,paddingHorizontal:11,paddingVertical:9,backgroundColor:COLORS.panel2},workflowOptionActive:{borderColor:'#4A7EE5',backgroundColor:'#17315F'},workflowOptionText:{fontSize:11,fontWeight:'800',color:COLORS.muted},workflowOptionTextActive:{color:COLORS.text},workflowWon:{borderColor:'#3C8B61',backgroundColor:'#123024'},workflowLost:{borderColor:'#8B4C56',backgroundColor:'#32171D'},workflowMeta:{fontSize:9,color:COLORS.muted,marginTop:8},workflowError:{fontSize:11,color:COLORS.red,marginTop:8},highlight:{marginTop:14,padding:12,borderRadius:12,borderWidth:1,borderColor:'#315EA855',backgroundColor:'#0E1D39'},highlightLabel:{fontSize:10,fontWeight:'800',color:COLORS.blue,letterSpacing:.7},highlightText:{fontSize:12,color:COLORS.text,lineHeight:18,marginTop:5},section:{marginTop:18},sectionTitle:{fontSize:15,fontWeight:'800',color:COLORS.text,marginBottom:7},bodyText:{fontSize:13,color:COLORS.muted,lineHeight:21},sourceButton:{marginTop:12,alignSelf:'flex-start',paddingHorizontal:13,paddingVertical:9,borderRadius:9,backgroundColor:COLORS.blue},sourceButtonText:{color:'#fff',fontWeight:'700',fontSize:12},profileWrap:{padding:20,paddingBottom:120},profileTitle:{fontSize:27,fontWeight:'900',color:COLORS.text},profileSubtitle:{fontSize:13,color:COLORS.muted,lineHeight:20,marginTop:5,marginBottom:16},settingsCard:{backgroundColor:COLORS.panel,borderRadius:14,borderWidth:1,borderColor:COLORS.line,paddingHorizontal:14},settingRow:{flexDirection:'row',alignItems:'center',paddingVertical:15},settingTitle:{fontSize:14,fontWeight:'700',color:COLORS.text},settingSubtitle:{fontSize:11,color:COLORS.muted,lineHeight:16,marginTop:3,paddingRight:15},settingDivider:{height:1,backgroundColor:COLORS.line},settingSection:{fontSize:10,color:COLORS.muted,fontWeight:'800',letterSpacing:1,marginTop:22,marginBottom:8},scoreChoices:{flexDirection:'row',gap:8},choice:{flex:1,borderWidth:1,borderColor:COLORS.line,borderRadius:10,paddingVertical:11,alignItems:'center',backgroundColor:COLORS.panel},choiceActive:{borderColor:'#315EA8',backgroundColor:'#15295A'},choiceText:{fontSize:12,color:COLORS.muted,fontWeight:'700'},choiceTextActive:{color:COLORS.text},aboutCard:{marginTop:16,backgroundColor:COLORS.panel,borderRadius:14,borderWidth:1,borderColor:COLORS.line,padding:15},aboutTitle:{fontSize:14,fontWeight:'800',color:COLORS.text},aboutText:{fontSize:11,color:COLORS.muted,lineHeight:18,marginTop:6},loading:{flex:1,alignItems:'center',justifyContent:'center',paddingBottom:100},loadingText:{color:COLORS.muted,fontSize:12,marginTop:12},error:{marginHorizontal:20,marginVertical:8,padding:12,borderRadius:12,borderWidth:1,borderColor:'#55333A',backgroundColor:'#29151A'},errorText:{color:'#FFC5CB',fontSize:12,lineHeight:18},retry:{color:COLORS.blue,fontWeight:'700',fontSize:12,marginTop:6},empty:{padding:40,alignItems:'center'},emptyTitle:{fontSize:15,fontWeight:'700',color:COLORS.text,textAlign:'center'},emptyText:{fontSize:12,color:COLORS.muted,lineHeight:18,textAlign:'center',marginTop:7,maxWidth:320},nav:{position:'absolute',left:12,right:12,bottom:12,height:64,borderRadius:18,borderWidth:1,borderColor:COLORS.line,backgroundColor:'#0F1729F2',flexDirection:'row',alignItems:'center',justifyContent:'space-around'},navButton:{alignItems:'center',justifyContent:'center',gap:4,minWidth:80},navIcon:{fontSize:19,color:COLORS.muted},navLabel:{fontSize:10,fontWeight:'700',color:COLORS.muted}
});
