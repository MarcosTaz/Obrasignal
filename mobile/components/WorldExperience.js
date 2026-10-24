import React,{useMemo,useState} from 'react';
import {Pressable,ScrollView,StyleSheet,Text,View,useWindowDimensions} from 'react-native';
import Svg,{Defs,LinearGradient,RadialGradient,Stop,Rect,Path,Circle,Line} from 'react-native-svg';
import BrandLogo from './BrandLogo';
import {FONT_BODY,FONT_DISPLAY} from '../src/typography.mjs';
import {EUROPE_MARKETS} from '../src/markets';
import {createWorldPalette} from '../src/world-palette.mjs';
import {DEFAULT_THEME} from '../src/theme-system.mjs';

const WorldThemeContext=React.createContext(null);
const FALLBACK_PALETTE=createWorldPalette(DEFAULT_THEME);
const FALLBACK_WORLD_THEME={P:FALLBACK_PALETTE,s:makeStyles(FALLBACK_PALETTE)};
function useWorldTheme(){return React.useContext(WorldThemeContext)||FALLBACK_WORLD_THEME;}
export function WorldThemeProvider({theme,children}){
  const value=useMemo(()=>{
    const P=createWorldPalette(theme);
    return {P,s:makeStyles(P)};
  },[theme]);
  return <WorldThemeContext.Provider value={value}>{children}</WorldThemeContext.Provider>;
}
const T=(v)=>v===null||v===undefined?'—':String(v);
const Eyebrow=({children})=>{const {s}=useWorldTheme();return <Text style={s.eyebrow}>{children}</Text>;};
const Tile=({children,style})=>{const {s}=useWorldTheme();return <View style={[s.tile,style]}>{children}</View>;};
const Btn=({children,onPress,secondary=false})=>{const {s}=useWorldTheme();return <Pressable accessibilityRole="button" onPress={onPress} style={[s.btn,secondary&&s.btnSec]}><Text style={[s.btnText,secondary&&s.btnSecText]}>{children}</Text></Pressable>;};

