import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, SafeAreaView, ScrollView, StyleSheet, Switch, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import AuthGate from './components/AuthGate';
import OpportunityExplanation from './components/OpportunityExplanation';
import ProfileOnboarding from './components/ProfileOnboarding';
import { supabase } from './lib/supabase';
import { api } from './src/api';
import { DEFAULT_SETTINGS, storage } from './src/storage';
import { syncUnreadOpportunityAlerts } from './src/notifications';

const FONT = 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const C = {
  bg: '#07111C',
  panel: '#0D1A29',
  panel2: '#101F31',
  line: '#22364F',
  text: '#F4F7FB',
  muted: '#9BAABD',
  muted2: '#6F829A',
  blue: '#5F8DF7',
  blueSoft: '#15294C',
  green: '#72DFA1',
  amber: '#EFCB78',
  red: '#FF8B9A',
};
const STATES = [['NEW','Novo'],['REVIEWING','Em análise'],['PREPARING','A preparar'],['SUBMITTED','Proposta enviada'],['WON','Ganho'],['LOST','Perdido']];

export default function App(){ return <AuthGate><WebMain/></AuthGate>; }

function Brand(){
  return <Text style={s.brand}>Obra<Text style={s.brandSignal}>Signal</Text></Text>;
}

function WebMain(){
  const { width } = useWindowDimensions();
  const compact = width < 760;
  const [tab,setTab] = useState('radar');
  const [items,setItems] = useState([]);
  const [stats,setStats] = useState({});
  const [settings,setSettings] = useState(DEFAULT_SETTINGS);
  const [profile,setProfile] = useState(undefined);
  const [selected,setSelected] = useState(null);
  const [loading,setLoading] = useState(true);
  const [profileLoading,setProfileLoading] = useState(true);
  const [saving,setSaving] = useState(false);
  const [radarError,setRadarError] = useState('');
  const [profileError,setProfileError] = useState('');
  const [search,setSearch] = useState('');
  const [notice,setNotice] = useState('');
  const requestId = useRef(0);
  const mounted = useRef(true);

  const load = useCallback(async ({criteria=settings}={}) => {
    const id = ++requestId.current;
    setRadarError('');
    setProfileError('');
    setLoading(true);
    setProfileLoading(true);
    try {
      const [profileResult,opResult,statsResult] = await Promise.allSettled([
        api.profile(),
        api.opportunities({ q:search, minscore:criteria.minScore, openOnly:criteria.openOnly, limit:80 }),
        api.stats(),
      ]);
      if (!mounted.current || id !== requestId.current) return;
      if (profileResult.status === 'fulfilled') {
        setProfile(profileResult.value);
        if (profileResult.value) storage.setProfile(profileResult.value).catch(()=>{});
      } else {
        setProfileError(profileResult.reason?.message || 'Não foi possível atualizar o perfil.');
      }
      if (opResult.status === 'fulfilled') {
        const nextItems = opResult.value?.items || [];
        const nextStats = statsResult.status === 'fulfilled' ? (statsResult.value || {}) : stats;
        setItems(nextItems);
        if (statsResult.status === 'fulfilled') setStats(nextStats);
        storage.setCache({items:nextItems,stats:nextStats}).catch(()=>{});
      } else {
        if (statsResult.status === 'fulfilled') setStats(statsResult.value || {});
        setRadarError(opResult.reason?.message || 'Não foi possível atualizar o Radar.');
      }
    } finally {
      if (mounted.current && id === requestId.current) {
        setLoading(false);
        setProfileLoading(false);
      }
    }
  }, [search, settings, stats]);

  useEffect(()=>{
    mounted.current = true;
    let active = true;
    (async()=>{
      let savedSettings = DEFAULT_SETTINGS;
      const hydrated = await Promise.allSettled([storage.getSettings(),storage.getCache(),storage.getProfile()]);
      if (!active) return;
      if (hydrated[0].status === 'fulfilled') { savedSettings = hydrated[0].value; setSettings(savedSettings); }
      if (hydrated[1].status === 'fulfilled' && hydrated[1].value) { setItems(hydrated[1].value.items || []); setStats(hydrated[1].value.stats || {}); setLoading(false); }
      if (hydrated[2].status === 'fulfilled' && hydrated[2].value) setProfile(hydrated[2].value);
      await load({criteria:savedSettings});
    })();
    return ()=>{ active=false; mounted.current=false; };
  }, []);

  useEffect(()=>{ storage.setSettings(settings).catch(()=>{}); }, [settings]);
  useEffect(()=>{
    if (!settings.notifications) { setNotice(''); return; }
    let active = true;
    (async()=>{
      try {
        const delivered = await syncUnreadOpportunityAlerts();
        if (active) setNotice(delivered > 0 ? `${delivered} alerta(s) novo(s).` : 'Notificações activadas.');
      } catch (_) {
        if (active) setNotice('Alertas Web ativos; push depende da aplicação nativa.');
      }
    })();
    return ()=>{active=false;};
  }, [settings.notifications]);

  const applyCriteria = patch => {
    const criteria = {...settings,...patch};
    setSettings(criteria);
    load({criteria});
  };
  const saveProfile = async patch => {
    setSaving(true); setProfileError('');
    try {
      const next = await api.saveProfile({...profile,...patch});
      setProfile(next);
      await storage.setProfile(next);
      setTab('radar');
      await load();
    } catch (e) {
      setProfileError(e?.responseBody?.error || e?.message || 'Não foi possível guardar o perfil.');
    } finally { setSaving(false); }
  };

  if (!profileLoading && profile !== undefined && (!profile?.name?.trim() || !profile?.activity?.trim())) {
    return <SafeAreaView style={s.safe}><ProfileOnboarding initialProfile={profile||{}} onComplete={next=>{setProfile(next);load();}}/></SafeAreaView>;
  }

  if (selected) return <OpportunityDetail item={selected} compact={compact} onBack={()=>setSelected(null)} onChanged={next=>{setSelected(next);setItems(old=>old.map(item=>item.id===next.id?next:item));}}/>;

  return <SafeAreaView style={s.safe}>
    <StatusBar style="light"/>
    <ScrollView style={s.pageScroll} contentContainerStyle={s.pageContent} keyboardShouldPersistTaps="handled">
      <View style={[s.shell,compact&&s.shellCompact]}>
        <Header onRefresh={()=>load()}/>
        <Nav tab={tab} setTab={setTab}/>
        {tab === 'profile'
          ? <ProfilePanel profile={profile} profileLoading={profileLoading} error={profileError} settings={settings} setSettings={setSettings} onOpenOnlyChange={value=>applyCriteria({openOnly:value})} onSave={saveProfile} saving={saving} notice={notice}/>
          : <RadarPanel compact={compact} items={items} stats={stats} settings={settings} search={search} setSearch={setSearch} loading={loading} error={radarError} notice={notice} onRefresh={()=>load()} onSearch={()=>load()} onMinScore={value=>applyCriteria({minScore:value})} onOpen={setSelected}/>
        }
      </View>
    </ScrollView>
  </SafeAreaView>;
}

