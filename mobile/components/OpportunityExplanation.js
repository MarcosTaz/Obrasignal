import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import WorkflowFunnel from './WorkflowFunnel';
import { api } from '../src/api';

const COLORS = {
  panel: '#10182B', line: '#253553', text: '#F3F6FF', muted: '#9BA8C0',
  blue: '#5E8BFF', green: '#6FE39A', amber: '#FFD66B', red: '#FF8998',
};
const WATCHLIST_PAGE_SIZE = 20;

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

function SavedOpportunityControl({ item, onChanged }) {
  const [saved, setSaved] = useState(!!item?.workflow?.is_saved);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setSaved(!!item?.workflow?.is_saved);
    setError('');
  }, [item?.id, item?.workflow?.is_saved]);

  const toggleSaved = async () => {
    if (busy || !item?.id) return;
    setBusy(true);
    setError('');
    try {
      if (saved) {
        await api.unsaveOpportunity(item.id);
        setSaved(false);
        onChanged?.();
      } else {
        const response = await api.saveOpportunity(item.id);
        if (response?.saved?.is_saved !== true) throw new Error('invalid_saved_state');
        setSaved(true);
        onChanged?.();
      }
    } catch (_) {
      setError(saved ? 'Não foi possível remover das guardadas.' : 'Não foi possível guardar a oportunidade.');
    } finally {
      setBusy(false);
    }
  };

  const label = saved ? 'Remover das guardadas' : 'Guardar oportunidade';
  return <View style={styles.saveWrap}>
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: busy, selected: saved }}
      disabled={busy}
      onPress={toggleSaved}
      style={[styles.saveButton, saved && styles.saveButtonOn, busy && styles.saveButtonBusy]}
    >
      <Text style={[styles.saveButtonText, saved && styles.saveButtonTextOn]}>{busy ? 'A guardar…' : (saved ? 'Guardada' : 'Guardar')}</Text>
    </Pressable>
    {error ? <Text accessibilityRole="alert" style={styles.saveError}>{error}</Text> : null}
  </View>;
}

function WatchlistRow({ saved }) {
  const status = saved?.status || 'NEW';
  const priority = saved?.priority || 'NORMAL';
  return <View style={styles.watchRow}>
    <View style={styles.watchHeader}>
      <Text style={styles.watchTitle}>{saved?.title || `Oportunidade ${saved?.opportunity_id || '—'}`}</Text>
      <Text style={styles.watchPriority}>{priority}</Text>
    </View>
    <Text style={styles.watchMeta}>{saved?.buyer || 'Entidade não identificada'} · {status}</Text>
    <Text style={styles.watchMeta}>Prazo: {saved?.deadline || 'não indicado'}</Text>
    {saved?.note ? <Text style={styles.watchNote}>{saved.note}</Text> : null}
    {saved?.url ? <Pressable accessibilityRole="link" onPress={() => Linking.openURL(saved.url)}><Text style={styles.watchLink}>Abrir publicação →</Text></Pressable> : null}
  </View>;
}

function SavedOpportunityList({ refreshKey }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [moreLoading, setMoreLoading] = useState(false);
  const [error, setError] = useState('');

  const load = async ({ nextOffset = 0, append = false } = {}) => {
    if (append ? moreLoading : loading) return;
    append ? setMoreLoading(true) : setLoading(true);
    setError('');
    try {
      const response = await api.savedOpportunities({ order: 'recent', limit: WATCHLIST_PAGE_SIZE, offset: nextOffset });
      const fresh = Array.isArray(response?.items) ? response.items : [];
      setItems(current => append
        ? Array.from(new Map([...current, ...fresh].map(value => [value.opportunity_id, value])).values())
        : fresh);
      setOffset(nextOffset);
      setHasMore(fresh.length === WATCHLIST_PAGE_SIZE);
    } catch (_) {
      setError('Não foi possível carregar as oportunidades guardadas.');
    } finally {
      append ? setMoreLoading(false) : setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load({ nextOffset: 0, append: false });
  }, [refreshKey]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) load({ nextOffset: 0, append: false });
  };

  return <View style={styles.watchWrap}>
    <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={toggle} style={styles.watchToggle}>
      <Text style={styles.watchToggleText}>{open ? 'Fechar guardadas' : 'Ver guardadas'}</Text>
    </Pressable>
    {open ? <View style={styles.watchPanel}>
      <Text style={styles.watchHeading}>Oportunidades guardadas</Text>
      <Text style={styles.watchHelp}>Lista privada da tua empresa. Estado, prioridade e notas são dados de acompanhamento, não verdade da fonte.</Text>
      {loading ? <View style={styles.watchLoading}><ActivityIndicator color={COLORS.blue}/><Text style={styles.watchMeta}>A carregar guardadas…</Text></View> : null}
      {error ? <Text accessibilityRole="alert" style={styles.saveError}>{error}</Text> : null}
      {!loading && !error && items.length === 0 ? <Text style={styles.watchEmpty}>Nenhuma oportunidade guardada.</Text> : null}
      {!loading ? items.map(saved => <WatchlistRow key={String(saved.opportunity_id)} saved={saved}/>) : null}
      {!loading && hasMore ? <Pressable disabled={moreLoading} onPress={() => load({ nextOffset: offset + WATCHLIST_PAGE_SIZE, append: true })} style={[styles.watchMore, moreLoading && styles.saveButtonBusy]}><Text style={styles.watchMoreText}>{moreLoading ? 'A carregar…' : 'Carregar mais guardadas'}</Text></Pressable> : null}
    </View> : null}
  </View>;
}

