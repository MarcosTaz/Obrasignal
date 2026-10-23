import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { api } from '../src/api';
import { storage } from '../src/storage';
import { supabase } from '../lib/supabase';
import { BRAND } from '../src/brand-palette.mjs';

const DELETE_CONFIRMATION = 'DELETE_MY_OBRASIGNAL_DATA';
const EXPORT_COMPLETENESS = 'CURRENT_CANONICAL_SERVER_ACCOUNT_DATA_ONLY';
const C = {bg:'#06111D',panel:'#0B1C2D',panel2:'#10283D',line:'#2B4760',text:'#F4F8FE',muted:'#A4BFD5',blue:'#78BEFB',green:'#9AE8C7',amber:'#F0C78B',red:'#FFB0B8'};
const sleep=(ms)=>new Promise(resolve=>setTimeout(resolve,ms));

function stateCopy(state) {
  if (!state || state.state === 'NONE') return 'Não existe um pedido de eliminação em curso.';
  if (state.state === 'PENDING') {
    if (state.product_private_db_deleted === true) return 'Os dados privados canónicos do produto foram removidos. A revogação externa de identidade, sessões, dispositivo e faturação continua pendente e não é apresentada como concluída.';
    return 'O pedido de eliminação está pendente. A remoção dos dados privados do produto ainda não está confirmada.';
  }
  if (state.state === 'FAILED') return 'O pedido anterior falhou. O acesso privado permanece bloqueado até um estado seguro ser novamente confirmado.';
  if (state.state === 'UNKNOWN') return 'O estado final não pode ser provado. O acesso privado permanece bloqueado; o ObraSignal não assume que a eliminação terminou.';
  if (state.state === 'NOT_FOUND') return 'A conta não foi encontrada no armazenamento canónico do produto.';
  return `Estado da eliminação: ${String(state.state)}`;
}