function Header({onRefresh}){
  return <View style={s.header}>
    <View><Brand/><Text style={s.headerSubtitle}>Decisão comercial para contratação pública</Text></View>
    <Pressable onPress={onRefresh} style={({pressed})=>[s.refreshButton,pressed&&s.pressed]}><Text style={s.refreshIcon}>↻</Text><Text style={s.refreshText}>Atualizar</Text></Pressable>
  </View>;
}

function Nav({tab,setTab}){
  return <View style={s.nav}>
    {['radar','profile'].map(key=><Pressable key={key} onPress={()=>setTab(key)} style={[s.navItem,tab===key&&s.navItemOn]}><Text style={[s.navText,tab===key&&s.navTextOn]}>{key==='radar'?'Radar':'Perfil'}</Text></Pressable>)}
  </View>;
}

function RadarPanel({compact,items,stats,settings,search,setSearch,loading,error,notice,onRefresh,onSearch,onMinScore,onOpen}){
  const visible = useMemo(()=>items,[items]);
  const statValues = [['Oportunidades',stats.total],['Abertas',stats.open],['Novas 24h',stats.new24],['Alta relevância',stats.high]];
  return <View style={s.bodyWrap}>
    <View style={[s.workspaceIntro,compact&&s.stack]}>
      <View style={s.workspaceCopy}><Text style={s.eyebrow}>RADAR COMERCIAL</Text><Text style={[s.workspaceTitle,compact&&s.workspaceTitleCompact]}>Oportunidades que merecem atenção.</Text><Text style={s.workspaceBody}>Priorizadas pelo perfil da tua empresa, com razão de encaixe e fonte oficial sempre acessível.</Text></View>
      <View style={[s.workspaceMeta,compact&&s.workspaceMetaCompact]}><Text style={s.metaKicker}>ATUALIZAÇÃO</Text><Text style={s.metaValue}>{stats.last_sync?new Date(stats.last_sync).toLocaleString():'A sincronizar'}</Text></View>
    </View>
    <View style={[s.statsGrid,compact&&s.statsGridCompact]}>{statValues.map(([label,value])=><View style={s.stat} key={label}><Text style={s.statValue}>{value??0}</Text><Text style={s.statLabel}>{label}</Text></View>)}</View>
    <View style={[s.tools,compact&&s.stack]}>
      <View style={s.search}><Text style={s.searchIcon}>⌕</Text><TextInput value={search} onChangeText={setSearch} onSubmitEditing={onSearch} placeholder="Pesquisar por obra, entidade ou CPV…" placeholderTextColor={C.muted2} style={s.input}/></View>
      <View style={s.filters}>{[60,75,90].map(v=><Pressable key={v} onPress={()=>onMinScore(v)} style={[s.filter,settings.minScore===v&&s.filterOn]}><Text style={[s.filterText,settings.minScore===v&&s.filterTextOn]}>{v}+ relevância</Text></Pressable>)}</View>
    </View>
    {notice?<Text style={s.notice}>{notice}</Text>:null}
    {error?<ErrorNotice message={error} onRetry={onRefresh}/>:null}
    <View style={s.listHead}><Text style={s.sectionTitle}>Radar</Text><Text style={s.listCount}>{visible.length} resultado(s)</Text></View>
    {loading?<Skeleton/>:visible.length?visible.map(item=><OpportunityCard key={String(item.id)} item={item} onOpen={()=>onOpen(item)}/>):<Text style={s.empty}>Sem resultados com estes filtros. Reduz a relevância mínima ou ajusta os critérios da empresa.</Text>}
  </View>;
}