export default function OpportunityExplanation({ item }) {
  const [watchlistRefresh, setWatchlistRefresh] = useState(0);
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
    <SavedOpportunityControl item={item} onChanged={() => setWatchlistRefresh(value => value + 1)} />
    <SavedOpportunityList refreshKey={watchlistRefresh} />
    {visibleFactors.length || blockers.length || negativeFactors.length ? <View style={styles.card}>
      <Text style={styles.heading}>Porque esta oportunidade</Text>
      {visibleFactors.map((factor) => <Factor key={factor.key} title={factor.label} text={factor.reason} score={factor.score} tone={toneForFactor(factor.key)} />)}
      {blockers.length ? <View style={styles.risk}><Text style={styles.riskTitle}>Atenção</Text>{blockers.map((blocker, index) => <Text key={`${blocker}-${index}`} style={styles.riskText}>• {blocker}</Text>)}</View> : null}
      {negativeFactors.length ? <View style={styles.risk}><Text style={styles.riskTitle}>Factores negativos</Text>{negativeFactors.map((factor, index) => <Text key={`${factor.reason}-${index}`} style={styles.riskText}>• {factor.reason}</Text>)}</View> : null}
    </View> : null}
    <WorkflowFunnel refreshKey={`${item?.id || ''}:${item?.workflow?.status || 'NEW'}:${item?.workflow?.updated_at || ''}:${watchlistRefresh}`} />
  </>;
}

const styles = StyleSheet.create({
  saveWrap:{marginTop:14},saveButton:{minHeight:46,borderWidth:1,borderColor:COLORS.blue,borderRadius:12,paddingHorizontal:16,paddingVertical:12,alignItems:'center',justifyContent:'center',backgroundColor:'transparent'},saveButtonOn:{backgroundColor:'#16284C',borderColor:COLORS.green},saveButtonBusy:{opacity:.65},saveButtonText:{color:COLORS.blue,fontSize:13,fontWeight:'900'},saveButtonTextOn:{color:COLORS.green},saveError:{color:COLORS.red,fontSize:11,marginTop:7},
  watchWrap:{marginTop:10},watchToggle:{minHeight:42,borderWidth:1,borderColor:COLORS.line,borderRadius:12,paddingHorizontal:14,paddingVertical:10,alignItems:'center',justifyContent:'center'},watchToggleText:{color:COLORS.text,fontSize:12,fontWeight:'900'},watchPanel:{marginTop:10,padding:12,borderRadius:12,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},watchHeading:{color:COLORS.text,fontSize:15,fontWeight:'900'},watchHelp:{color:COLORS.muted,fontSize:10,lineHeight:15,marginTop:4},watchLoading:{flexDirection:'row',alignItems:'center',gap:8,marginTop:12},watchEmpty:{color:COLORS.muted,fontSize:12,paddingVertical:16,textAlign:'center'},watchRow:{borderTopWidth:1,borderTopColor:COLORS.line,paddingVertical:11,marginTop:8},watchHeader:{flexDirection:'row',justifyContent:'space-between',gap:10},watchTitle:{color:COLORS.text,fontSize:12,fontWeight:'800',flex:1},watchPriority:{color:COLORS.blue,fontSize:10,fontWeight:'900'},watchMeta:{color:COLORS.muted,fontSize:10,marginTop:4},watchNote:{color:COLORS.text,fontSize:11,lineHeight:16,marginTop:6},watchLink:{color:COLORS.blue,fontSize:11,fontWeight:'800',marginTop:7},watchMore:{borderWidth:1,borderColor:COLORS.blue,borderRadius:10,padding:10,alignItems:'center',marginTop:10},watchMoreText:{color:COLORS.blue,fontSize:11,fontWeight:'900'},
  card:{marginTop:14,padding:14,borderRadius:14,borderWidth:1,borderColor:COLORS.line,backgroundColor:COLORS.panel},
  heading:{color:COLORS.text,fontSize:16,fontWeight:'900',marginBottom:5},row:{flexDirection:'row',alignItems:'flex-start',marginTop:10},icon:{width:28,height:28,borderRadius:9,alignItems:'center',justifyContent:'center',marginRight:10},dot:{width:8,height:8,borderRadius:4},body:{flex:1},factorHeader:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:8},title:{color:COLORS.text,fontSize:12,fontWeight:'800'},factorScore:{fontSize:11,fontWeight:'900'},text:{color:COLORS.muted,fontSize:12,lineHeight:17,marginTop:2},risk:{marginTop:14,borderRadius:10,borderWidth:1,borderColor:'#5A4526',backgroundColor:'#241D10',padding:10},riskTitle:{color:COLORS.amber,fontSize:10,fontWeight:'900',textTransform:'uppercase',letterSpacing:.6},riskText:{color:COLORS.text,fontSize:12,lineHeight:18,marginTop:4},
});