export function Skyline(){
return <Svg viewBox="0 0 1440 540" preserveAspectRatio="xMidYMid slice" pointerEvents="none" style={StyleSheet.absoluteFillObject}>
<Defs>
<LinearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><Stop offset="0" stopColor="#020812"/><Stop offset=".5" stopColor="#102439"/><Stop offset="1" stopColor="#5B3932"/></LinearGradient>
<RadialGradient id="glow"><Stop offset="0" stopColor="#D98854" stopOpacity=".57"/><Stop offset="1" stopColor="#D98854" stopOpacity="0"/></RadialGradient>
<LinearGradient id="building" x1="0" y1="0" x2="1" y2="1"><Stop offset="0" stopColor="#26445C"/><Stop offset="1" stopColor="#030B15"/></LinearGradient>
</Defs>
<Rect width="1440" height="540" fill="url(#sky)"/>
<Circle cx="1090" cy="335" r="390" fill="url(#glow)"/>
{Array.from({length:35},(_,i)=>{const x=i*47-10,w=22+i%4*11,h=65+(i*47)%250;return <React.Fragment key={i}>
<Rect x={x} y={435-h} width={w} height={h+100} fill="url(#building)"/>
{Array.from({length:Math.floor(h/17)},(_,j)=><Line key={j} x1={x+5} x2={x+w-5} y1={443-h+j*17} y2={443-h+j*17} stroke={j%3?'#6288A0':'#DD945E'} strokeOpacity={j%3?.16:.49}/>)}
</React.Fragment>})}
<Path d="M0 442 Q290 408 680 472 T1440 453 V540 H0Z" fill="#06111D"/>
<Path d="M-15 502 Q350 392 738 507 T1480 482" stroke="#DF9163" strokeWidth="4" strokeOpacity=".65" fill="none"/>
<Path d="M-15 514 Q350 403 738 518 T1480 494" stroke="#71CBF3" strokeWidth="2" strokeOpacity=".53" fill="none"/>
<Path d="M1013 423 L1100 170 L1180 203 L1180 422 M1050 213 H1280 M1100 170 V101 M1180 203 L1370 203 M1100 170 L1180 420" stroke="#8FCBEE" strokeWidth="2.6" strokeOpacity=".73" fill="none"/>
<Path d="M1068 277 L1180 202 L1300 277 M1070 340 L1180 270 L1300 345" stroke="#75C4EB" strokeOpacity=".43" strokeWidth="2" fill="none"/>
<Path d="M820 435 L900 252 L947 270 L947 433 M900 252 V154 M785 154 H1115 M900 154 L988 215" stroke="#D6A076" strokeOpacity=".6" strokeWidth="2" fill="none"/>
<Circle cx="1180" cy="203" r="5" fill="#E8AA72"/><Circle cx="900" cy="252" r="5" fill="#E8AA72"/>
</Svg>;
}
const PanelEmpty=({preview=false})=>{const {s}=useWorldTheme();return <View style={s.noData}><Text style={s.emptyIcon}>◇</Text><Text style={s.emptyTitle}>No verified results loaded</Text><Text style={s.emptySub}>{preview?'This is an interface preview, not live customer data.':'Your account-scoped results will appear once the authenticated radar responds.'}</Text></View>;};
export function WorldAnalytics({items=[],stats={},preview=false,compact=false,onOpen}){
const {s,P}=useWorldTheme();
const result=preview?[]:items;
const scored=result.map(x=>Number(x.decision_score??x.score)).filter(Number.isFinite);
const histogram=[0,0,0,0,0,0].map((_,i)=>scored.filter(v=>Math.min(5,Math.max(0,Math.floor(v/20)))===i).length);
const max=Math.max(1,...histogram);
const sourceCounts=useMemo(()=>{const m=new Map();result.forEach(x=>{const k=x.source||'Unspecified';m.set(k,(m.get(k)||0)+1)});return [...m.entries()].sort((a,b)=>b[1]-a[1]).slice(0,5)},[result]);
return <View style={s.analytics}>
 <View style={s.statGrid}>{[['Identified opportunities',stats.total],['Open tenders',stats.open],['New in 24h',stats.new24],['High relevance',stats.high]].map(([name,value])=><Tile key={name} style={s.stat}>
  <Text style={s.statLabel}>{name}</Text><Text style={s.statNumber}>{preview?'—':T(value)}</Text><View style={s.statBar}/>
 </Tile>)}</View>
 <View style={[s.mainPanels,compact&&s.vertical]}>
  <Tile style={s.largePanel}><View style={s.panelHead}><Eyebrow>INTELLIGENCE RADAR</Eyebrow><Text style={s.panelTag}>SCHEMATIC</Text></View>
   <View style={s.radar}><Svg width="100%" height="245" viewBox="0 0 350 260">
    {Array.from({length:5},(_,i)=><Circle key={i} cx="175" cy="130" r={25+i*22} stroke={i===2?P.copper:'#4B86A6'} strokeOpacity={i===2?.7:.35} fill="none"/>)}
    <Line x1="50" y1="130" x2="300" y2="130" stroke="#548AAC" strokeOpacity=".38"/><Line x1="175" y1="5" x2="175" y2="254" stroke="#548AAC" strokeOpacity=".38"/>
    <Path d="M175 130 L264 50 A125 125 0 0 1 264 212 Z" fill="#C87D55" fillOpacity=".1"/>
    <Circle cx="175" cy="130" r="7" fill="#C87D55"/>
   </Svg></View><Text style={s.hint}>Conceptual radar · no live geolocation implied</Text>
  </Tile>
  <Tile style={s.largePanel}><View style={s.panelHead}><Eyebrow>RELEVANCE DISTRIBUTION</Eyebrow><Text style={s.panelTag}>LOADED RESULTS</Text></View>
   <Text style={s.largePanelTitle}>{scored.length?'Evidence-driven scoring':'Awaiting market signals'}</Text>
   <View style={s.chart}>{histogram.map((count,i)=><View key={i} style={s.barSlot}><View style={s.barTrack}><View style={[s.bar,{height:count?Math.max(6,count/max*154):3,backgroundColor:i>3?P.copper:P.blue,opacity:count?1:.24}]}/></View><Text style={s.barLabel}>{i*20}</Text></View>)}</View><Text style={s.hint}>{scored.length?String(scored.length)+' scored results loaded':'No illustrative numbers are substituted for live data.'}</Text>
  </Tile>
  <Tile style={s.largePanel}><View style={s.panelHead}><Eyebrow>PRIORITY QUEUE</Eyebrow><Text style={s.panelTag}>REAL RECORDS ONLY</Text></View>
   {result.length?result.slice(0,4).map(x=><Pressable accessibilityRole="button" onPress={()=>onOpen?.(x)} key={String(x.id)} style={s.queueRow}><View style={s.queueStripe}/><View style={{flex:1}}><Text numberOfLines={2} style={s.queueTitle}>{x.title||'Untitled tender'}</Text><Text style={s.queueSource}>{x.source||'Official source'}</Text></View><Text style={s.queueScore}>{T(x.decision_score??x.score)}</Text></Pressable>):<PanelEmpty preview={preview}/>}
  </Tile>
 </View>
 <View style={[s.lowerPanels,compact&&s.vertical]}>
  <Tile style={s.lower}><Eyebrow>SOURCE EVIDENCE</Eyebrow><Text style={s.lowerTitle}>Traceability</Text>{sourceCounts.length?sourceCounts.map(([source,count])=><View key={source} style={s.sourceRow}><Text numberOfLines={1} style={s.sourceText}>{source}</Text><Text style={s.mintText}>{count} loaded</Text></View>):<Text style={s.hint}>Verified sources will appear when data is available.</Text>}</Tile>
  <Tile style={s.lower}><Eyebrow>VERIFIED COVERAGE</Eyebrow><Text style={s.lowerTitle}>International vision.</Text><Text style={s.hint}>Available source markets are defined explicitly. Worldwide coverage is not implied.</Text><Text style={s.coverageValue}>{EUROPE_MARKETS.length} <Text style={s.coverageSub}>European market definitions</Text></Text></Tile>
  <Tile style={s.lower}><Eyebrow>DECISION INTEGRITY</Eyebrow><Text style={s.lowerTitle}>Evidence first.</Text><Text style={s.hint}>Always check the original authority notice before making a bid decision.</Text><Text style={s.flowLabel}>SOURCE → FIT → ACTION</Text></Tile>
 </View>
 </View>;
}
const nav=[['radar','◈','Overview'],['opportunities','▤','Opportunities'],['analytics','▥','Analytics'],['markets','◎','Markets'],['profile','▣','Company'],['settings','⚙','Settings']];
export function WorldSidebar({tab,onTab,compact}){
const {s,P}=useWorldTheme();
return <View style={[s.sidebar,compact&&s.sidebarCompact]}><View style={s.sidebarBrand}><BrandLogo inverse={P.isDark} markSize={35} textSize={21}/></View>
 {!compact?<Eyebrow>COMMAND CENTRE</Eyebrow>:null}<View style={[s.sideLinks,compact&&s.sideLinksCompact]}>{nav.map(([key,glyph,name])=><Pressable accessibilityRole="button" accessibilityState={{selected:key===tab}} onPress={()=>onTab(key)} key={key} style={[s.sideLink,tab===key&&s.active]}><Text style={s.sideGlyph}>{glyph}</Text><Text style={[s.sideText,tab===key&&{color:P.light}]}>{name}</Text></Pressable>)}</View>
 {!compact?<View style={s.sideBottom}><Text style={s.sideBottomTitle}>Decisions today.</Text><Text style={s.sideBottomTitleBlue}>Built for tomorrow.</Text><Text style={s.hint}>Procurement intelligence, without the noise.</Text></View>:null}
</View>;
}
export function WorldToolbar({onRefresh,tab}){const {s}=useWorldTheme();return <View style={s.toolbar}><View><Eyebrow>OBRASIGNAL / INTELLIGENCE</Eyebrow><Text style={s.toolbarTitle}>{nav.find(x=>x[0]===tab)?.[2]||'Workspace'}</Text></View><Btn secondary onPress={onRefresh}>↻ Refresh</Btn></View>;}
export function WorldHero({compact}){const {s}=useWorldTheme();return <View style={s.workHero}><Skyline/><View style={s.heroVeil}/><View style={s.workHeroCopy}><Eyebrow>GLOBAL PROCUREMENT INTELLIGENCE</Eyebrow><Text style={[s.workHeroTitle,{color:'#F3F7FE'},compact&&{fontSize:26,lineHeight:34}]}>Anticipate opportunities.{ '\n'}<Text style={{color:'#78BEFB'}}>Build what’s next.</Text></Text><Text style={s.heroBody}>Official sources, prioritised signals and clear commercial decisions.</Text></View></View>;}
export function WorldMarkets(){const {s}=useWorldTheme();return <View style={s.analytics}><Eyebrow>VERIFIED MARKET SCOPE</Eyebrow><Text style={s.largePanelTitle}>International ambition. Defined sources.</Text><Text style={s.hint}>Markets shown have European source definitions, not a promise of complete coverage.</Text><View style={s.markets}>{EUROPE_MARKETS.map(([code,name])=><Tile key={code} style={s.countryTile}><Text style={s.country}>{name}</Text><Text style={s.code}>{code}</Text></Tile>)}</View></View>;}