function OpportunityCard({item,onOpen}){
  const score=item.decision_score??item.score??0;
  const deadline=item.deadline_status?.label||item.deadline||'Prazo não indicado';
  return <Pressable onPress={onOpen} style={({pressed})=>[s.card,pressed&&s.cardPressed]}>
    <View style={s.cardTop}><View style={s.sourcePill}><Text style={s.source}>{item.source||'TED'}</Text></View><Text style={[s.score,{color:score>=80?C.green:C.blue}]}>{score}/100</Text></View>
    <Text style={s.cardTitle}>{item.title||'Sem título'}</Text><Text style={s.buyer}>{item.buyer||'Entidade não identificada'}</Text>
    <View style={s.cardFacts}>{item.value?<Text style={s.meta}>Valor · {item.value}</Text>:null}<Text style={s.meta}>Prazo · {deadline}</Text></View>
    <View style={s.reasonBox}><Text style={s.reasonLabel}>PORQUE APARECEU</Text><Text style={s.reason}>{item.decision_reason||item.match_reason||'Correspondência com o perfil'}</Text></View>
    <Text style={s.open}>Ver oportunidade →</Text>
  </Pressable>;
}

function OpportunityDetail({item,onBack,onChanged,compact}){
  const [current,setCurrent]=useState(null); const [note,setNote]=useState(''); const [busy,setBusy]=useState(false); const [error,setError]=useState('');
  useEffect(()=>{let active=true; api.opportunity(item.id).then(fresh=>{if(!active)return;setCurrent(fresh);setNote(fresh?.workflow?.note||'');onChanged(fresh);}).catch(e=>{if(active)setError(e?.message||'Não foi possível obter o detalhe.');}); return()=>{active=false;};},[item.id]);
  const update=async(next=current?.workflow?.status||'NEW',nextNote=note)=>{if(!current||busy)return;setBusy(true);setError('');try{const result=await api.setWorkflow(current.id,next,nextNote);const workflow=result?.workflow||result;const value={...current,workflow};setCurrent(value);onChanged(value);}catch(_){setError('Não foi possível guardar o acompanhamento.');}finally{setBusy(false);}};
  return <SafeAreaView style={s.safe}><StatusBar style="light"/><ScrollView style={s.pageScroll} contentContainerStyle={s.detailPage}>
    <Pressable onPress={onBack}><Text style={s.back}>← Voltar ao Radar</Text></Pressable>
    {!current&&!error?<View style={s.loader}><ActivityIndicator color={C.blue}/><Text style={s.muted}>A obter o detalhe atual…</Text></View>:null}
    {error&&!current?<ErrorNotice message={error} onRetry={()=>{}}/>:null}
    {current?<View>
      <View style={[s.detailTop,compact&&s.stack]}><View style={s.sourcePill}><Text style={s.source}>{current.source||'TED'} · {current.external_id||'referência oficial'}</Text></View><Text style={s.deadline}>{current.deadline_status?.label||'Prazo não indicado'}</Text></View>
      <Text style={[s.detailTitle,compact&&s.detailTitleCompact]}>{current.title||'Sem título'}</Text><Text style={s.buyer}>{current.buyer||'Entidade não identificada'}</Text>
      <Text style={s.detailScore}>{current.decision_score??current.score??0}<Text style={s.scoreOutOf}>/100</Text></Text>
      <View style={s.factGrid}>{current.value?<Fact label="VALOR ESTIMADO" value={current.value}/>:null}<Fact label="PRAZO" value={current.deadline||'não indicado'}/><Fact label="PUBLICAÇÃO" value={current.publication_date||'não indicada'}/>{current.cpv?<Fact label="CPV" value={current.cpv}/>:null}</View>
      <View style={s.workflow}><Text style={s.eyebrow}>ACOMPANHAMENTO COMERCIAL</Text><View style={s.stateRow}>{STATES.map(([key,label])=><Pressable key={key} disabled={busy} onPress={()=>update(key)} style={[s.state,current.workflow?.status===key&&s.stateOn]}><Text style={[s.stateText,current.workflow?.status===key&&s.stateTextOn]}>{label}</Text></Pressable>)}</View><TextInput value={note} onChangeText={setNote} multiline placeholder="Próximo passo, contacto ou nota interna…" placeholderTextColor={C.muted2} style={[s.field,s.note]}/><Pressable disabled={busy} onPress={()=>update(current.workflow?.status||'NEW',note)} style={s.secondaryButton}><Text style={s.secondaryButtonText}>{busy?'A guardar…':'Guardar nota'}</Text></Pressable>{error?<Text style={s.errorText}>{error}</Text>:null}</View>
      <OpportunityExplanation item={current}/><Text style={s.heading}>Objeto do contrato</Text><Text style={s.body}>{current.description||'Descrição não disponível. Consulta a publicação oficial antes de tomar uma decisão.'}</Text>{current.url?<Pressable style={s.primaryButton} onPress={()=>Linking.openURL(current.url)}><Text style={s.primaryButtonText}>Abrir fonte oficial e documentos</Text></Pressable>:null}<Text style={s.trust}>Confirma sempre prazo, requisitos e contactos na fonte oficial. O scoring é uma recomendação baseada no perfil da tua empresa.</Text>
    </View>:null}
  </ScrollView></SafeAreaView>;
}
function Fact({label,value}){return <View style={s.fact}><Text style={s.factLabel}>{label}</Text><Text style={s.factValue}>{value}</Text></View>;}

