import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Switch, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import AuthGate from './components/AuthGate';
import BrandLogo from './components/BrandLogo';
import OpportunityExplanation from './components/OpportunityExplanation';
import ProfileOnboarding from './components/ProfileOnboarding';
import { api } from './src/api';
import { EUROPE_MARKETS } from './src/markets';
import { DEFAULT_SETTINGS, storage } from './src/storage';
import { THEMES, resolveTheme, createThemeColors } from './src/theme-system.mjs';
import { syncUnreadOpportunityAlerts } from './src/notifications';

const FONT = 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const PAGE_SIZE = 80;
const ThemeContext = React.createContext(null);
const STATES = [['NEW','Novo'],['REVIEWING','Em análise'],['PREPARING','A preparar'],['SUBMITTED','Proposta enviada'],['WON','Ganho'],['LOST','Perdido']];

export default function App(){ return <AuthGate><WebMain/></AuthGate>; }
function Brand(){const {inverseBrand}=React.useContext(ThemeContext);return <BrandLogo markSize={38} textSize={24} inverse={inverseBrand}/>; }

function useDocumentScroll(){
  useEffect(()=>{
    if(typeof document==='undefined') return undefined;
    const nodes=[document.documentElement,document.body,document.getElementById('root')].filter(Boolean);
    const before=nodes.map(node=>({node,height:node.style.height,minHeight:node.style.minHeight,overflowY:node.style.overflowY,overflowX:node.style.overflowX}));
    nodes.forEach(node=>{node.style.height='auto';node.style.minHeight='100%';node.style.overflowY='auto';node.style.overflowX='hidden';});
    return()=>before.forEach(({node,height,minHeight,overflowY,overflowX})=>{node.style.height=height;node.style.minHeight=minHeight;node.style.overflowY=overflowY;node.style.overflowX=overflowX;});
  },[]);
}

