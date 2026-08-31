import React, { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { supabase } from '../lib/supabase';

const C={bg:'#07111C',panel:'#0D1A29',line:'#22364F',text:'#F4F7FB',muted:'#9BAABD',blue:'#5F8DF7',green:'#72DFA1',red:'#FF8B9A'};

export default function PasswordRecovery({onComplete,onCancel}){
  const[password,setPassword]=useState('');
  const[confirm,setConfirm]=useState('');
  const[busy,setBusy]=useState(false);
  const[error,setError]=useState('');
  const[success,setSuccess]=useState('');

  const submit=async()=>{
    setError('');setSuccess('');
    if(password.length<8){setError('Usa uma palavra-passe com pelo menos 8 caracteres.');return;}
    if(password!==confirm){setError('As duas palavras-passe não coincidem.');return;}
    setBusy(true);
    try{
      const {error:updateError}=await supabase.auth.updateUser({password});
      if(updateError)throw updateError;
      setSuccess('Palavra-passe atualizada.');
      onComplete?.();
    }catch(e){setError(e?.message||'Não foi possível atualizar a palavra-passe. Pede um novo link de recuperação.');}
    finally{setBusy(false);}
  };

  const cancel=async()=>{
    if(busy)return;
    try{await supabase.auth.signOut();}catch(_){}
    onCancel?.();
  };

  return <View style={s.page}><View style={s.card}>
    <Text style={s.brand}>Obra<Text style={s.brandBlue}>Signal</Text></Text>
    <Text style={s.eyebrow}>RECUPERAÇÃO DE ACESSO</Text>
    <Text style={s.title}>Define uma nova palavra-passe.</Text>
    <Text style={s.body}>O link de recuperação já confirmou a sessão temporária. Agora escolhe a nova palavra-passe antes de continuar para os dados privados da conta.</Text>
    <Text style={s.label}>NOVA PALAVRA-PASSE</Text><TextInput value={password} onChangeText={setPassword} secureTextEntry autoComplete="new-password" placeholder="Pelo menos 8 caracteres" placeholderTextColor={C.muted} style={s.input}/>
    <Text style={s.label}>CONFIRMAR PALAVRA-PASSE</Text><TextInput value={confirm} onChangeText={setConfirm} secureTextEntry autoComplete="new-password" placeholder="Repete a nova palavra-passe" placeholderTextColor={C.muted} style={s.input}/>
    {error?<Text accessibilityRole="alert" style={s.error}>{error}</Text>:null}{success?<Text style={s.success}>{success}</Text>:null}
    <Pressable accessibilityRole="button" disabled={busy} onPress={submit} style={[s.primary,busy&&s.disabled]}>{busy?<ActivityIndicator color={C.bg}/>:<Text style={s.primaryText}>Guardar nova palavra-passe</Text>}</Pressable>
    <Pressable accessibilityRole="button" disabled={busy} onPress={cancel} style={s.secondary}><Text style={s.secondaryText}>Cancelar e sair</Text></Pressable>
  </View></View>;
}

const s=StyleSheet.create({page:{flex:1,minHeight:'100%',backgroundColor:C.bg,alignItems:'center',justifyContent:'center',padding:24},card:{width:'100%',maxWidth:520,backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:18,padding:28},brand:{color:C.text,fontSize:22,fontWeight:'800',letterSpacing:-.8},brandBlue:{color:'#7FA2FF'},eyebrow:{color:C.blue,fontSize:9,fontWeight:'900',letterSpacing:1.3,marginTop:28},title:{color:C.text,fontSize:28,lineHeight:34,fontWeight:'900',marginTop:8},body:{color:C.muted,fontSize:12,lineHeight:19,marginTop:9,marginBottom:20},label:{color:'#C4CFDD',fontSize:9,fontWeight:'900',letterSpacing:.6,marginTop:10,marginBottom:6},input:{minHeight:50,borderWidth:1,borderColor:'#2A3E5B',borderRadius:10,backgroundColor:'#091522',color:C.text,paddingHorizontal:13},error:{color:C.red,fontSize:11,lineHeight:17,marginTop:10},success:{color:C.green,fontSize:11,lineHeight:17,marginTop:10},primary:{minHeight:48,borderRadius:10,backgroundColor:C.text,alignItems:'center',justifyContent:'center',marginTop:18},primaryText:{color:C.bg,fontSize:12,fontWeight:'900'},secondary:{minHeight:42,alignItems:'center',justifyContent:'center',marginTop:6},secondaryText:{color:'#A9BCFF',fontSize:11,fontWeight:'800'},disabled:{opacity:.55}});