function ProfilePanel({profile,profileLoading,error,settings,setSettings,onOpenOnlyChange,onSave,saving,notice}){
  if(profileLoading&&!profile)return <View style={s.loader}><ActivityIndicator color={C.blue}/><Text style={s.muted}>A carregar o perfil…</Text></View>;
  if(!profile)return error?<ErrorNotice message={error} onRetry={()=>{}}/>:null;
  return <ProfileForm profile={profile} settings={settings} setSettings={setSettings} onOpenOnlyChange={onOpenOnlyChange} onSave={onSave} saving={saving} notice={notice} error={error}/>;
}

function ProfileForm({profile,settings,setSettings,onOpenOnlyChange,onSave,saving,notice,error}){
  const [name,setName]=useState(profile.name||''); const [activity,setActivity]=useState(profile.activity||''); const [interests,setInterests]=useState((profile.contract_interests||profile.keywords||[]).join('\n')); const [cpv,setCpv]=useState((profile.cpv_prefixes||[]).join(', ')); const [coverage,setCoverage]=useState(profile.coverage_mode||(profile.regions?.length?'regions':'portugal')); const [regions,setRegions]=useState((profile.regions||[]).join(', ')); const [countries,setCountries]=useState(profile.countries||['PRT']); const [minValue,setMinValue]=useState(profile.min_value==null?'':String(profile.min_value)); const [maxValue,setMaxValue]=useState(profile.max_value==null?'':String(profile.max_value));
  const list=v=>v.split(/[,\n]/).map(x=>x.trim()).filter(Boolean);
  const toggleCountry=code=>setCountries(x=>x.includes(code)?(code==='PRT'?x:x.filter(c=>c!==code)):[...x,code]);
  const save=()=>onSave({name:name.trim(),activity:activity.trim(),contract_interests:list(interests),coverage_mode:coverage,countries:coverage==='europe'?countries:['PRT'],regions:coverage==='regions'?list(regions):[],cpv_prefixes:list(cpv),min_value:minValue===''?null:Number(minValue),max_value:maxValue===''?null:Number(maxValue)});
  return <View style={s.profileWrap}><Text style={s.eyebrow}>PERFIL COMERCIAL</Text><Text style={s.profileTitle}>O teu perfil define o Radar.</Text><Text style={s.workspaceBody}>Descreve o negócio em linguagem normal; os critérios são usados para ordenar o que merece atenção.</Text>
    <View style={s.formCard}><Label text="Empresa"/><TextInput value={name} onChangeText={setName} placeholder="Nome da empresa" placeholderTextColor={C.muted2} style={s.field}/><Label text="Actividade principal"/><TextInput value={activity} onChangeText={setActivity} placeholder="Ex.: instalações eléctricas" placeholderTextColor={C.muted2} style={s.field}/><Label text="Trabalhos e contratos que procuras"/><TextInput value={interests} onChangeText={setInterests} multiline placeholder={'Ex.: manutenção de escolas\nInstalação de painéis solares'} placeholderTextColor={C.muted2} style={[s.field,s.note]}/><Label text="Onde aceitas trabalhar?"/><View style={s.filters}>{[['portugal','Todo Portugal'],['regions','Zonas específicas'],['europe','Outros mercados']].map(([key,label])=><Pressable key={key} onPress={()=>setCoverage(key)} style={[s.filter,coverage===key&&s.filterOn]}><Text style={[s.filterText,coverage===key&&s.filterTextOn]}>{label}</Text></Pressable>)}</View>{coverage==='regions'?<TextInput value={regions} onChangeText={setRegions} placeholder="Distritos, regiões ou cidades" placeholderTextColor={C.muted2} style={s.field}/>:null}{coverage==='europe'?<View style={s.filters}>{[['PRT','Portugal'],['ESP','Espanha'],['FRA','França']].map(([code,label])=><Pressable key={code} onPress={()=>toggleCountry(code)} style={[s.filter,countries.includes(code)&&s.filterOn]}><Text style={[s.filterText,countries.includes(code)&&s.filterTextOn]}>{label}</Text></Pressable>)}</View>:null}<Label text="Intervalo habitual dos contratos (€)"/><View style={s.valueRow}><TextInput value={minValue} onChangeText={setMinValue} placeholder="A partir de €" placeholderTextColor={C.muted2} style={[s.field,s.valueField]}/><TextInput value={maxValue} onChangeText={setMaxValue} placeholder="Até €" placeholderTextColor={C.muted2} style={[s.field,s.valueField]}/></View><Label text="Avançado · famílias CPV"/><TextInput value={cpv} onChangeText={setCpv} placeholder="45, 4531" placeholderTextColor={C.muted2} style={s.field}/>{error?<Text style={s.errorText}>{error}</Text>:null}<Pressable onPress={save} disabled={saving} style={s.primaryButton}><Text style={s.primaryButtonText}>{saving?'A guardar…':'Guardar e recalcular o Radar'}</Text></Pressable></View>
    <View style={s.settingsCard}><Setting title="Só oportunidades abertas" copy="Oculta procedimentos já encerrados." value={!!settings.openOnly} onValueChange={onOpenOnlyChange}/><Setting title="Notificações" copy={notice||'Alertas para novas oportunidades relevantes.'} value={!!settings.notifications} onValueChange={value=>setSettings(x=>({...x,notifications:value}))}/></View>
    <Pressable onPress={()=>supabase.auth.signOut()} style={s.signOut}><Text style={s.signOutText}>Terminar sessão</Text></Pressable>
  </View>;
}
function Label({text}){return <Text style={s.label}>{text}</Text>;}
function Setting({title,copy,value,onValueChange}){return <View style={s.setting}><View style={s.settingCopy}><Text style={s.settingTitle}>{title}</Text><Text style={s.muted}>{copy}</Text></View><Switch value={value} onValueChange={onValueChange}/></View>;}
function ErrorNotice({message,onRetry}){return <View style={s.errorBox}><View style={{flex:1}}><Text style={s.errorTitle}>Não foi possível atualizar</Text><Text style={s.errorText}>{message}</Text></View>{onRetry?<Pressable onPress={onRetry} style={s.retry}><Text style={s.retryText}>Tentar novamente</Text></Pressable>:null}</View>;}
function Skeleton(){return <View>{[1,2,3].map(i=><View key={i} style={s.skeleton}><View style={[s.skeletonLine,{width:'26%'}]}/><View style={[s.skeletonLine,{width:'82%',height:16}]}/><View style={[s.skeletonLine,{width:'58%'}]}/></View>)}</View>;}