function WebMain(){
  useDocumentScroll();
  const { width } = useWindowDimensions();
  const compact = width < 760;
  const [tab,setTab] = useState('radar');
  const [items,setItems] = useState([]);
  const [stats,setStats] = useState({});
  const [page,setPage] = useState({limit:PAGE_SIZE,offset:0,has_more:false,next_offset:null});
  const [settings,setSettings] = useState(DEFAULT_SETTINGS);
  const themed = useMemo(() => { const C=createThemeColors(settings.theme); return {C,s:buildStyles(C),inverseBrand:resolveTheme(settings.theme).mode==='dark'}; },[settings.theme]);
  const {C,s}=themed;
  const [profile,setProfile] = useState(undefined);
  const [selected,setSelected] = useState(null);
  const [loading,setLoading] = useState(true);
  const [loadingMore,setLoadingMore] = useState(false);
  const [profileLoading,setProfileLoading] = useState(true);
  const [saving,setSaving] = useState(false);
  const [radarError,setRadarError] = useState('');
  const [profileError,setProfileError] = useState('');
  const [search,setSearch] = useState('');
  const [appliedSearch,setAppliedSearch] = useState('');
  const [notice,setNotice] = useState('');
  const requestId = useRef(0);
  const mounted = useRef(true);

  const load = useCallback(async ({criteria=settings,query=appliedSearch}={}) => {
    const id=++requestId.current;
    setRadarError('');setProfileError('');setLoading(true);setProfileLoading(true);
    try{
      const [profileResult,opResult,statsResult]=await Promise.allSettled([
        api.profile(),
        api.opportunities({q:query,minscore:criteria.minScore,openOnly:criteria.openOnly,limit:PAGE_SIZE,offset:0}),
        api.stats(),
      ]);
      if(!mounted.current||id!==requestId.current)return;
      if(profileResult.status==='fulfilled'){
        setProfile(profileResult.value);
        if(profileResult.value)storage.setProfile(profileResult.value).catch(()=>{});
      }else setProfileError(profileResult.reason?.message||'Unable to update o perfil.');
      if(opResult.status==='fulfilled'){
        const nextItems=opResult.value?.items||[];
        const nextStats=statsResult.status==='fulfilled'?(statsResult.value||{}):stats;
        setItems(nextItems);setPage(opResult.value?.page||{limit:PAGE_SIZE,offset:0,has_more:false,next_offset:null});
        if(statsResult.status==='fulfilled')setStats(nextStats);
        storage.setCache({items:nextItems,stats:nextStats}).catch(()=>{});
      }else{
        if(statsResult.status==='fulfilled')setStats(statsResult.value||{});
        setRadarError(opResult.reason?.message||'Unable to update o Radar.');
      }
    }finally{
      if(mounted.current&&id===requestId.current){setLoading(false);setProfileLoading(false);}
    }
  },[appliedSearch,settings,stats]);

  const loadMore = useCallback(async()=>{
    if(loading||loadingMore||!page?.has_more||page?.next_offset==null)return;
    setLoadingMore(true);setRadarError('');
    try{
      const result=await api.opportunities({q:appliedSearch,minscore:settings.minScore,openOnly:settings.openOnly,limit:PAGE_SIZE,offset:page.next_offset});
      if(!mounted.current)return;
      setItems(current=>{
        const merged=new Map(current.map(item=>[String(item.id),item]));
        (result?.items||[]).forEach(item=>merged.set(String(item.id),item));
        const next=[...merged.values()];
        storage.setCache({items:next,stats}).catch(()=>{});
        return next;
      });
      setPage(result?.page||{limit:PAGE_SIZE,offset:page.next_offset,has_more:false,next_offset:null});
    }catch(e){setRadarError(e?.message||'Unable to load more opportunities.');}
    finally{if(mounted.current)setLoadingMore(false);}
  },[appliedSearch,loading,loadingMore,page,settings,stats]);

  useEffect(()=>{
    mounted.current=true;let active=true;
    (async()=>{
      let savedSettings=DEFAULT_SETTINGS;
      const hydrated=await Promise.allSettled([storage.getSettings(),storage.getCache(),storage.getProfile()]);
      if(!active)return;
      if(hydrated[0].status==='fulfilled'){savedSettings=hydrated[0].value;setSettings(savedSettings);}
      if(hydrated[1].status==='fulfilled'&&hydrated[1].value){setItems(hydrated[1].value.items||[]);setStats(hydrated[1].value.stats||{});setLoading(false);}
      if(hydrated[2].status==='fulfilled'&&hydrated[2].value)setProfile(hydrated[2].value);
      await load({criteria:savedSettings,query:''});
    })();
    return()=>{active=false;mounted.current=false;};
  },[]);

  useEffect(()=>{storage.setSettings(settings).catch(()=>{});},[settings]);
  useEffect(()=>{
    if(!settings.notifications){setNotice('');return;}
    let active=true;(async()=>{try{const delivered=await syncUnreadOpportunityAlerts();if(active)setNotice(delivered>0?`${delivered} new alert(s).`:'Notifications ativadas.');}catch(_){if(active)setNotice('Web notifications enabled; push requires the native app.');}})();
    return()=>{active=false;};
  },[settings.notifications]);

  const applyCriteria=patch=>{const criteria={...settings,...patch};setSettings(criteria);load({criteria,query:appliedSearch});};
  const submitSearch=()=>{const query=search.trim();setAppliedSearch(query);load({query});};
  const clearSearch=()=>{setSearch('');setAppliedSearch('');load({query:''});};
  const saveProfile=async patch=>{
    setSaving(true);setProfileError('');
    try{const next=await api.saveProfile({...profile,...patch});setProfile(next);await storage.setProfile(next);setTab('radar');await load({criteria:settings,query:appliedSearch});}
    catch(e){setProfileError(e?.responseBody?.message||e?.responseBody?.error||e?.message||'Unable to save company profile.');}
    finally{setSaving(false);}
  };

  if(!profileLoading&&profile!==undefined&&(!profile?.name?.trim()||!profile?.activity?.trim()))return <ThemeContext.Provider value={themed}><View style={s.documentPage}><ProfileOnboarding initialProfile={profile||{}} onComplete={next=>{setProfile(next);load({criteria:settings,query:appliedSearch});}}/></View></ThemeContext.Provider>;
  if(selected)return <ThemeContext.Provider value={themed}><OpportunityDetail item={selected} compact={compact} onBack={()=>setSelected(null)} onChanged={next=>{setSelected(next);setItems(old=>old.map(item=>item.id===next.id?next:item));}}/></ThemeContext.Provider>;

  return <ThemeContext.Provider value={themed}><View style={s.documentPage}>
    <StatusBar style="auto"/>
    <View style={s.pageContent}><View style={[s.shell,compact&&s.shellCompact]}>
      <Header onRefresh={()=>load({criteria:settings,query:appliedSearch})}/><Nav tab={tab} setTab={setTab}/>
      {tab==='settings'
        ? <ThemeSettings settings={settings} setSettings={setSettings} onOpenOnlyChange={value=>applyCriteria({openOnly:value})} notice={notice}/>
        : tab==='profile'
        ? <ProfilePanel profile={profile} profileLoading={profileLoading} error={profileError} settings={settings} setSettings={setSettings} onOpenOnlyChange={value=>applyCriteria({openOnly:value})} onSave={saveProfile} saving={saving} notice={notice} onRetry={()=>load({criteria:settings,query:appliedSearch})}/>
        : <RadarPanel compact={compact} items={items} stats={stats} settings={settings} search={search} setSearch={setSearch} appliedSearch={appliedSearch} loading={loading} loadingMore={loadingMore} page={page} error={radarError} notice={notice} onRefresh={()=>load({criteria:settings,query:appliedSearch})} onSearch={submitSearch} onClearSearch={clearSearch} onMinScore={value=>applyCriteria({minScore:value})} onLoadMore={loadMore} onOpen={setSelected}/>} 
    </View></View>
  </View></ThemeContext.Provider>;
}

