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
import { api } from './src/api';
import { DEFAULT_SETTINGS, storage } from './src/storage';
import { configureNotifications } from './src/notifications';

const COLORS = {
  bg: '#070C18', panel: '#10182B', panel2: '#151F36', line: '#253553',
  text: '#F3F6FF', muted: '#9BA8C0', blue: '#5E8BFF', green: '#6FE39A',
  amber: '#FFD66B', red: '#FF8998',
};

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
  return <Pressable onPress={() => onOpen(item)} style={({ pressed }) => [styles.card, pressed && { opacity: 0.86 }]}>
    <View style={styles.cardTop}><View style={styles.sourcePill}><Text style={styles.sourceText}>{item.source}</Text></View><Score value={item.score || 0} /></View>
    <Text style={styles.cardTitle} numberOfLines={4}>{item.title || 'Sem título'}</Text>
    <Text style={styles.buyer} numberOfLines={2}>{item.buyer || 'Entidade não identificada'}</Text>
    <Deadline item={item} />
    {item.value ? <Text style={styles.meta}>Valor: {item.value}</Text> : null}
    <Text style={styles.reason} numberOfLines={2}>{item.match_reason || 'Correspondência com obra'}</Text>
    <View style={styles.cardBottom}><Text style={styles.openText}>Ver oportunidade →</Text>
      <Pressable hitSlop={12} onPress={(e) => { e.stopPropagation?.(); onSave(item.id); }}><Text style={[styles.saveIcon, saved && { color: COLORS.amber }]}>{saved ? '★' : '☆'}</Text></Pressable>
    </View>
  </Pressable>;
}