export function WorldLanding({onLogin}){
const {s,P}=useWorldTheme();
const {width}=useWindowDimensions(),compact=width<760;
const [preview,setPreview]=useState(false);
return <ScrollView style={s.public} contentContainerStyle={s.publicContent}>
 <View style={s.publicNav}><BrandLogo inverse markSize={35} textSize={22}/><View style={s.navActions}><Btn secondary onPress={()=>setPreview(!preview)}>{preview?'Introduction':'Explore platform'}</Btn><Btn onPress={onLogin}>Sign in →</Btn></View></View>
 {preview?<View style={s.preview}><View style={s.demoLabel}><Text style={s.demoLabelText}>INTERFACE PREVIEW · NOT LIVE DATA</Text></View><Text style={s.previewTitle}>Your procurement command centre.</Text><Text style={s.hint}>This demonstration never loads private accounts or invents official tender figures.</Text><WorldHero compact={compact}/><WorldAnalytics preview compact={compact}/><View style={s.previewActions}><Btn secondary onPress={()=>setPreview(false)}>← Back</Btn><Btn onPress={onLogin}>Private access →</Btn></View></View>:
 <>
 <View style={s.publicHero}><Skyline/><View style={s.heroVeil}/><View style={[s.heroContent,compact&&{paddingHorizontal:22,paddingTop:85,paddingBottom:60}]}>
 <Eyebrow>PUBLIC PROCUREMENT INTELLIGENCE / GLOBAL VISION</Eyebrow>
 <Text style={[s.headline,{fontSize:compact?43:75,lineHeight:compact?50:81}]}>Anticipate{ '\n'}opportunities.{ '\n'}<Text style={{color:P.blue}}>Build what’s next.</Text></Text>
 <Text style={s.heroBody}>Find the signals worth pursuing. Turn official procurement information into confident commercial decisions.</Text>
 <View style={[s.heroButtons,compact&&s.vertical]}><Btn onPress={()=>setPreview(true)}>Explore the experience ↗</Btn><Btn secondary onPress={onLogin}>Existing customer →</Btn></View>
 <View style={s.heroFooter}><Text style={s.heroFootText}>INTERNATIONAL VISION</Text><View style={s.divot}/><Text style={s.heroFootText}>OFFICIAL SOURCES</Text><View style={s.divot}/><Text style={s.heroFootText}>EXPLAINABLE FIT</Text></View>
 </View><View style={s.copperLine}/></View>
 <View style={s.below}><Eyebrow>01 / A DIFFERENT STANDARD</Eyebrow><Text style={s.belowTitle}>Less noise. <Text style={{color:P.blue}}>More direction.</Text></Text>
 <View style={[s.valueGrid,compact&&s.vertical]}>{[
 ['01','DISCOVER','Identify opportunities through verified procurement sources.'],
 ['02','EVALUATE','Understand the fit, the evidence and the risks.'],
 ['03','ADVANCE','Keep the next commercial step connected to its origin.']
 ].map(([n,title,desc])=><Tile key={n} style={s.valueTile}><Text style={s.valueNum}>{n}</Text><Text style={s.valueTitle}>{title}</Text><Text style={s.valueDesc}>{desc}</Text><View style={s.valueAccent}/></Tile>)}</View>
 <View style={s.bottomCta}><Text style={s.ctaTitle}>See the platform before the first decision.</Text><Btn onPress={()=>setPreview(true)}>Open workspace preview ↗</Btn></View></View>
 </>}
 <View style={s.footer}><BrandLogo inverse markSize={25} textSize={17}/><Text style={s.footerText}>Global ambition · verified operational markets only · © 2026 ObraSignal</Text></View>
 </ScrollView>;
}
function makeStyles(P){return StyleSheet.create({
 public:{flex:1,backgroundColor:P.bg},publicContent:{backgroundColor:P.bg,minHeight:'100%'},
 publicNav:{minHeight:83,paddingVertical:14,paddingHorizontal:24,backgroundColor:'#04101A',flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:10,borderBottomWidth:1,borderBottomColor:P.line,flexWrap:'wrap'},
 navActions:{flexDirection:'row',alignItems:'center',gap:9,flexWrap:'wrap'},btn:{minHeight:43,paddingHorizontal:19,paddingVertical:10,backgroundColor:P.copper,borderRadius:6,borderWidth:1,borderColor:'#E1A981',justifyContent:'center',alignItems:'center'},
 btnText:{color:'#071524',fontFamily:FONT_BODY,fontSize:12,fontWeight:'800',letterSpacing:.2},btnSec:{backgroundColor:P.secondaryButton,borderColor:P.secondaryBorder},btnSecText:{color:P.light},
 publicHero:{minHeight:640,position:'relative',overflow:'hidden',justifyContent:'center'},heroVeil:{position:'absolute',left:0,right:0,top:0,bottom:0,backgroundColor:'rgba(3,11,22,.46)'},
 heroContent:{maxWidth:1540,width:'100%',marginHorizontal:'auto',paddingTop:100,paddingBottom:74,paddingHorizontal:62},
 eyebrow:{fontFamily:FONT_BODY,fontSize:9,color:P.blue,letterSpacing:2.3,fontWeight:'800'},
 headline:{color:P.light,fontWeight:'900',letterSpacing:-2,maxWidth:1000,marginTop:19,textShadowColor:'#000C',textShadowRadius:16},
 heroBody:{fontFamily:FONT_BODY,fontSize:16,color:'#D4E5F3',maxWidth:650,lineHeight:26,marginTop:22},
 heroButtons:{flexDirection:'row',alignItems:'flex-start',gap:12,marginTop:28},
 heroFooter:{flexDirection:'row',gap:14,alignItems:'center',flexWrap:'wrap',marginTop:58},heroFootText:{fontFamily:FONT_BODY,fontSize:9,fontWeight:'800',color:P.soft,letterSpacing:1.4},
 divot:{width:20,height:1,backgroundColor:P.copper},copperLine:{height:3,backgroundColor:P.copper},
 below:{maxWidth:1550,width:'100%',alignSelf:'center',paddingHorizontal:26,paddingVertical:78},
 belowTitle:{fontFamily:FONT_BODY,fontSize:36,color:P.light,fontWeight:'900',marginTop:12,marginBottom:27},
 valueGrid:{flexDirection:'row',gap:13},vertical:{flexDirection:'column'},tile:{borderRadius:10,borderWidth:1,borderColor:P.line,backgroundColor:P.panel,padding:16,overflow:'hidden'},
 valueTile:{flex:1,minHeight:210,padding:24,justifyContent:'space-between'},valueNum:{color:P.accentLabel,fontFamily:FONT_BODY,fontSize:12,fontWeight:'900'},
 valueTitle:{fontFamily:FONT_BODY,fontSize:23,color:P.light,fontWeight:'900'},valueDesc:{fontFamily:FONT_BODY,fontSize:13,lineHeight:21,color:P.muted},valueAccent:{height:3,width:36,backgroundColor:P.copper},
 bottomCta:{flexDirection:'row',gap:20,alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',paddingTop:50,marginTop:32,borderTopWidth:1,borderTopColor:P.line},
 ctaTitle:{color:P.light,fontFamily:FONT_BODY,fontSize:25,fontWeight:'800'},footer:{padding:24,borderTopWidth:1,borderTopColor:P.line,flexDirection:'row',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:12},
 footerText:{color:P.muted,fontFamily:FONT_BODY,fontSize:10},preview:{width:'100%',maxWidth:1600,alignSelf:'center',padding:22,gap:12},
 demoLabel:{alignSelf:'flex-start',paddingVertical:8,paddingHorizontal:12,borderRadius:5,borderColor:P.copper,borderWidth:1},demoLabelText:{color:'#FACFAE',fontFamily:FONT_BODY,fontSize:10,fontWeight:'900',letterSpacing:1.2},
 previewTitle:{color:P.light,fontFamily:FONT_BODY,fontSize:30,fontWeight:'900'},previewActions:{flexDirection:'row',gap:12,flexWrap:'wrap',paddingTop:20},
 workHero:{minHeight:250,borderRadius:11,borderWidth:1,borderColor:P.line,overflow:'hidden',justifyContent:'center'},
 workHeroCopy:{padding:25,maxWidth:800},workHeroTitle:{fontFamily:FONT_BODY,fontSize:34,lineHeight:43,color:P.light,fontWeight:'900',marginTop:11},analytics:{paddingVertical:14,gap:13},
 statGrid:{flexDirection:'row',flexWrap:'wrap',gap:11},stat:{minHeight:116,flexBasis:210,flexGrow:1,justifyContent:'space-between'},
 statLabel:{fontFamily:FONT_BODY,fontSize:11,color:P.muted},statNumber:{fontFamily:FONT_BODY,fontSize:31,color:P.light,fontWeight:'900'},statBar:{width:'36%',height:3,backgroundColor:P.blue},
 mainPanels:{flexDirection:'row',gap:12},largePanel:{flex:1,minWidth:0,minHeight:375},panelHead:{flexDirection:'row',justifyContent:'space-between',gap:7,flexWrap:'wrap'},
 panelTag:{fontFamily:FONT_BODY,fontSize:9,color:P.accentLabel,fontWeight:'800',letterSpacing:1},radar:{flex:1,alignItems:'center',justifyContent:'center',backgroundColor:P.radar,borderRadius:7,marginVertical:12},
 hint:{fontFamily:FONT_BODY,fontSize:11,color:P.muted,lineHeight:18,marginTop:9},largePanelTitle:{fontFamily:FONT_BODY,fontSize:19,color:P.light,fontWeight:'800',marginTop:16},
 chart:{minHeight:209,flex:1,flexDirection:'row',alignItems:'flex-end',gap:9,paddingBottom:4,marginTop:13,borderBottomWidth:1,borderBottomColor:P.line},
 barSlot:{flex:1,alignItems:'center'},barTrack:{height:167,width:'100%',justifyContent:'flex-end',alignItems:'center'},bar:{width:'80%',borderTopLeftRadius:3,borderTopRightRadius:3},
 barLabel:{color:P.muted,fontFamily:FONT_BODY,fontSize:10,marginTop:6},
 queueRow:{flexDirection:'row',alignItems:'center',gap:9,paddingVertical:13,borderBottomWidth:1,borderBottomColor:P.line},queueStripe:{width:3,height:29,backgroundColor:P.copper},
 queueTitle:{fontFamily:FONT_BODY,fontSize:12,color:P.light,fontWeight:'800'},queueSource:{fontFamily:FONT_BODY,fontSize:10,color:P.muted,marginTop:5},queueScore:{fontFamily:FONT_BODY,fontSize:17,color:P.blue,fontWeight:'900'},
 noData:{flex:1,minHeight:230,justifyContent:'center',alignItems:'center',paddingHorizontal:10},
 emptyIcon:{fontFamily:FONT_BODY,fontSize:42,color:P.blue},emptyTitle:{fontFamily:FONT_BODY,fontSize:14,fontWeight:'800',color:P.light,textAlign:'center'},emptySub:{fontFamily:FONT_BODY,fontSize:11,color:P.muted,textAlign:'center',lineHeight:17,marginTop:9},
 lowerPanels:{flexDirection:'row',gap:12},lower:{flex:1,minWidth:0,minHeight:175},lowerTitle:{fontFamily:FONT_BODY,fontSize:17,color:P.light,fontWeight:'800',marginTop:10},
 sourceRow:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',marginTop:9,gap:8},
 sourceText:{flex:1,color:P.muted,fontFamily:FONT_BODY,fontSize:11},mintText:{color:P.mint,fontFamily:FONT_BODY,fontSize:10},coverageValue:{fontFamily:FONT_BODY,fontSize:32,color:P.blue,fontWeight:'900',marginTop:15},
 coverageSub:{fontFamily:FONT_BODY,fontSize:10,color:P.muted,fontWeight:'600'},flowLabel:{fontFamily:FONT_BODY,fontSize:10,color:P.accentLabel,fontWeight:'900',marginTop:24,letterSpacing:2},
 sidebar:{width:240,minHeight:600,backgroundColor:P.sidebar,borderRightWidth:1,borderRightColor:P.line,padding:17},
 sidebarCompact:{width:'100%',minHeight:0,borderRightWidth:0,borderBottomWidth:1,borderBottomColor:P.line},
 sidebarBrand:{paddingVertical:17,marginBottom:19},sideLinks:{gap:7,marginTop:16},sideLinksCompact:{flexDirection:'row',flexWrap:'wrap'},
 sideLink:{flexDirection:'row',alignItems:'center',gap:11,borderRadius:7,padding:12},
 active:{backgroundColor:P.sidebarActive,borderWidth:1,borderColor:P.blue},sideGlyph:{fontFamily:FONT_BODY,fontSize:18,color:P.blue,width:22},
 sideText:{fontFamily:FONT_BODY,fontSize:12,color:P.muted,fontWeight:'700'},sideBottom:{marginTop:'auto',padding:15,backgroundColor:P.sidebarBottom,borderRadius:8,borderWidth:1,borderColor:P.line},
 sideBottomTitle:{fontFamily:FONT_BODY,fontSize:17,color:P.light,fontWeight:'900'},sideBottomTitleBlue:{fontFamily:FONT_BODY,fontSize:17,color:P.blue,fontWeight:'900'},
 toolbar:{minHeight:70,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:12,flexWrap:'wrap'},
 toolbarTitle:{fontFamily:FONT_BODY,fontSize:21,color:P.light,fontWeight:'900',marginTop:4},
 markets:{flexDirection:'row',gap:10,flexWrap:'wrap'},countryTile:{flexBasis:170,flexGrow:1,flexDirection:'row',alignItems:'center',justifyContent:'space-between'},
 country:{fontFamily:FONT_BODY,fontSize:12,color:P.light},code:{color:P.accentLabel,fontFamily:FONT_BODY,fontSize:10,fontWeight:'900'}
});}