function Header({onRefresh}){const {C,s}=React.useContext(ThemeContext);return <View style={s.header}><View><Brand/><Text style={s.headerSubtitle}>Public procurement intelligence</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Refresh radar" onPress={onRefresh} style={({pressed})=>[s.refreshButton,pressed&&s.pressed]}><Text style={s.refreshIcon}>↻</Text><Text style={s.refreshText}>Refresh</Text></Pressable></View>;}
function Nav({tab,setTab}){const {C,s}=React.useContext(ThemeContext);return <View style={s.nav}>{['radar','profile','settings'].map(key=><Pressable accessibilityRole="button" key={key} onPress={()=>setTab(key)} style={[s.navItem,tab===key&&s.navItemOn]}><Text style={[s.navText,tab===key&&s.navTextOn]}>{key==='radar'?'Radar':key==='profile'?'Profile':'Settings'}</Text></Pressable>)}</View>;}

function RadarPanel({compact,items,stats,settings,search,setSearch,appliedSearch,loading,loadingMore,page,error,notice,onRefresh,onSearch,onClearSearch,onMinScore,onLoadMore,onOpen}){const {C,s}=React.useContext(ThemeContext);
  const visible=useMemo(()=>items,[items]);
  const statValues=[['Opportunities',stats.total],['Open',stats.open],['New in 24h',stats.new24],['High relevance',stats.high]];
  return <View style={s.bodyWrap}>
    <View style={[s.workspaceIntro,compact&&s.stack]}><View style={s.workspaceCopy}><Text style={s.eyebrow}>COMMERCIAL RADAR</Text><Text style={[s.workspaceTitle,compact&&s.workspaceTitleCompact]}>Opportunities worth your attention.</Text><Text style={s.workspaceBody}>Prioritised for your company, with explainable matches and original source links.</Text></View><View style={[s.workspaceMeta,compact&&s.workspaceMetaCompact]}><Text style={s.metaKicker}>LAST UPDATE</Text><Text style={s.metaValue}>{stats.last_sync?new Date(stats.last_sync).toLocaleString('en-GB'):'Syncing'}</Text></View></View>
    <View style={[s.statsGrid,compact&&s.statsGridCompact]}>{statValues.map(([label,value])=><View style={s.stat} key={label}><Text style={s.statValue}>{value??0}</Text><Text style={s.statLabel}>{label}</Text></View>)}</View>
    <View style={[s.tools,compact&&s.stack]}><View style={s.search}><Text style={s.searchIcon}>⌕</Text><TextInput value={search} onChangeText={setSearch} onSubmitEditing={onSearch} returnKeyType="search" placeholder="Search projects, authorities or CPV…" placeholderTextColor={C.muted2} style={s.input}/><Pressable accessibilityRole="button" onPress={onSearch} style={s.searchButton}><Text style={s.searchButtonText}>Search</Text></Pressable>{appliedSearch?<Pressable accessibilityRole="button" onPress={onClearSearch} style={s.clearButton}><Text style={s.clearButtonText}>Clear</Text></Pressable>:null}</View><View style={s.filters}>{[60,75,90].map(v=><Pressable key={v} onPress={()=>onMinScore(v)} style={[s.filter,settings.minScore===v&&s.filterOn]}><Text style={[s.filterText,settings.minScore===v&&s.filterTextOn]}>{v}+ relevance</Text></Pressable>)}</View></View>
    {notice?<Text style={s.notice}>{notice}</Text>:null}{error?<ErrorNotice message={error} onRetry={onRefresh}/>:null}
    <View style={s.listHead}><Text style={s.sectionTitle}>Radar</Text><Text style={s.listCount}>{visible.length}{page?.has_more?'+':''} results loaded</Text></View>
    {loading?<Skeleton/>:visible.length?<View style={s.opportunityGrid}>{visible.map(item=><OpportunityCard key={String(item.id)} item={item} onOpen={()=>onOpen(item)}/>)}</View>:<Text style={s.empty}>Sem resultados com estes filtros. Reduz a relevance mínima ou ajusta os critérios da empresa.</Text>}
    {!loading&&page?.has_more?<Pressable disabled={loadingMore} accessibilityRole="button" onPress={onLoadMore} style={[s.loadMore,loadingMore&&s.disabled]}>{loadingMore?<ActivityIndicator color={C.text}/>:<Text style={s.loadMoreText}>Load more opportunities</Text>}</Pressable>:null}
    {!loading&&visible.length>0&&!page?.has_more?<Text style={s.endOfList}>End of results for the current criteria.</Text>:null}
  </View>;
}

function OpportunityCard({item,onOpen}){const {C,s}=React.useContext(ThemeContext);const score=item.decision_score??item.score??0;const deadline=item.deadline_status?.label||item.deadline||'Deadline not specified';return <Pressable accessibilityRole="button" onPress={onOpen} style={({pressed})=>[s.card,pressed&&s.cardPressed]}><View style={s.cardTop}><View style={s.sourcePill}><Text style={s.source}>{item.source||'TED'}</Text></View><Text style={[s.score,{color:score>=80?C.green:C.blue}]}>{score}/100</Text></View><Text style={s.cardTitle}>{item.title||'Untitled opportunity'}</Text><Text style={s.buyer}>{item.buyer||'Authority not identified'}</Text><View style={s.cardFacts}>{item.value?<Text style={s.meta}>Value · {item.value}</Text>:null}<Text style={s.meta}>Deadline · {deadline}</Text></View><View style={s.reasonBox}><Text style={s.reasonLabel}>WHY THIS MATCHED</Text><Text style={s.reason}>{item.decision_reason||item.match_reason||'Profile match'}</Text></View><Text style={s.open}>View opportunity →</Text></Pressable>;}

function OpportunityDetail({item,onBack,onChanged,compact}){const {C,s}=React.useContext(ThemeContext);
  useDocumentScroll();
  const [current,setCurrent]=useState(null);const [note,setNote]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [loading,setLoading]=useState(true);const [reload,setReload]=useState(0);
  useEffect(()=>{let active=true;setLoading(true);setError('');api.opportunity(item.id).then(fresh=>{if(!active)return;setCurrent(fresh);setNote(fresh?.workflow?.note||'');onChanged(fresh);}).catch(e=>{if(active)setError(e?.status===404?'This opportunity is no longer available.':(e?.message||'Unable to load this opportunity.'));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[item.id,reload]);
  const update=async(next=current?.workflow?.status||'NEW',nextNote=note)=>{if(!current||busy)return;setBusy(true);setError('');try{const result=await api.setWorkflow(current.id,next,nextNote);const workflow=result?.workflow||result;if(!workflow?.status)throw new Error('invalid_workflow_response');const value={...current,workflow};setCurrent(value);onChanged(value);}catch(_){setError('Unable to save workflow changes.');}finally{setBusy(false);}};
  return <View style={s.documentPage}><StatusBar style="light"/><View style={s.detailPage}><Pressable onPress={onBack}><Text style={s.back}>← Back to radar</Text></Pressable>
    {loading?<View style={s.loader}><ActivityIndicator color={C.blue}/><Text style={s.muted}>Loading opportunity details…</Text></View>:null}
    {!loading&&error&&!current?<ErrorNotice message={error} onRetry={()=>setReload(value=>value+1)}/>:null}
    {!loading&&current?<View><View style={[s.detailTop,compact&&s.stack]}><View style={s.sourcePill}><Text style={s.source}>{current.source||'TED'} · {current.external_id||'official reference'}</Text></View><Text style={s.deadline}>{current.deadline_status?.label||'Deadline not specified'}</Text></View><Text style={[s.detailTitle,compact&&s.detailTitleCompact]}>{current.title||'Untitled opportunity'}</Text><Text style={s.buyer}>{current.buyer||'Authority not identified'}</Text><Text style={s.detailScore}>{current.decision_score??current.score??0}<Text style={s.scoreOutOf}>/100</Text></Text><View style={s.factGrid}>{current.value?<Fact label="ESTIMATED VALUE" value={current.value}/>:null}<Fact label="DEADLINE" value={current.deadline||'not specified'}/><Fact label="PUBLISHED" value={current.publication_date||'not specified'}/>{current.cpv?<Fact label="CPV" value={current.cpv}/>:null}</View>
      <View style={s.workflow}><Text style={s.eyebrow}>COMMERCIAL WORKFLOW</Text><View style={s.stateRow}>{STATES.map(([key,label])=><Pressable key={key} disabled={busy} onPress={()=>update(key)} style={[s.state,current.workflow?.status===key&&s.stateOn]}><Text style={[s.stateText,current.workflow?.status===key&&s.stateTextOn]}>{label}</Text></Pressable>)}</View><TextInput value={note} onChangeText={setNote} multiline placeholder="Next step, contact or internal note…" placeholderTextColor={C.muted2} style={[s.field,s.note]}/><Pressable disabled={busy} onPress={()=>update(current.workflow?.status||'NEW',note)} style={s.secondaryButton}><Text style={s.secondaryButtonText}>{busy?'Saving…':'Save note'}</Text></Pressable>{error?<Text accessibilityRole="alert" style={s.errorText}>{error}</Text>:null}</View>
      <OpportunityExplanation item={current}/><Text style={s.heading}>Contract subject</Text><Text style={s.body}>{current.description||'Description unavailable. Check the official publication before deciding.'}</Text>{current.url?<Pressable style={s.primaryButton} onPress={()=>Linking.openURL(current.url)}><Text style={s.primaryButtonText}>Open official source and documents</Text></Pressable>:<Text style={s.sourceMissing}>No direct source link is available. Verify the reference and issuing authority before proceeding.</Text>}<Text style={s.trust}>Always verify deadlines and requirements with the official source. Relevance scoring supports, but does not replace, your judgement.</Text></View>:null}
  </View></View>;
}
function Fact({label,value}){const {C,s}=React.useContext(ThemeContext);return <View style={s.fact}><Text style={s.factLabel}>{label}</Text><Text style={s.factValue}>{value}</Text></View>;}

function ProfilePanel({profile,profileLoading,error,settings,setSettings,onOpenOnlyChange,onSave,saving,notice,onRetry}){const {C,s}=React.useContext(ThemeContext);if(profileLoading&&!profile)return <View style={s.loader}><ActivityIndicator color={C.blue}/><Text style={s.muted}>Loading company profile…</Text></View>;if(!profile)return error?<ErrorNotice message={error} onRetry={onRetry}/>:null;return <ProfileForm profile={profile} settings={settings} setSettings={setSettings} onOpenOnlyChange={onOpenOnlyChange} onSave={onSave} saving={saving} notice={notice} error={error}/>;}

function ProfileForm({profile,settings,setSettings,onOpenOnlyChange,onSave,saving,notice,error}){const {C,s}=React.useContext(ThemeContext);
  const [name,setName]=useState(profile.name||'');const [activity,setActivity]=useState(profile.activity||'');const [interests,setInterests]=useState((profile.contract_interests||profile.keywords||[]).join('\n'));const [cpv,setCpv]=useState((profile.cpv_prefixes||[]).join(', '));const [coverage,setCoverage]=useState(profile.coverage_mode||(profile.regions?.length?'regions':'portugal'));const [regions,setRegions]=useState((profile.regions||[]).join(', '));const [countries,setCountries]=useState(profile.countries||['PRT']);const [minValue,setMinValue]=useState(profile.min_value==null?'':String(profile.min_value));const [maxValue,setMaxValue]=useState(profile.max_value==null?'':String(profile.max_value));const [localError,setLocalError]=useState('');
  const list=v=>v.split(/[,\n]/).map(x=>x.trim()).filter(Boolean);const toggleCountry=code=>setCountries(x=>x.includes(code)?(code==='PRT'?x:x.filter(c=>c!==code)):[...x,code]);
  const amount=value=>{if(String(value).trim()==='')return null;const parsed=Number(String(value).replace(/\s/g,'').replace(',','.'));return Number.isFinite(parsed)?parsed:NaN;};
  const save=()=>{const min=amount(minValue),max=amount(maxValue),work=list(interests);if(!name.trim()||!activity.trim()){setLocalError('Enter a company name and primary activity.');return;}if(!work.length){setLocalError('Add at least one target contract or service.');return;}if([min,max].some(value=>value!=null&&!Number.isFinite(value))||(min!=null&&max!=null&&min>max)){setLocalError('Review the contract value range.');return;}setLocalError('');onSave({name:name.trim(),activity:activity.trim(),contract_interests:work,coverage_mode:coverage,countries:coverage==='europe'?countries:['PRT'],regions:coverage==='regions'?list(regions):[],cpv_prefixes:list(cpv),min_value:min,max_value:max});};
  return <View style={s.profileWrap}><Text style={s.eyebrow}>COMPANY PROFILE</Text><Text style={s.profileTitle}>Your profile shapes the radar.</Text><Text style={s.workspaceBody}>Describe your business in natural language to prioritise relevant opportunities.</Text><View style={s.formCard}><Label text="Empresa"/><TextInput value={name} onChangeText={setName} placeholder="Company name" placeholderTextColor={C.muted2} style={s.field}/><Label text="Primary activity"/><TextInput value={activity} onChangeText={setActivity} placeholder="e.g. electrical installations" placeholderTextColor={C.muted2} style={s.field}/><Label text="Target contracts and services"/><TextInput value={interests} onChangeText={setInterests} multiline placeholder={'e.g. school maintenance\nSolar panel installation'} placeholderTextColor={C.muted2} style={[s.field,s.note]}/><Label text="Where can your company deliver?"/><View style={s.filters}>{[['portugal','Portugal (supported market)'],['regions','Specific regions'],['europe','Additional markets']].map(([key,label])=><Pressable key={key} onPress={()=>setCoverage(key)} style={[s.filter,coverage===key&&s.filterOn]}><Text style={[s.filterText,coverage===key&&s.filterTextOn]}>{label}</Text></Pressable>)}</View>{coverage==='regions'?<TextInput value={regions} onChangeText={setRegions} placeholder="Districts, regions or cities" placeholderTextColor={C.muted2} style={s.field}/>:null}{coverage==='europe'?<><Text style={s.marketHelp}>Available coverage: 32 European markets through TED/eForms and selected national connectors. Other regions require verified sources.</Text><View style={s.filters}>{EUROPE_MARKETS.map(([code,label])=><Pressable key={code} onPress={()=>toggleCountry(code)} style={[s.filter,countries.includes(code)&&s.filterOn]}><Text style={[s.filterText,countries.includes(code)&&s.filterTextOn]}>{label}</Text></Pressable>)}</View></>:null}<Label text="Typical contract value (€)"/><View style={s.valueRow}><TextInput value={minValue} onChangeText={setMinValue} keyboardType="numeric" placeholder="From €" placeholderTextColor={C.muted2} style={[s.field,s.valueField]}/><TextInput value={maxValue} onChangeText={setMaxValue} keyboardType="numeric" placeholder="Up to €" placeholderTextColor={C.muted2} style={[s.field,s.valueField]}/></View><Label text="Advanced · CPV categories"/><TextInput value={cpv} onChangeText={setCpv} placeholder="45, 4531" placeholderTextColor={C.muted2} style={s.field}/>{localError?<Text accessibilityRole="alert" style={s.errorText}>{localError}</Text>:null}{error?<Text accessibilityRole="alert" style={s.errorText}>{error}</Text>:null}<Pressable onPress={save} disabled={saving} style={[s.primaryButton,saving&&s.disabled]}><Text style={s.primaryButtonText}>{saving?'Saving…':'Save and refresh radar'}</Text></Pressable></View><View style={s.settingsCard}><Setting title="Open opportunities only" copy="Hide closed procedures." value={!!settings.openOnly} onValueChange={onOpenOnlyChange}/><Setting title="Notifications" copy={notice||'Alerts for relevant new opportunities.'} value={!!settings.notifications} onValueChange={value=>setSettings(x=>({...x,notifications:value}))}/></View></View>;
}
function ThemeSettings({settings,setSettings,onOpenOnlyChange,notice}) {
  const {s,C}=React.useContext(ThemeContext);
  const selected=resolveTheme(settings.theme).id;
  return <View style={s.profileWrap}>
    <Text style={s.eyebrow}>PERSONALISATION</Text><Text style={s.profileTitle}>Settings</Text>
    <Text style={s.workspaceBody}>Choose your workspace appearance. The underlying data, access controls and scoring remain unchanged.</Text>
    <Text style={s.heading}>Colour themes</Text>
    <View style={s.themeGrid}>{THEMES.map(theme=><Pressable key={theme.id} accessibilityRole="radio" accessibilityState={{checked:selected===theme.id}} accessibilityLabel={'Theme '+theme.name} onPress={()=>setSettings(previous=>({...previous,theme:theme.id}))} style={[s.themeCard,selected===theme.id&&s.themeSelected]}>
      <View style={s.themePalette}>{theme.swatches.map((color,index)=><View key={index} style={[s.themeSwatch,{backgroundColor:color}]}/>)}</View>
      <Text style={s.themeName}>{theme.name}{selected===theme.id?' ✓':''}</Text>
      <Text style={s.themeMeta}>{theme.description||'Immediate preview · five coordinated tones'}</Text>
    </Pressable>)}</View>
    <Text style={s.themeHint}>Themes change the interface, never the official brand or radar outcomes.</Text>
    <View style={s.settingsCard}><Setting title="Open opportunities only" copy="Hide closed procedures." value={!!settings.openOnly} onValueChange={onOpenOnlyChange}/><Setting title="Notifications" copy={notice||'Alerts for relevant new opportunities.'} value={!!settings.notifications} onValueChange={value=>setSettings(old=>({...old,notifications:value}))}/></View>
  </View>;
}
function Label({text}){const {C,s}=React.useContext(ThemeContext);return <Text style={s.label}>{text}</Text>;}
function Setting({title,copy,value,onValueChange}){const {C,s}=React.useContext(ThemeContext);return <View style={s.setting}><View style={s.settingCopy}><Text style={s.settingTitle}>{title}</Text><Text style={s.muted}>{copy}</Text></View><Switch value={value} onValueChange={onValueChange}/></View>;}
function ErrorNotice({message,onRetry}){const {C,s}=React.useContext(ThemeContext);return <View style={s.errorBox}><View style={{flex:1}}><Text style={s.errorTitle}>Unable to update</Text><Text style={s.errorText}>{message}</Text></View>{onRetry?<Pressable onPress={onRetry} style={s.retry}><Text style={s.retryText}>Try again</Text></Pressable>:null}</View>;}
function Skeleton(){const {C,s}=React.useContext(ThemeContext);return <View>{[1,2,3].map(i=><View key={i} style={s.skeleton}><View style={[s.skeletonLine,{width:'26%'}]}/><View style={[s.skeletonLine,{width:'82%',height:16}]}/><View style={[s.skeletonLine,{width:'58%'}]}/></View>)}</View>;}

function buildStyles(C){return StyleSheet.create({
  documentPage:{width:'100%',minHeight:'100vh',backgroundColor:C.bg},pageContent:{width:'100%',alignItems:'center',paddingBottom:48},shell:{width:'100%',maxWidth:1800,minHeight:'100vh',borderLeftWidth:1,borderRightWidth:1,borderColor:C.line,backgroundColor:C.bg},shellCompact:{borderLeftWidth:0,borderRightWidth:0},
  brand:{fontFamily:FONT,fontSize:24,fontWeight:'800',letterSpacing:-.9,color:C.text},brandSignal:{color:C.muted},header:{minHeight:82,paddingHorizontal:22,paddingVertical:16,flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:18,borderBottomWidth:1,borderBottomColor:C.line},headerSubtitle:{fontFamily:FONT,color:C.muted2,fontSize:10,fontWeight:'600',marginTop:3},refreshButton:{minHeight:40,flexDirection:'row',alignItems:'center',gap:7,paddingHorizontal:12,borderRadius:10,borderWidth:1,borderColor:C.line,backgroundColor:C.subtle},refreshIcon:{fontFamily:FONT,fontSize:18,color:C.muted},refreshText:{fontFamily:FONT,fontSize:10,fontWeight:'700',color:C.muted},pressed:{opacity:.8},
  nav:{minHeight:52,flexDirection:'row',alignItems:'center',gap:4,paddingHorizontal:18,borderBottomWidth:1,borderBottomColor:C.line},navItem:{paddingHorizontal:15,paddingVertical:9,borderRadius:9},navItemOn:{backgroundColor:C.navActive},navText:{fontFamily:FONT,color:C.muted2,fontWeight:'700',fontSize:11},navTextOn:{color:C.blueText},bodyWrap:{paddingHorizontal:22,paddingBottom:36},
  workspaceIntro:{paddingTop:30,paddingBottom:22,flexDirection:'row',justifyContent:'space-between',alignItems:'flex-end',gap:24},stack:{flexDirection:'column',alignItems:'stretch'},workspaceCopy:{flex:1},eyebrow:{fontFamily:FONT,color:C.blue,fontSize:9,fontWeight:'800',letterSpacing:1.5},workspaceTitle:{fontFamily:FONT,color:C.text,fontSize:36,lineHeight:42,fontWeight:'800',letterSpacing:-1.25,marginTop:10},workspaceTitleCompact:{fontSize:29,lineHeight:34},workspaceBody:{fontFamily:FONT,color:C.muted,fontSize:13,lineHeight:20,marginTop:9,maxWidth:660},workspaceMeta:{alignItems:'flex-end',maxWidth:270},workspaceMetaCompact:{alignItems:'flex-start',marginTop:8},metaKicker:{fontFamily:FONT,color:C.muted2,fontSize:8,fontWeight:'800',letterSpacing:1.2},metaValue:{fontFamily:FONT,color:C.muted,fontSize:10,fontWeight:'600',marginTop:5},
  opportunityGrid:{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(320px,1fr))',gap:14,marginTop:8},statsGrid:{display:'grid',gridTemplateColumns:'repeat(4, minmax(0, 1fr))',gap:10,paddingBottom:18},statsGridCompact:{gridTemplateColumns:'repeat(2, minmax(0, 1fr))'},stat:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:14,paddingHorizontal:15,paddingVertical:15},statValue:{fontFamily:FONT,fontSize:25,fontWeight:'800',color:C.text,letterSpacing:-.7},statLabel:{fontFamily:FONT,fontSize:9,color:C.muted2,marginTop:4,fontWeight:'600'},
  tools:{padding:10,borderRadius:14,backgroundColor:C.subtle,borderWidth:1,borderColor:C.line,flexDirection:'row',alignItems:'center',gap:10,marginBottom:10},search:{flex:1,minHeight:46,borderWidth:1,borderColor:C.line,borderRadius:10,flexDirection:'row',flexWrap:'wrap',alignItems:'center',paddingHorizontal:11,backgroundColor:C.input},searchIcon:{fontFamily:FONT,color:C.blue,fontSize:18},input:{fontFamily:FONT,flex:1,minWidth:180,color:C.text,paddingHorizontal:8,minHeight:44,fontSize:13},searchButton:{paddingHorizontal:10,paddingVertical:7,borderRadius:8,backgroundColor:C.action},searchButtonText:{fontFamily:FONT,color:C.onAction,fontSize:9,fontWeight:'800'},clearButton:{paddingHorizontal:9,paddingVertical:7},clearButtonText:{fontFamily:FONT,color:C.muted,fontSize:9,fontWeight:'700'},filters:{flexDirection:'row',flexWrap:'wrap',gap:6},filter:{borderWidth:1,borderColor:C.line,borderRadius:999,paddingHorizontal:11,paddingVertical:7},filterOn:{borderColor:C.blue,backgroundColor:C.blueSoft},filterText:{fontFamily:FONT,color:C.muted2,fontSize:10,fontWeight:'700'},filterTextOn:{color:C.blueText},notice:{fontFamily:FONT,color:C.muted,textAlign:'center',marginVertical:7,fontSize:10},
  listHead:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',paddingVertical:12,gap:12},sectionTitle:{fontFamily:FONT,color:C.text,fontSize:14,fontWeight:'800'},listCount:{fontFamily:FONT,color:C.muted2,fontSize:9,fontWeight:'700'},empty:{fontFamily:FONT,color:C.muted,textAlign:'center',padding:40,lineHeight:20},card:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:18,marginBottom:0},cardPressed:{borderColor:C.borderStrong,backgroundColor:C.panel2},cardTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center'},sourcePill:{alignSelf:'flex-start',paddingHorizontal:8,paddingVertical:5,borderRadius:999,borderWidth:1,borderColor:C.line,backgroundColor:C.subtle},source:{fontFamily:FONT,color:C.muted,fontSize:8,fontWeight:'800',letterSpacing:.8},score:{fontFamily:FONT,fontWeight:'800',fontSize:13},cardTitle:{fontFamily:FONT,color:C.text,fontSize:18,lineHeight:24,fontWeight:'800',marginTop:13},buyer:{fontFamily:FONT,color:C.muted,fontSize:11,marginTop:7},cardFacts:{flexDirection:'row',flexWrap:'wrap',gap:12,marginTop:10},meta:{fontFamily:FONT,color:C.muted2,fontSize:9,fontWeight:'600'},reasonBox:{marginTop:14,padding:12,borderRadius:10,backgroundColor:C.input,borderWidth:1,borderColor:C.line},reasonLabel:{fontFamily:FONT,color:C.muted2,fontSize:8,fontWeight:'800',letterSpacing:1},reason:{fontFamily:FONT,color:C.muted,fontSize:10,lineHeight:16,marginTop:5},open:{fontFamily:FONT,color:C.blue,fontWeight:'800',fontSize:10,marginTop:13},loadMore:{minHeight:46,borderRadius:11,borderWidth:1,borderColor:C.borderStrong,backgroundColor:C.subtle,alignItems:'center',justifyContent:'center',marginTop:6},loadMoreText:{fontFamily:FONT,color:C.blueText,fontWeight:'800',fontSize:11},endOfList:{fontFamily:FONT,color:C.muted2,textAlign:'center',fontSize:9,marginTop:16},disabled:{opacity:.55},
  loader:{minHeight:280,alignItems:'center',justifyContent:'center',gap:12},muted:{fontFamily:FONT,color:C.muted,fontSize:11,lineHeight:17},detailPage:{width:'100%',maxWidth:1400,alignSelf:'center',paddingHorizontal:22,paddingTop:28,paddingBottom:60},back:{fontFamily:FONT,color:C.muted,fontSize:11,fontWeight:'700',marginBottom:24},detailTop:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',gap:12},deadline:{fontFamily:FONT,color:C.amber,fontSize:10,fontWeight:'700'},detailTitle:{fontFamily:FONT,color:C.text,fontSize:34,lineHeight:40,fontWeight:'800',letterSpacing:-1,marginTop:16},detailTitleCompact:{fontSize:28,lineHeight:34},detailScore:{fontFamily:FONT,color:C.green,fontSize:30,fontWeight:'800',marginTop:16},scoreOutOf:{color:C.muted2,fontSize:14},factGrid:{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:18},fact:{flexGrow:1,flexBasis:190,minWidth:145,backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:12,padding:13},factLabel:{fontFamily:FONT,color:C.muted2,fontSize:8,fontWeight:'800',letterSpacing:1},factValue:{fontFamily:FONT,color:C.text,fontSize:11,fontWeight:'600',marginTop:5},workflow:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:16,marginTop:20},stateRow:{flexDirection:'row',flexWrap:'wrap',gap:7,marginTop:12},state:{borderWidth:1,borderColor:C.line,borderRadius:999,paddingHorizontal:11,paddingVertical:8},stateOn:{borderColor:C.blue,backgroundColor:C.blueSoft},stateText:{fontFamily:FONT,color:C.muted,fontSize:10,fontWeight:'700'},stateTextOn:{color:C.blueText},field:{fontFamily:FONT,backgroundColor:C.input,borderWidth:1,borderColor:C.line,borderRadius:10,color:C.text,paddingHorizontal:13,paddingVertical:12},note:{minHeight:84,marginTop:12,textAlignVertical:'top'},secondaryButton:{borderWidth:1,borderColor:C.blue,borderRadius:10,padding:11,alignItems:'center',marginTop:9},secondaryButtonText:{fontFamily:FONT,color:C.blue,fontWeight:'800',fontSize:11},heading:{fontFamily:FONT,color:C.text,fontSize:16,fontWeight:'800',marginTop:24},body:{fontFamily:FONT,color:C.muted,fontSize:12,lineHeight:20,marginTop:8},trust:{fontFamily:FONT,color:C.muted2,fontSize:9,lineHeight:15,marginTop:15},sourceMissing:{fontFamily:FONT,color:C.amber,fontSize:10,lineHeight:16,marginTop:16},primaryButton:{backgroundColor:C.action,borderRadius:10,padding:13,alignItems:'center',marginTop:20},primaryButtonText:{fontFamily:FONT,color:C.onAction,fontWeight:'800',fontSize:11},
  profileWrap:{paddingHorizontal:22,paddingTop:28,paddingBottom:48,maxWidth:1150,width:'100%',alignSelf:'center'},profileTitle:{fontFamily:FONT,color:C.text,fontSize:31,lineHeight:37,fontWeight:'800',letterSpacing:-.8,marginTop:9},formCard:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:18,marginTop:20},label:{fontFamily:FONT,color:C.text,fontWeight:'800',fontSize:10,letterSpacing:.4,marginTop:17,marginBottom:7},valueRow:{flexDirection:'row',gap:10,flexWrap:'wrap'},valueField:{flex:1,minWidth:180},marketHelp:{fontFamily:FONT,color:C.muted,fontSize:10,lineHeight:16,marginTop:10,marginBottom:8},settingsCard:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:6,marginTop:14},setting:{padding:13,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:14,borderBottomWidth:1,borderBottomColor:C.line},settingCopy:{flex:1},settingTitle:{fontFamily:FONT,color:C.text,fontWeight:'800',fontSize:12},
  themeGrid:{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(230px,1fr))',gap:14,marginTop:18},themeCard:{minHeight:140,borderWidth:1,borderRadius:14,borderColor:C.line,backgroundColor:C.panel,padding:14},themeSelected:{borderWidth:2,borderColor:C.blue},themePalette:{height:64,flexDirection:'row',borderRadius:9,overflow:'hidden',marginBottom:12},themeSwatch:{flex:1},themeName:{fontFamily:FONT,color:C.text,fontWeight:'800',fontSize:13},themeMeta:{fontFamily:FONT,color:C.muted,fontSize:10,lineHeight:16,marginTop:5},themeHint:{fontFamily:FONT,color:C.muted,fontSize:11,lineHeight:17,marginTop:18},
  errorBox:{marginVertical:8,backgroundColor:C.errorBg,borderWidth:1,borderColor:C.errorBorder,borderRadius:12,padding:13,flexDirection:'row',alignItems:'center',gap:12},errorTitle:{fontFamily:FONT,color:C.errorText,fontSize:10,fontWeight:'800'},errorText:{fontFamily:FONT,color:C.errorText,fontSize:10,lineHeight:16,marginTop:3},retry:{paddingHorizontal:12,paddingVertical:8,borderRadius:8,backgroundColor:C.errorBg},retryText:{fontFamily:FONT,color:C.errorText,fontWeight:'700',fontSize:10},skeleton:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:16,padding:18,marginBottom:10,gap:12},skeletonLine:{height:10,borderRadius:6,backgroundColor:C.subtle},
});}
