import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { api } from '../src/api';

const CONFIRMATION = 'DELETE_MY_OBRASIGNAL_DATA';
const EXPORT_SCOPE = 'CURRENT_CANONICAL_SERVER_ACCOUNT_DATA_ONLY';

function errorMessage(error){
  return error?.responseBody?.error || error?.message || 'Não foi possível concluir o pedido.';
}

export default function AccountPrivacyControls(){
  const [open,setOpen]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [exportData,setExportData]=useState(null);
  const [status,setStatus]=useState(null);
  const [confirmation,setConfirmation]=useState('');

  const refreshStatus=async()=>{
    setLoading(true);setError('');
    try{setStatus(await api.accountDeletionStatus());}
    catch(error){setError(errorMessage(error));}
    finally{setLoading(false);}
  };

  useEffect(()=>{if(open)refreshStatus();},[open]);

  const requestExport=async()=>{
    setLoading(true);setError('');setExportData(null);
    try{setExportData(await api.accountExport());}
    catch(error){setError(errorMessage(error));}
    finally{setLoading(false);}
  };

  const requestDeletion=async()=>{
    if(confirmation!==CONFIRMATION){setError(`Escreve exatamente ${CONFIRMATION} para confirmar.`);return;}
    setLoading(true);setError('');
    try{const result=await api.requestAccountDeletion(confirmation);setStatus(result?.deletion||result);}
    catch(error){setError(errorMessage(error));}
    finally{setLoading(false);}
  };

  return <>
    <Pressable accessibilityRole="button" accessibilityLabel="Privacidade e dados" onPress={()=>setOpen(true)} style={s.trigger}><Text style={s.triggerText}>Privacidade e dados</Text></Pressable>
    <Modal visible={open} animationType="slide" transparent onRequestClose={()=>setOpen(false)}>
      <View style={s.backdrop}><View style={s.panel}><ScrollView contentContainerStyle={s.content}>
        <View style={s.row}><Text style={s.title}>Privacidade e dados</Text><Pressable onPress={()=>setOpen(false)}><Text style={s.close}>Fechar</Text></Pressable></View>
        <Text style={s.body}>A exportação apresenta apenas os dados atuais que o servidor canónico consegue provar. Não representa dados de sistemas externos.</Text>
        <Pressable disabled={loading} onPress={requestExport} style={s.button}><Text style={s.buttonText}>Exportar os meus dados</Text></Pressable>
        {exportData?<View style={s.box}><Text style={s.label}>schema_version: {String(exportData.schema_version??'UNKNOWN')}</Text><Text style={s.label}>Âmbito: {String(exportData.scope||EXPORT_SCOPE)}</Text><Text style={s.code}>{JSON.stringify(exportData,null,2)}</Text></View>:null}
        <Text style={s.section}>Pedido de eliminação</Text>
        <Text style={s.body}>O pedido aceite permanece PENDING enquanto a revogação externa de identidade, sessões, dispositivos ou faturação não estiver provada. Isto não afirma eliminação concluída.</Text>
        <Pressable disabled={loading} onPress={refreshStatus} style={s.secondary}><Text style={s.secondaryText}>Atualizar estado</Text></Pressable>
        <Text style={s.label}>Estado: {String(status?.status||status?.deletion_status||'UNKNOWN')}</Text>
        <Text style={s.body}>Para pedir eliminação, escreve exatamente:</Text><Text style={s.codeInline}>{CONFIRMATION}</Text>
        <TextInput value={confirmation} onChangeText={setConfirmation} autoCapitalize="characters" placeholder="confirmation" placeholderTextColor="#8290aa" style={s.input}/>
        <Pressable disabled={loading||confirmation!==CONFIRMATION} onPress={requestDeletion} style={[s.destructive,(loading||confirmation!==CONFIRMATION)&&s.disabled]}><Text style={s.destructiveText}>Pedir eliminação</Text></Pressable>
        {loading?<View style={s.loading}><ActivityIndicator/><Text style={s.body}>A carregar…</Text></View>:null}
        {error?<Text accessibilityRole="alert" style={s.error}>Não foi possível concluir: {error}</Text>:null}
      </ScrollView></View></View>
    </Modal>
  </>;
}

const s=StyleSheet.create({trigger:{position:'absolute',right:14,bottom:70,zIndex:50,backgroundColor:'#10182B',borderColor:'#253553',borderWidth:1,borderRadius:999,paddingHorizontal:12,paddingVertical:9},triggerText:{color:'#9DB7FF',fontSize:11,fontWeight:'800'},backdrop:{flex:1,backgroundColor:'rgba(0,0,0,0.65)',justifyContent:'flex-end'},panel:{maxHeight:'86%',backgroundColor:'#0B1220',borderTopLeftRadius:20,borderTopRightRadius:20,borderWidth:1,borderColor:'#253553'},content:{padding:20,paddingBottom:34},row:{flexDirection:'row',justifyContent:'space-between',alignItems:'center'},title:{color:'#F3F6FF',fontSize:22,fontWeight:'900'},close:{color:'#9DB7FF',fontWeight:'800'},section:{color:'#F3F6FF',fontSize:16,fontWeight:'900',marginTop:24},body:{color:'#A9B4C8',fontSize:12,lineHeight:18,marginTop:10},button:{backgroundColor:'#5E8BFF',borderRadius:10,padding:13,alignItems:'center',marginTop:14},buttonText:{color:'#fff',fontWeight:'900'},secondary:{borderColor:'#5E8BFF',borderWidth:1,borderRadius:10,padding:11,alignItems:'center',marginTop:12},secondaryText:{color:'#9DB7FF',fontWeight:'800'},destructive:{backgroundColor:'#B4233A',borderRadius:10,padding:13,alignItems:'center',marginTop:12},destructiveText:{color:'#fff',fontWeight:'900'},disabled:{opacity:.45},box:{backgroundColor:'#10182B',borderRadius:10,padding:12,marginTop:12},label:{color:'#D7DEEC',fontSize:11,marginTop:10},code:{color:'#C5D0E5',fontFamily:'monospace',fontSize:10,marginTop:8},codeInline:{color:'#FFD66B',fontFamily:'monospace',fontSize:11,marginTop:8},input:{backgroundColor:'#10182B',borderColor:'#253553',borderWidth:1,borderRadius:10,color:'#F3F6FF',padding:12,marginTop:10},loading:{flexDirection:'row',alignItems:'center',gap:8,marginTop:12},error:{color:'#FF8998',fontSize:12,marginTop:12}});
