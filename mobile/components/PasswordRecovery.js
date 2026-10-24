import React, { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { supabase } from '../lib/supabase';
import { BRAND } from '../src/brand-palette.mjs';
import BrandLogo from './BrandLogo';
import {FONT_BODY,FONT_DISPLAY} from '../src/typography.mjs';
import {classifyAuthFailure} from '../src/auth-failure-feedback.mjs';

const C={bg:'#06111D',panel:'#0B1C2D',line:'#2B4760',text:'#F4F8FE',muted:'#A4BFD5',blue:'#78BEFB',green:'#9AE8C7',red:'#FFB0B8'};

export default function PasswordRecovery({onComplete,onCancel}){
  const[password,setPassword]=useState('');
  const[confirm,setConfirm]=useState('');
  const[busy,setBusy]=useState(false);
  const[error,setError]=useState('');
  const[success,setSuccess]=useState('');
  const[passwordUpdated,setPasswordUpdated]=useState(false);

  const submit=async()=>{
    setError('');setSuccess('');
    if(!passwordUpdated){
      if(password.length<8){setError('Use a password with at least 8 characters.');return;}
      if(password!==confirm){setError('The passwords do not match.');return;}
    }
    setBusy(true);
    try{
      if(!passwordUpdated){
        const {error:updateError}=await supabase.auth.updateUser({password});
        if(updateError)throw updateError;
        setPasswordUpdated(true);
        setPassword('');
        setConfirm('');
      }
      const {error:signOutError}=await supabase.auth.signOut();
      if(signOutError){
        setError('Password updated, but we could not end the recovery session. Retry sign-out or close this browser; do not continue to your workspace.');
        return;
      }
      onComplete?.();
    }catch(e){
      setError(passwordUpdated
        ? 'Password was updated but sign-out failed. Please retry ending this recovery session.'
        : classifyAuthFailure(e,'recovery').message);
    }finally{setBusy(false);}
  };

  const cancel=async()=>{
    if(busy)return;
    try{await supabase.auth.signOut();}catch(_){}
    onCancel?.();
  };

  return <View style={s.page}><View style={s.card}>
    <BrandLogo inverse markSize={56} textSize={30}/>
    <Text style={s.eyebrow}>ACCOUNT RECOVERY</Text>
    <Text style={s.title}>Set a new password.</Text>
    <Text style={s.body}>Your recovery link has established a temporary identity session. Choose a new password to complete the reset.</Text>
    {!passwordUpdated?<><Text style={s.label}>NEW PASSWORD</Text><TextInput value={password} onChangeText={setPassword} secureTextEntry autoComplete="new-password" placeholder="At least 8 characters" placeholderTextColor={C.muted} style={s.input}/>
    <Text style={s.label}>CONFIRM PASSWORD</Text><TextInput value={confirm} onChangeText={setConfirm} secureTextEntry autoComplete="new-password" placeholder="Repeat the new password" placeholderTextColor={C.muted} style={s.input}/></>:null}
    {error?<Text accessibilityRole="alert" style={s.error}>{error}</Text>:null}{success?<Text style={s.success}>{success}</Text>:null}
    <Pressable accessibilityRole="button" disabled={busy} onPress={submit} style={[s.primary,busy&&s.disabled]}>{busy?<ActivityIndicator color={C.bg}/>:<Text style={s.primaryText}>{passwordUpdated?'Retry secure sign-out':'Save new password'}</Text>}</Pressable>
    <Pressable accessibilityRole="button" disabled={busy} onPress={cancel} style={s.secondary}><Text style={s.secondaryText}>Cancel and sign out</Text></Pressable>
  </View></View>;
}

const s=StyleSheet.create({page:{flex:1,minHeight:'100%',backgroundColor:C.bg,alignItems:'center',justifyContent:'center',padding:24},card:{width:'100%',maxWidth:520,backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:18,padding:28},brand:{color:C.text,fontFamily:FONT_BODY,fontSize:22,fontWeight:'800',letterSpacing:-.8},brandBlue:{color:'#A4BFD5'},eyebrow:{color:C.blue,fontFamily:FONT_BODY,fontSize:9,fontWeight:'900',letterSpacing:1.3,marginTop:28},title:{color:C.text,fontFamily:FONT_DISPLAY,fontSize:28,lineHeight:34,fontWeight:'900',marginTop:8},body:{color:C.muted,fontFamily:FONT_BODY,fontSize:12,lineHeight:19,marginTop:9,marginBottom:20},label:{color:'#D9E6F2',fontFamily:FONT_BODY,fontSize:9,fontWeight:'900',letterSpacing:.6,marginTop:10,marginBottom:6},input:{minHeight:50,borderWidth:1,borderColor:'#36546F',borderRadius:10,backgroundColor:'#081725',color:C.text,paddingHorizontal:13},error:{color:C.red,fontFamily:FONT_BODY,fontSize:11,lineHeight:17,marginTop:10},success:{color:C.green,fontFamily:FONT_BODY,fontSize:11,lineHeight:17,marginTop:10},primary:{minHeight:48,borderRadius:10,backgroundColor:C.text,alignItems:'center',justifyContent:'center',marginTop:18},primaryText:{color:C.bg,fontFamily:FONT_BODY,fontSize:12,fontWeight:'900'},secondary:{minHeight:42,alignItems:'center',justifyContent:'center',marginTop:6},secondaryText:{color:'#D9E6F2',fontFamily:FONT_BODY,fontSize:11,fontWeight:'800'},disabled:{opacity:.55}});