export default function AccountPrivacyControls({ children }) {
  const [open,setOpen]=useState(false);
  const [ready,setReady]=useState(false);
  const [privacyLocked,setPrivacyLocked]=useState(true);
  const [status,setStatus]=useState(null);
  const [statusLoading,setStatusLoading]=useState(false);
  const [statusError,setStatusError]=useState('');
  const [exportData,setExportData]=useState(null);
  const [exportLoading,setExportLoading]=useState(false);
  const [exportError,setExportError]=useState('');
  const [confirmation,setConfirmation]=useState('');
  const [deleteLoading,setDeleteLoading]=useState(false);
  const [deleteError,setDeleteError]=useState('');

  const exportText=useMemo(()=>exportData?JSON.stringify(exportData,null,2):'',[exportData]);
  const deletionBlocked=status?.state==='PENDING'||status?.state==='NOT_FOUND';

  const refreshStatus=async({initial=false}={})=>{
    setStatusLoading(true);setStatusError('');
    if(initial){setReady(false);setPrivacyLocked(true);}
    const attempts=initial?3:1;
    try{
      let lastError=null;
      for(let attempt=1;attempt<=attempts;attempt+=1){
        try{
          const next=await api.accountDeletionStatus();
          if(!next||typeof next.state!=='string')throw new Error('invalid_deletion_state_contract');
          setStatus(next);
          const shouldLock=next.state!=='NONE';
          setPrivacyLocked(shouldLock);
          setReady(true);
          return next;
        }catch(error){
          lastError=error;
          if(attempt<attempts)await sleep(500*attempt);
        }
      }
      throw lastError||new Error('account_deletion_status_unavailable');
    }catch(_){
      setStatusError(initial?'Não foi possível confirmar o estado privado da conta.':'Não foi possível atualizar o estado de eliminação.');
      if(initial){setReady(false);setPrivacyLocked(true);}
      return null;
    }finally{setStatusLoading(false);}
  };

  useEffect(()=>{refreshStatus({initial:true});},[]);
  useEffect(()=>{if(open&&ready)refreshStatus();},[open]);

  const prepareExport=async()=>{
    setExportLoading(true);setExportError('');setExportData(null);
    try{
      const payload=await api.accountExport();
      if(!payload||payload.schema_version!=='account-export.v1')throw new Error('invalid_export_contract');
      setExportData(payload);
    }catch(_){setExportError('Não foi possível preparar uma exportação completa dos dados canónicos desta conta.');}
    finally{setExportLoading(false);}
  };

  const downloadExport=()=>{
    if(!exportText||Platform.OS!=='web'||typeof document==='undefined'||typeof URL==='undefined')return;
    const blob=new Blob([exportText],{type:'application/json;charset=utf-8'});
    const url=URL.createObjectURL(blob);
    const anchor=document.createElement('a');
    anchor.href=url;
    anchor.download=`obrasignal-account-export-${new Date().toISOString().slice(0,10)}.json`;
    document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
  };

  const requestDeletion=async()=>{
    if(deleteLoading||confirmation!==DELETE_CONFIRMATION)return;
    setDeleteLoading(true);setDeleteError('');setPrivacyLocked(true);
    try{
      const next=await api.requestAccountDeletion(confirmation);
      setStatus(next||null);setExportData(null);setConfirmation('');
      if(next?.product_private_db_deleted===true){
        let localClean=false;
        try{await storage.bindPrivateTenant(null);localClean=true;}catch(_){setDeleteError('Os dados do servidor foram removidos, mas não foi possível confirmar a limpeza da cache privada neste dispositivo.');}
        try{
          const {error}=await supabase.auth.signOut();
          if(error)throw error;
        }catch(_){if(localClean)setDeleteError('A cache privada foi limpa, mas não foi possível confirmar o fim da sessão neste dispositivo.');}
      }else if(next?.state==='NONE'){
        setPrivacyLocked(false);
      }
    }catch(_){
      setDeleteError('Não foi possível provar o resultado do pedido. O acesso privado permanece bloqueado até uma leitura autoritativa do estado.');
      await refreshStatus();
    }finally{setDeleteLoading(false);}
  };

  if(!ready){
    return <View style={styles.gate}><Text style={styles.title}>Account & privacy</Text>{statusLoading?<><ActivityIndicator color={C.blue}/><Text style={styles.body}>A confirmar o estado privado da conta…</Text></>:<><Text accessibilityRole="alert" style={styles.error}>{statusError||'Não foi possível confirmar o estado privado da conta.'}</Text><Pressable onPress={()=>refreshStatus({initial:true})} style={styles.secondary}><Text style={styles.secondaryText}>Tentar novamente</Text></Pressable></>}</View>;
  }

  return <View style={styles.shell}>
    <View style={styles.privacyBar}><Text style={styles.privacyHint}>{privacyLocked?'Private data locked':'Account & privacy'}</Text><Pressable accessibilityRole="button" accessibilityLabel="Account & privacy" onPress={()=>setOpen(true)} style={styles.launcher}><Text style={styles.launcherText}>Account & privacy</Text><Text style={styles.arrow}>›</Text></Pressable></View>
    {privacyLocked?<View style={styles.gate}><Text style={styles.title}>Conta em ciclo de eliminação</Text><Text style={styles.body}>{stateCopy(status)}</Text><Pressable onPress={()=>setOpen(true)} style={styles.secondary}><Text style={styles.secondaryText}>Ver estado e opções</Text></Pressable></View>:children}

    <Modal visible={open} animationType="slide" transparent={false} onRequestClose={()=>!deleteLoading&&setOpen(false)}>
      <View style={styles.modal}><View style={styles.header}><View style={styles.headerCopy}><Text style={styles.title}>Account & privacy</Text><Text style={styles.muted}>Controlos autenticados para os dados privados da tua conta ObraSignal.</Text></View><Pressable disabled={deleteLoading} onPress={()=>setOpen(false)} style={styles.close}><Text style={styles.closeText}>Fechar</Text></Pressable></View>
        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.card}><Text style={styles.heading}>Estado da conta</Text>{statusLoading?<View style={styles.loading}><ActivityIndicator color={C.blue}/><Text style={styles.muted}>A atualizar…</Text></View>:<Text style={styles.body}>{stateCopy(status)}</Text>}{statusError?<Text accessibilityRole="alert" style={styles.error}>{statusError}</Text>:null}<Pressable disabled={statusLoading} onPress={()=>refreshStatus()} style={styles.secondary}><Text style={styles.secondaryText}>Atualizar estado</Text></Pressable></View>

          <View style={styles.card}><Text style={styles.heading}>Exportar os meus dados</Text><Text style={styles.body}>Inclui os dados canónicos atuais do servidor pertencentes à conta. Não inclui os concursos públicos partilhados, dados do fornecedor de identidade, registos-fonte do fornecedor de faturação nem cache privada deste dispositivo.</Text><Text style={styles.scope}>Escopo: {EXPORT_COMPLETENESS}</Text><Pressable disabled={exportLoading||deletionBlocked} onPress={prepareExport} style={[styles.primary,(exportLoading||deletionBlocked)&&styles.disabled]}><Text style={styles.primaryText}>{exportLoading?'A preparar…':'Preparar exportação'}</Text></Pressable>{exportError?<Text accessibilityRole="alert" style={styles.error}>{exportError}</Text>:null}{exportData?<View style={styles.exportBox}><Text style={styles.success}>Exportação preparada · {exportData.schema_version}</Text>{Platform.OS==='web'?<Pressable onPress={downloadExport} style={styles.download}><Text style={styles.downloadText}>Descarregar JSON</Text></Pressable>:<Text style={styles.muted}>O conteúdo pode ser selecionado e copiado abaixo.</Text>}<ScrollView style={styles.exportScroll}><Text selectable style={styles.exportText}>{exportText}</Text></ScrollView></View>:null}</View>

          <View style={[styles.card,styles.dangerCard]}><Text style={styles.dangerHeading}>Eliminar dados privados da conta</Text><Text style={styles.body}>Remove os dados privados canónicos mantidos pelo produto e bloqueia a conta contra reativação acidental. A revogação de identidade/sessões externas e dos sistemas de faturação não é declarada concluída sem prova desses fornecedores.</Text>{status?.state==='FAILED'||status?.state==='UNKNOWN'?<Text style={styles.warning}>O estado anterior não é conclusivo. Repetir o pedido é permitido enquanto o acesso privado permanece bloqueado.</Text>:null}<Text style={styles.warning}>Para confirmar, escreve exatamente:</Text><Text selectable style={styles.confirmation}>{DELETE_CONFIRMATION}</Text><TextInput accessibilityLabel="Confirmação de eliminação" value={confirmation} onChangeText={setConfirmation} autoCapitalize="characters" autoCorrect={false} placeholder="Escreve a confirmação exata" placeholderTextColor={C.muted} style={styles.input}/><Pressable disabled={deleteLoading||deletionBlocked||confirmation!==DELETE_CONFIRMATION} onPress={requestDeletion} style={[styles.deleteButton,(deleteLoading||deletionBlocked||confirmation!==DELETE_CONFIRMATION)&&styles.disabled]}><Text style={styles.deleteText}>{deleteLoading?'A processar…':status?.state==='FAILED'||status?.state==='UNKNOWN'?'Repetir pedido de eliminação':'Eliminar dados privados'}</Text></Pressable>{deleteError?<Text accessibilityRole="alert" style={styles.error}>{deleteError}</Text>:null}{status?.state==='PENDING'?<Text style={styles.pending}>PENDENTE — a conta não é apresentada como totalmente eliminada enquanto as fronteiras externas não estiverem provadas.</Text>:null}</View>
        </ScrollView>
      </View>
    </Modal>
  </View>;
}

