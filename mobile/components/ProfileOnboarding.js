import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { api } from '../src/api';
import { trackTraffic } from '../src/analytics';
import { EUROPE_MARKETS } from '../src/markets';
import { storage } from '../src/storage';
import { BRAND } from '../src/brand-palette.mjs';
import BrandLogo from './BrandLogo';

const COLORS={bg:'#06111D',card:'#0B1C2D',line:'#2B4760',text:'#F4F8FE',muted:'#A4BFD5',blue:'#78BEFB',blueSoft:'#10283D',green:'#9AE8C7',red:'#FFB0B8'};
const MODES=[['europe','Select supported markets'],['portugal','Portugal only'],['regions','Specific Portuguese regions']];
const parseList=value=>value.split(/[,\n]/).map(item=>item.trim()).filter(Boolean);
const parseCurrency=value=>{const clean=String(value||'').replace(/[^\d,.-]/g,'').replace(',','.');return clean===''?null:Number(clean)};
const displayCurrency=value=>value==null?'':new Intl.NumberFormat('en-GB',{maximumFractionDigits:0}).format(value);
function readiness(profile){let done=0;if(profile.name)done++;if(profile.activity)done++;if(profile.contract_interests?.length)done++;if(profile.countries?.length)done++;if(profile.min_value!=null||profile.max_value!=null)done++;return Math.round(done/5*100)}
function sameCoreProfile(expected,actual){return Boolean(actual&&actual.name===expected.name&&actual.activity===expected.activity&&JSON.stringify(actual.contract_interests||[])===JSON.stringify(expected.contract_interests||[]))}