function Detail({ item, saved, onBack, onSave }) {
  return <SafeAreaView style={styles.safe}><StatusBar style="light" /><ScrollView contentContainerStyle={styles.detailWrap}>
    <View style={styles.detailHeader}><Pressable onPress={onBack} style={styles.backButton}><Text style={styles.backText}>‹  Voltar</Text></Pressable>
      <Pressable onPress={() => onSave(item.id)}><Text style={[styles.saveIcon, saved && { color: COLORS.amber }]}>{saved ? '★' : '☆'}</Text></Pressable>
    </View>
    <View style={styles.cardTop}><View style={styles.sourcePill}><Text style={styles.sourceText}>{item.source}</Text></View><Score value={item.score || 0} /></View>
    <Text style={styles.detailTitle}>{item.title || 'Sem título'}</Text>
    <Text style={styles.detailBuyer}>{item.buyer || 'Entidade não identificada'}</Text>
    <Deadline item={item} large />
    <View style={styles.infoGrid}>
      <Info label="PUBLICAÇÃO" value={item.publication_date || '—'} /><Info label="VALOR" value={item.value || 'Não indicado'} />
      <Info label="PAÍS" value={item.country || 'PRT'} /><Info label="CPV" value={item.cpv || '—'} />
    </View>
    {item.match_reason ? <View style={styles.highlight}><Text style={styles.highlightLabel}>{item.priority_label || 'RELEVÂNCIA'}</Text><Text style={styles.highlightText}>{item.match_reason}</Text></View> : null}
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

export default function App() {
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

  if (selected) return <Detail item={selected} saved={saved.includes(selected.id)} onBack={() => setSelected(null)} onSave={toggleSave} />;

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

const styles = StyleSheet.create({
  safe:{flex:1,backgroundColor:COLORS.bg},container:{flex:1,backgroundColor:COLORS.bg},header:{paddingHorizontal:20,paddingTop:12,paddingBottom:8,flexDirection:'row',justifyContent:'space-between',alignItems:'center'},logo:{color:COLORS.text,fontSize:25,fontWeight:'900',letterSpacing:1.3},logoAccent:{color:COLORS.blue},subtitle:{color:COLORS.muted,fontSize:12,marginTop:4},refresh:{width:42,height:42,borderRadius:21,backgroundColor:COLORS.panel2,alignItems:'center',justifyContent:'center',borderWidth:1,borderColor:COLORS.line},refreshText:{color:COLORS.text,fontSize:25},statsRow:{paddingHorizontal:20,gap:10,paddingVertical:10},stat:{width:125,backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:14,padding:12},statLabel:{color:COLORS.muted,fontSize:11},statValue:{color:COLORS.text,fontSize:22,fontWeight:'800',marginTop:3},searchBox:{marginHorizontal:20,height:48,borderRadius:14,backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,flexDirection:'row',alignItems:'center',paddingHorizontal:13},searchIcon:{color:COLORS.muted,fontSize:23,marginRight:7},input:{flex:1,color:COLORS.text,fontSize:14},clear:{color:COLORS.muted,fontSize:24,paddingLeft:8},filters:{paddingHorizontal:20,paddingVertical:10,gap:8},filter:{paddingHorizontal:13,paddingVertical:8,borderRadius:999,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},filterActive:{borderColor:COLORS.blue,backgroundColor:'#17294D'},filterText:{color:COLORS.muted,fontSize:12,fontWeight:'600'},filterTextActive:{color:COLORS.text},list:{paddingHorizontal:20,paddingBottom:105},column:{gap:12},columnItem:{flex:1},listHeader:{flexDirection:'row',alignItems:'center',gap:8,marginTop:5,marginBottom:4},listTitle:{color:COLORS.text,fontSize:17,fontWeight:'800'},listCount:{color:COLORS.muted,fontSize:12,backgroundColor:COLORS.panel2,paddingHorizontal:8,paddingVertical:4,borderRadius:99},card:{backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:16,padding:15,marginVertical:7,flex:1},cardTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:8},sourcePill:{backgroundColor:'#22304E',borderRadius:999,paddingHorizontal:9,paddingVertical:5},sourceText:{color:'#C8D5F0',fontSize:11,fontWeight:'800'},score:{fontSize:19,fontWeight:'900'},cardTitle:{color:COLORS.text,fontSize:16,fontWeight:'800',lineHeight:21,marginTop:10},buyer:{color:'#C3CDE0',fontSize:13,lineHeight:18,marginTop:7},deadline:{flexDirection:'row',alignItems:'center',gap:6,borderWidth:1,borderRadius:9,paddingHorizontal:9,paddingVertical:7,marginTop:10,alignSelf:'flex-start'},dot:{width:7,height:7,borderRadius:4},deadlineText:{fontWeight:'800'},meta:{color:COLORS.muted,fontSize:12,marginTop:8},reason:{color:'#B9C6DF',fontSize:12,lineHeight:17,backgroundColor:'#0D1628',padding:9,borderRadius:9,marginTop:9},cardBottom:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginTop:9},openText:{color:'#8DB4FF',fontSize:13,fontWeight:'700'},saveIcon:{color:'#71809D',fontSize:25},detailWrap:{padding:20,paddingBottom:50},detailHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginBottom:16},backButton:{paddingVertical:5},backText:{color:COLORS.blue,fontSize:16,fontWeight:'700'},detailTitle:{color:COLORS.text,fontSize:25,fontWeight:'900',lineHeight:31,marginTop:15},detailBuyer:{color:'#C3CDE0',fontSize:15,lineHeight:21,marginTop:8},infoGrid:{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:16},infoBox:{width:'48%',backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:12,padding:11},infoLabel:{color:COLORS.muted,fontSize:9,fontWeight:'800'},infoValue:{color:COLORS.text,fontSize:12,fontWeight:'700',marginTop:4},highlight:{backgroundColor:'#14213C',borderWidth:1,borderColor:'#31518B',borderRadius:14,padding:14,marginTop:16},highlightLabel:{color:COLORS.green,fontSize:11,fontWeight:'900'},highlightText:{color:'#D6E0F2',fontSize:13,lineHeight:19,marginTop:5},section:{marginTop:22},sectionTitle:{color:COLORS.text,fontSize:17,fontWeight:'800',marginBottom:8},bodyText:{color:'#C0CADB',fontSize:14,lineHeight:21},sourceButton:{backgroundColor:COLORS.blue,borderRadius:12,padding:13,alignItems:'center',marginTop:13},sourceButtonText:{color:'#fff',fontWeight:'800'},error:{marginHorizontal:20,marginBottom:6,padding:12,borderRadius:12,backgroundColor:'#321B25',borderWidth:1,borderColor:'#6B3144'},errorText:{color:'#F4C6D0',fontSize:12,lineHeight:17},retry:{color:COLORS.blue,fontWeight:'800',marginTop:6},loading:{flex:1,alignItems:'center',justifyContent:'center',gap:10},loadingText:{color:COLORS.muted},empty:{padding:30,alignItems:'center'},emptyTitle:{color:COLORS.text,fontSize:17,fontWeight:'800'},emptyText:{color:COLORS.muted,textAlign:'center',marginTop:7,lineHeight:19},nav:{position:'absolute',left:12,right:12,bottom:10,height:66,backgroundColor:'#0F1729',borderWidth:1,borderColor:COLORS.line,borderRadius:20,flexDirection:'row',justifyContent:'space-around',alignItems:'center'},navButton:{alignItems:'center',justifyContent:'center',minWidth:80},navIcon:{color:COLORS.muted,fontSize:21},navLabel:{color:COLORS.muted,fontSize:10,fontWeight:'700',marginTop:2},profileWrap:{padding:20,paddingBottom:120},profileTitle:{color:COLORS.text,fontSize:28,fontWeight:'900'},profileSubtitle:{color:COLORS.muted,fontSize:13,lineHeight:19,marginTop:5,marginBottom:18},settingsCard:{backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:16,paddingHorizontal:15},settingRow:{flexDirection:'row',alignItems:'center',paddingVertical:16,gap:12},settingDivider:{height:1,backgroundColor:COLORS.line},settingTitle:{color:COLORS.text,fontSize:14,fontWeight:'800'},settingSubtitle:{color:COLORS.muted,fontSize:11,lineHeight:16,marginTop:3},settingSection:{color:COLORS.muted,fontSize:10,fontWeight:'900',marginTop:25,marginBottom:10},scoreChoices:{flexDirection:'row',gap:10},choice:{flex:1,paddingVertical:13,borderRadius:12,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel,alignItems:'center'},choiceActive:{borderColor:COLORS.blue,backgroundColor:'#17294D'},choiceText:{color:COLORS.muted,fontWeight:'800'},choiceTextActive:{color:COLORS.text},aboutCard:{backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.line,borderRadius:16,padding:15,marginTop:25},aboutTitle:{color:COLORS.text,fontSize:16,fontWeight:'900'},aboutText:{color:COLORS.muted,fontSize:12,lineHeight:18,marginTop:6}
});