const styles=StyleSheet.create({
  shell:{flex:1,backgroundColor:C.bg},privacyBar:{minHeight:42,paddingHorizontal:18,paddingVertical:7,backgroundColor:C.bg,borderBottomWidth:1,borderBottomColor:C.line,flexDirection:'row',alignItems:'center',justifyContent:'flex-end',gap:12},privacyHint:{color:C.muted,fontSize:9,fontWeight:'700'},launcher:{minHeight:28,flexDirection:'row',alignItems:'center',gap:7,paddingHorizontal:10,borderRadius:999,borderWidth:1,borderColor:C.line,backgroundColor:C.panel2},launcherText:{color:C.text,fontSize:9,fontWeight:'800'},arrow:{color:C.text,fontSize:16},gate:{flex:1,minHeight:300,alignItems:'center',justifyContent:'center',gap:12,padding:28,backgroundColor:C.bg},modal:{flex:1,backgroundColor:C.bg},header:{paddingTop:20,paddingHorizontal:20,paddingBottom:15,borderBottomWidth:1,borderBottomColor:C.line,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:14},headerCopy:{flex:1},title:{color:C.text,fontSize:24,fontWeight:'900'},muted:{color:C.muted,fontSize:11,lineHeight:17},close:{paddingHorizontal:12,paddingVertical:9,borderRadius:9,borderWidth:1,borderColor:C.line},closeText:{color:C.text,fontSize:11,fontWeight:'800'},content:{width:'100%',maxWidth:860,alignSelf:'center',padding:18,paddingBottom:56,gap:14},card:{borderWidth:1,borderColor:C.line,backgroundColor:C.panel,borderRadius:14,padding:16},dangerCard:{borderColor:'#A33131'},heading:{color:C.text,fontSize:15,fontWeight:'900'},dangerHeading:{color:'#A33131',fontSize:15,fontWeight:'900'},body:{color:C.text,fontSize:12,lineHeight:19,marginTop:7,maxWidth:760},scope:{color:C.muted,fontSize:9,marginTop:9},loading:{flexDirection:'row',alignItems:'center',gap:8,marginTop:10},primary:{marginTop:14,minHeight:46,borderRadius:10,backgroundColor:C.text,alignItems:'center',justifyContent:'center',paddingHorizontal:14},primaryText:{color:C.bg,fontWeight:'900',fontSize:12},secondary:{alignSelf:'center',marginTop:11,paddingVertical:9,paddingHorizontal:12,borderWidth:1,borderColor:BRAND.slate,borderRadius:9},secondaryText:{color:C.text,fontSize:11,fontWeight:'800'},disabled:{opacity:.45},error:{color:C.red,fontSize:11,lineHeight:16,marginTop:9,textAlign:'center'},success:{color:C.green,fontSize:11,fontWeight:'900'},exportBox:{marginTop:13,borderTopWidth:1,borderTopColor:C.line,paddingTop:13},download:{alignSelf:'flex-start',marginTop:10,paddingHorizontal:12,paddingVertical:8,borderRadius:9,backgroundColor:C.panel2},downloadText:{color:C.text,fontSize:11,fontWeight:'900'},exportScroll:{maxHeight:280,marginTop:10,borderWidth:1,borderColor:C.line,borderRadius:9,backgroundColor:C.bg,padding:10},exportText:{color:C.text,fontFamily:'monospace',fontSize:9,lineHeight:14},warning:{color:C.amber,fontSize:11,fontWeight:'800',marginTop:12,lineHeight:17},confirmation:{color:C.text,fontFamily:'monospace',fontSize:11,marginTop:7},input:{marginTop:10,borderWidth:1,borderColor:'#A33131',borderRadius:10,color:C.text,backgroundColor:C.bg,padding:12},deleteButton:{marginTop:12,minHeight:46,borderRadius:10,borderWidth:1,borderColor:C.red,alignItems:'center',justifyContent:'center',paddingHorizontal:12},deleteText:{color:'#A33131',fontSize:12,fontWeight:'900'},pending:{color:C.amber,fontSize:10,lineHeight:15,marginTop:11}
});