export default function ProfileOnboarding({initialProfile,onComplete}){
  const[name,setName]=useState(initialProfile?.name||'');
  const[activity,setActivity]=useState(initialProfile?.activity||'');
  const[interests,setInterests]=useState((initialProfile?.contract_interests||initialProfile?.keywords||[]).join('\n'));
  const[coverageMode,setCoverageMode]=useState(initialProfile?.coverage_mode||(initialProfile?.regions?.length?'regions':'europe'));
  const[regions,setRegions]=useState((initialProfile?.regions||[]).join(', '));
  const[countries,setCountries]=useState(initialProfile?.countries?.length?initialProfile.countries:[]);
  const[minValue,setMinValue]=useState(displayCurrency(initialProfile?.min_value));
  const[maxValue,setMaxValue]=useState(displayCurrency(initialProfile?.max_value));
  const[advanced,setAdvanced]=useState(false);const[cpv,setCpv]=useState((initialProfile?.cpv_prefixes||[]).join(', '));
  const[saving,setSaving]=useState(false);const[error,setError]=useState('');
  const draft=useMemo(()=>({...initialProfile,name:name.trim(),activity:activity.trim(),contract_interests:parseList(interests),coverage_mode:coverageMode,countries:coverageMode==='europe'?countries:['PRT'],regions:coverageMode==='regions'?parseList(regions):[],cpv_prefixes:parseList(cpv),min_value:parseCurrency(minValue),max_value:parseCurrency(maxValue)}),[initialProfile,name,activity,interests,coverageMode,countries,regions,cpv,minValue,maxValue]);
  const toggleCountry=code=>setCountries(current=>current.includes(code)?current.filter(x=>x!==code):[...current,code]);
  const save=async()=>{
    if(!draft.name||!draft.activity){setError('Enter a company name and primary activity.');return}
    if(coverageMode==='europe' && !countries.length){setError('Select at least one currently supported market.');return}
    if(!draft.contract_interests.length){setError('Describe at least one target contract or service.');return}
    if([draft.min_value,draft.max_value].some(v=>v!=null&&!Number.isFinite(v))||(draft.min_value!=null&&draft.max_value!=null&&draft.min_value>draft.max_value)){setError('Review the usual contract value range.');return}
    setSaving(true);setError('');
    try{
      const saved=await api.saveProfile(draft);
      if(!sameCoreProfile(draft,saved))throw new Error('The server did not confirm the saved company profile.');
      const persisted=await api.profile();
      if(!sameCoreProfile(saved,persisted))throw new Error('The company profile was not saved. Please retry.');
      await storage.setProfile(persisted);
      trackTraffic('profile_completed').catch(()=>{});
      onComplete(persisted);
    }catch(err){setError(err?.responseBody?.message||err?.responseBody?.error||err?.message||'Unable to save company profile.')}finally{setSaving(false)}
  };
  return <ScrollView style={styles.safe} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled"><View style={styles.hero}><BrandLogo inverse markSize={42} textSize={24} style={{marginBottom:28}}/><Text style={styles.eyebrow}>GETTING STARTED</Text><Text style={styles.title}>Tell us what your company does.</Text><Text style={styles.subtitle}>Describe your capabilities in everyday language. ObraSignal helps structure relevant procurement signals.</Text><View style={styles.readiness}><View><Text style={styles.readinessLabel}>COMPANY PROFILE</Text><Text style={styles.readinessCopy}>Better detail makes for better relevance.</Text></View><Text style={styles.readinessValue}>{readiness(draft)}%</Text></View></View><View style={styles.card}>
    <Text style={styles.section}>Your company</Text><TextInput value={name} onChangeText={setName} placeholder="Company name" placeholderTextColor={COLORS.muted} style={styles.input}/><TextInput value={activity} onChangeText={setActivity} placeholder="Primary activity — e.g. electrical installation" placeholderTextColor={COLORS.muted} style={styles.input}/>
    <Text style={styles.section}>Which contracts or services do you target?</Text><Text style={styles.help}>Be specific: steelwork, school maintenance or solar panel installation. One activity per line.</Text><TextInput value={interests} onChangeText={setInterests} multiline numberOfLines={4} placeholder={'Industrial building construction\nRoof renovation'} placeholderTextColor={COLORS.muted} style={[styles.input,styles.multiline]}/>
    <Pressable onPress={()=>setAdvanced(x=>!x)}><Text style={styles.advanced}>{advanced?'Hide advanced CPV settings':'Advanced: review CPV codes'}</Text></Pressable>{advanced?<><Text style={styles.help}>Optional. Only edit if you already work with CPV codes.</Text><TextInput value={cpv} onChangeText={setCpv} placeholder="Ex.: 45, 4531" placeholderTextColor={COLORS.muted} style={styles.input}/></>:null}
    <Text style={styles.section}>Which markets can you serve?</Text><Text style={styles.help}>Select countries with verified source coverage. Global expansion is a product strategy, not a claim that every market is live.</Text><View style={styles.choices}>{MODES.map(([key,label])=><Pressable key={key} onPress={()=>setCoverageMode(key)} style={[styles.choice,coverageMode===key&&styles.choiceOn]}><Text style={[styles.choiceText,coverageMode===key&&styles.choiceTextOn]}>{label}</Text></Pressable>)}</View>{coverageMode==='regions'?<><Text style={styles.help}>Specify the districts or cities in Portugal your company can serve.</Text><TextInput value={regions} onChangeText={setRegions} placeholder="e.g. Lisbon, Setúbal, Leiria" placeholderTextColor={COLORS.muted} style={styles.input}/></>:null}{coverageMode==='europe'?<><Text style={styles.help}>32 supported European markets via TED/eForms and selected national connectors.</Text><View style={styles.choices}>{EUROPE_MARKETS.map(([code,label])=><Pressable key={code} onPress={()=>toggleCountry(code)} style={[styles.choice,countries.includes(code)&&styles.choiceOn]}><Text style={[styles.choiceText,countries.includes(code)&&styles.choiceTextOn]}>{label}</Text></Pressable>)}</View></>:null}
    <Text style={styles.section}>Typical contract value</Text><Text style={styles.help}>Optional. Specify your usual contract range in euros.</Text><View style={styles.row}><View style={styles.half}><Text style={styles.moneyLabel}>From</Text><View style={styles.money}><Text style={styles.euro}>€</Text><TextInput value={minValue} onChangeText={setMinValue} placeholder="50 000" keyboardType="numeric" placeholderTextColor={COLORS.muted} style={styles.moneyInput}/></View></View><View style={styles.half}><Text style={styles.moneyLabel}>To</Text><View style={styles.money}><Text style={styles.euro}>€</Text><TextInput value={maxValue} onChangeText={setMaxValue} placeholder="1 000 000" keyboardType="numeric" placeholderTextColor={COLORS.muted} style={styles.moneyInput}/></View></View></View>
    {error?<Text accessibilityRole="alert" style={styles.error}>{error}</Text>:null}<Pressable onPress={save} disabled={saving} style={({pressed})=>[styles.button,pressed&&{opacity:.86},saving&&{opacity:.6}]}>{saving?<ActivityIndicator color={COLORS.bg}/>:<Text style={styles.buttonText}>Create my radar</Text>}</Pressable>
  </View></ScrollView>
}
const styles=StyleSheet.create({safe:{flex:1,backgroundColor:COLORS.bg},content:{width:'100%',maxWidth:860,alignSelf:'center',paddingHorizontal:24,paddingTop:34,paddingBottom:60},hero:{marginBottom:22},brand:{color:COLORS.text,fontSize:20,fontWeight:'800',letterSpacing:-.7,marginBottom:32},brandBlue:{color:COLORS.muted},eyebrow:{color:COLORS.blue,fontSize:9,fontWeight:'900',letterSpacing:1.5},title:{color:COLORS.text,fontSize:34,fontWeight:'900',lineHeight:40,letterSpacing:-1,marginTop:8},subtitle:{color:COLORS.muted,fontSize:13,lineHeight:21,marginTop:10,maxWidth:650},readiness:{marginTop:20,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:18,padding:16,backgroundColor:COLORS.blueSoft,borderRadius:14,borderWidth:1,borderColor:BRAND.mineral},readinessLabel:{color:COLORS.text,fontSize:9,fontWeight:'900',letterSpacing:1.2},readinessCopy:{color:COLORS.muted,fontSize:10,lineHeight:15,marginTop:4},readinessValue:{color:COLORS.green,fontWeight:'900',fontSize:24},card:{backgroundColor:COLORS.card,borderRadius:18,padding:20,borderWidth:1,borderColor:COLORS.line},section:{color:COLORS.text,fontSize:13,fontWeight:'900',marginTop:16,marginBottom:8},help:{color:COLORS.muted,fontSize:11,lineHeight:18,marginBottom:9},input:{borderWidth:1,borderColor:COLORS.line,borderRadius:11,paddingHorizontal:14,paddingVertical:12,color:COLORS.text,backgroundColor:COLORS.card,marginBottom:10},multiline:{minHeight:112,textAlignVertical:'top'},advanced:{color:COLORS.text,fontWeight:'800',fontSize:11,marginBottom:12},choices:{flexDirection:'row',flexWrap:'wrap',gap:8,marginBottom:12},choice:{borderWidth:1,borderColor:BRAND.mineral,borderRadius:999,paddingHorizontal:12,paddingVertical:9},choiceOn:{borderColor:COLORS.blue,backgroundColor:COLORS.blueSoft},choiceText:{color:COLORS.muted,fontSize:11,fontWeight:'700'},choiceTextOn:{color:COLORS.text},row:{flexDirection:'row',gap:10,flexWrap:'wrap'},half:{flex:1,minWidth:190},moneyLabel:{color:COLORS.muted,fontSize:10,marginBottom:5},money:{flexDirection:'row',alignItems:'center',borderWidth:1,borderColor:COLORS.line,borderRadius:11,backgroundColor:COLORS.card},euro:{color:COLORS.text,paddingLeft:12,fontWeight:'800'},moneyInput:{flex:1,color:COLORS.text,padding:12},error:{color:COLORS.red,marginVertical:8,lineHeight:18,fontSize:11},button:{minHeight:50,borderRadius:11,backgroundColor:BRAND.copper,alignItems:'center',justifyContent:'center',marginTop:14},buttonText:{color:COLORS.text,fontWeight:'900',fontSize:13}});