const s=StyleSheet.create({
  safe:{flex:1,backgroundColor:C.bg},pageScroll:{flex:1,backgroundColor:C.bg},pageContent:{flexGrow:1,alignItems:'center',paddingBottom:48},shell:{width:'100%',maxWidth:1180,minHeight:'100%',borderLeftWidth:1,borderRightWidth:1,borderColor:'#14263A',backgroundColor:C.bg},shellCompact:{borderLeftWidth:0,borderRightWidth:0},
  brand:{fontFamily:FONT,fontSize:24,fontWeight:'800',letterSpacing:-.9,color:C.text},brandSignal:{color:'#7FA2FF'},header:{minHeight:82,paddingHorizontal:22,paddingVertical:16,flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:18,borderBottomWidth:1,borderBottomColor:'#182A3E'},headerSubtitle:{fontFamily:FONT,color:C.muted2,fontSize:10,fontWeight:'600',marginTop:3},refreshButton:{minHeight:40,flexDirection:'row',alignItems:'center',gap:7,paddingHorizontal:12,borderRadius:10,borderWidth:1,borderColor:'#273D58',backgroundColor:'#0A1725'},refreshIcon:{fontFamily:FONT,fontSize:18,color:'#A7B7C9'},refreshText:{fontFamily:FONT,fontSize:10,fontWeight:'700',color:'#A7B7C9'},pressed:{opacity:.8},
  nav:{minHeight:52,flexDirection:'row',alignItems:'center',gap:4,paddingHorizontal:18,borderBottomWidth:1,borderBottomColor:'#182A3E'},navItem:{paddingHorizontal:15,paddingVertical:9,borderRadius:9},navItemOn:{backgroundColor:'#10213A'},navText:{fontFamily:FONT,color:C.muted2,fontWeight:'700',fontSize:11},navTextOn:{color:'#B8C8F8'},bodyWrap:{paddingHorizontal:22,paddingBottom:36},
  workspaceIntro:{paddingTop:30,paddingBottom:22,flexDirection:'row',justifyContent:'space-between',alignItems:'flex-end',gap:24},stack:{flexDirection:'column',alignItems:'stretch'},workspaceCopy:{flex:1},eyebrow:{fontFamily:FONT,color:C.blue,fontSize:9,fontWeight:'800',letterSpacing:1.5},workspaceTitle:{fontFamily:FONT,color:C.text,fontSize:36,lineHeight:42,fontWeight:'800',letterSpacing:-1.25,marginTop:10},workspaceTitleCompact:{fontSize:29,lineHeight:34},workspaceBody:{fontFamily:FONT,color:'#91A2B6',fontSize:13,lineHeight:20,marginTop:9,maxWidth:660},workspaceMeta:{alignItems:'flex-end',maxWidth:270},workspaceMetaCompact:{alignItems:'flex-start',marginTop:8},metaKicker:{fontFamily:FONT,color:'#60758E',fontSize:8,fontWeight:'800',letterSpacing:1.2},metaValue:{fontFamily:FONT,color:'#A7B6C8',fontSize:10,fontWeight:'600',marginTop:5},
  statsGrid:{display:'grid',gridTemplateColumns:'repeat(4, minmax(0, 1fr))',gap:10,paddingBottom:18},statsGridCompact:{gridTemplateColumns:'repeat(2, minmax(0, 1fr))'},stat:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:14,paddingHorizontal:15,paddingVertical:15},statValue:{fontFamily:FONT,fontSize:25,fontWeight:'800',color:C.text,letterSpacing:-.7},statLabel:{fontFamily:FONT,fontSize:9,color:C.muted2,marginTop:4,fontWeight:'600'},
  tools:{padding:10,borderRadius:14,backgroundColor:'#0A1725',borderWidth:1,borderColor:'#1F3249',flexDirection:'row',alignItems:'center',gap:10,marginBottom:10},search:{flex:1,minHeight:46,borderWidth:1,borderColor:'#263B56',borderRadius:10,flexDirection:'row',alignItems:'center',paddingHorizontal:11,backgroundColor:'#091522'},searchIcon:{fontFamily:FONT,color:C.blue,fontSize:18},input:{fontFamily:FONT,flex:1,color:C.text,paddingHorizontal:8,minHeight:44,fontSize:13},filters:{flexDirection:'row',flexWrap:'wrap',gap:6},filter:{borderWidth:1,borderColor:'#2A3F59',borderRadius:999,paddingHorizontal:11,paddingVertical:7},filterOn:{borderColor:C.blue,backgroundColor:C.blueSoft},filterText:{fontFamily:FONT,color:C.muted2,fontSize:10,fontWeight:'700'},filterTextOn:{color:'#C2CFFF'},notice:{fontFamily:FONT,color:C.muted,textAlign:'center',marginVertical:7,fontSize:10},
  listHead:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',paddingVertical:12},sectionTitle:{fontFamily:FONT,color:C.text,fontSize:14,fontWeight:'800'},listCount:{fontFamily:FONT,color:C.muted2,fontSize:9,fontWeight:'700'},empty:{fontFamily:FONT,color:C.muted,textAlign:'center',padding:40,lineHeight:20},card:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:18,marginBottom:10},cardPressed:{borderColor:'#3A5879',backgroundColor:C.panel2},cardTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center'},sourcePill:{alignSelf:'flex-start',paddingHorizontal:8,paddingVertical:5,borderRadius:999,borderWidth:1,borderColor:'#2A405A',backgroundColor:'#102033'},source:{fontFamily:FONT,color:'#8195AC',fontSize:8,fontWeight:'800',letterSpacing:.8},score:{fontFamily:FONT,fontWeight:'800',fontSize:13},cardTitle:{fontFamily:FONT,color:C.text,fontSize:18,lineHeight:24,fontWeight:'800',marginTop:13},buyer:{fontFamily:FONT,color:'#91A2B5',fontSize:11,marginTop:7},cardFacts:{flexDirection:'row',flexWrap:'wrap',gap:12,marginTop:10},meta:{fontFamily:FONT,color:'#72869E',fontSize:9,fontWeight:'600'},reasonBox:{marginTop:14,padding:12,borderRadius:10,backgroundColor:'#091522',borderWidth:1,borderColor:'#1D2F45'},reasonLabel:{fontFamily:FONT,color:'#60748C',fontSize:8,fontWeight:'800',letterSpacing:1},reason:{fontFamily:FONT,color:'#B1BDCB',fontSize:10,lineHeight:16,marginTop:5},open:{fontFamily:FONT,color:'#91ADFF',fontWeight:'800',fontSize:10,marginTop:13},
  loader:{minHeight:280,alignItems:'center',justifyContent:'center',gap:12},muted:{fontFamily:FONT,color:C.muted,fontSize:11,lineHeight:17},detailPage:{width:'100%',maxWidth:980,alignSelf:'center',paddingHorizontal:22,paddingTop:28,paddingBottom:60},back:{fontFamily:FONT,color:'#93A8C1',fontSize:11,fontWeight:'700',marginBottom:24},detailTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:12},deadline:{fontFamily:FONT,color:C.amber,fontSize:10,fontWeight:'700'},detailTitle:{fontFamily:FONT,color:C.text,fontSize:34,lineHeight:40,fontWeight:'800',letterSpacing:-1,marginTop:16},detailTitleCompact:{fontSize:28,lineHeight:34},detailScore:{fontFamily:FONT,color:C.green,fontSize:30,fontWeight:'800',marginTop:16},scoreOutOf:{color:'#60758E',fontSize:14},factGrid:{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:18},fact:{flexGrow:1,flexBasis:190,minWidth:145,backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:12,padding:13},factLabel:{fontFamily:FONT,color:'#61768F',fontSize:8,fontWeight:'800',letterSpacing:1},factValue:{fontFamily:FONT,color:C.text,fontSize:11,fontWeight:'600',marginTop:5},workflow:{backgroundColor:C.panel,borderWidth:1,borderColor:'#263B55',borderRadius:16,padding:16,marginTop:20},stateRow:{flexDirection:'row',flexWrap:'wrap',gap:7,marginTop:12},state:{borderWidth:1,borderColor:'#2C405A',borderRadius:999,paddingHorizontal:11,paddingVertical:8},stateOn:{borderColor:C.blue,backgroundColor:C.blueSoft},stateText:{fontFamily:FONT,color:'#899BAF',fontSize:10,fontWeight:'700'},stateTextOn:{color:'#C4D0FF'},field:{fontFamily:FONT,backgroundColor:'#091522',borderWidth:1,borderColor:'#2A3E58',borderRadius:10,color:C.text,paddingHorizontal:13,paddingVertical:12},note:{minHeight:84,marginTop:12,textAlignVertical:'top'},secondaryButton:{borderWidth:1,borderColor:'#4E72DD',borderRadius:10,padding:11,alignItems:'center',marginTop:9},secondaryButtonText:{fontFamily:FONT,color:'#9BB1FF',fontWeight:'800',fontSize:11},heading:{fontFamily:FONT,color:C.text,fontSize:16,fontWeight:'800',marginTop:24},body:{fontFamily:FONT,color:'#9CAABD',fontSize:12,lineHeight:20,marginTop:8},trust:{fontFamily:FONT,color:'#64788F',fontSize:9,lineHeight:15,marginTop:15},primaryButton:{backgroundColor:C.text,borderRadius:10,padding:13,alignItems:'center',marginTop:20},primaryButtonText:{fontFamily:FONT,color:C.bg,fontWeight:'800',fontSize:11},
  profileWrap:{paddingHorizontal:22,paddingTop:28,paddingBottom:48,maxWidth:900,width:'100%',alignSelf:'center'},profileTitle:{fontFamily:FONT,color:C.text,fontSize:31,lineHeight:37,fontWeight:'800',letterSpacing:-.8,marginTop:9},formCard:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:18,marginTop:20},label:{fontFamily:FONT,color:'#C5CED9',fontWeight:'800',fontSize:10,letterSpacing:.4,marginTop:17,marginBottom:7},valueRow:{flexDirection:'row',gap:10},valueField:{flex:1},settingsCard:{backgroundColor:'#0B1725',borderWidth:1,borderColor:C.line,borderRadius:16,padding:6,marginTop:14},setting:{padding:13,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:14,borderBottomWidth:1,borderBottomColor:'#182A3E'},settingCopy:{flex:1},settingTitle:{fontFamily:FONT,color:C.text,fontWeight:'800',fontSize:12},signOut:{alignItems:'center',padding:16,marginTop:14},signOutText:{fontFamily:FONT,color:C.red,fontWeight:'700',fontSize:11},
  errorBox:{marginVertical:8,backgroundColor:'#1A1118',borderWidth:1,borderColor:'#6B3443',borderRadius:12,padding:13,flexDirection:'row',alignItems:'center',gap:12},errorTitle:{fontFamily:FONT,color:'#FFC1CA',fontSize:10,fontWeight:'800'},errorText:{fontFamily:FONT,color:'#D9A6AE',fontSize:10,lineHeight:16,marginTop:3},retry:{paddingHorizontal:12,paddingVertical:8,borderRadius:8,backgroundColor:'#251B2D'},retryText:{fontFamily:FONT,color:'#D2B6FF',fontWeight:'700',fontSize:10},skeleton:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:18,marginBottom:10,gap:12},skeletonLine:{height:10,borderRadius:6,backgroundColor:'#1C2D41'},
});
