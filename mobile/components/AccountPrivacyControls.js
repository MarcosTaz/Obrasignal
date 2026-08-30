import React, { useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { api } from '../src/api'

const DELETE_CONFIRMATION = 'DELETE_MY_OBRASIGNAL_DATA'
const EXPORT_COMPLETENESS = 'CURRENT_CANONICAL_SERVER_ACCOUNT_DATA_ONLY'

function stateCopy(state) {
  if (!state || state.state === 'NONE') return 'Não existe um pedido de eliminação em curso.'
  if (state.state === 'PENDING') {
    if (state.product_private_db_deleted === true) return 'Os dados privados do produto foram removidos. A revogação externa de identidade, sessões, dispositivo e reconciliação de faturação continua pendente.'
    return 'O pedido de eliminação está pendente. A remoção dos dados privados do produto ainda não está confirmada.'
  }
  if (state.state === 'FAILED') return 'O pedido anterior falhou de forma fechada. Os dados não são apresentados como eliminados.'
  if (state.state === 'UNKNOWN') return 'O estado final não pode ser provado com a evidência disponível. A conclusão da eliminação não é assumida.'
  if (state.state === 'NOT_FOUND') return 'A conta não foi encontrada no armazenamento do produto.'
  return `Estado da eliminação: ${String(state.state)}`
}

export default function AccountPrivacyControls({ children }) {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState(null)
  const [statusLoading, setStatusLoading] = useState(false)
  const [statusError, setStatusError] = useState('')
  const [exportData, setExportData] = useState(null)
  const [exportLoading, setExportLoading] = useState(false)
  const [exportError, setExportError] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const exportText = useMemo(() => exportData ? JSON.stringify(exportData, null, 2) : '', [exportData])
  const deletionBlocked = status?.state === 'PENDING' || status?.state === 'UNKNOWN' || status?.state === 'NOT_FOUND'

  const refreshStatus = async () => {
    setStatusLoading(true)
    setStatusError('')
    try {
      const next = await api.accountDeletionStatus()
      setStatus(next || null)
    } catch (_) {
      setStatusError('Não foi possível confirmar o estado de eliminação da conta.')
    } finally {
      setStatusLoading(false)
    }
  }

  useEffect(() => {
    if (open) refreshStatus()
  }, [open])

  const prepareExport = async () => {
    setExportLoading(true)
    setExportError('')
    setExportData(null)
    try {
      const payload = await api.accountExport()
      if (!payload || payload.schema_version !== 'account-export.v1') throw new Error('invalid_export_contract')
      setExportData(payload)
    } catch (_) {
      setExportError('Não foi possível preparar a exportação dos dados da conta. Nenhuma exportação é apresentada como completa.')
    } finally {
      setExportLoading(false)
    }
  }

  const requestDeletion = async () => {
    if (deleteLoading || confirmation !== DELETE_CONFIRMATION) return
    setDeleteLoading(true)
    setDeleteError('')
    try {
      const next = await api.requestAccountDeletion(confirmation)
      setStatus(next || null)
      setExportData(null)
      setConfirmation('')
    } catch (_) {
      setDeleteError('Não foi possível concluir o pedido de eliminação. O ObraSignal não assume que os dados foram eliminados.')
      await refreshStatus()
    } finally {
      setDeleteLoading(false)
    }
  }

  return <View style={styles.shell}>
    {children}
    <Pressable accessibilityRole="button" accessibilityLabel="Conta e privacidade" onPress={() => setOpen(true)} style={styles.launcher}>
      <Text style={styles.launcherText}>Privacidade</Text>
    </Pressable>
    <Modal visible={open} animationType="slide" transparent={false} onRequestClose={() => setOpen(false)}>
      <View style={styles.modal}>
        <View style={styles.header}>
          <View style={styles.headerCopy}>
            <Text style={styles.title}>Conta e privacidade</Text>
            <Text style={styles.muted}>Controlos autenticados para os dados privados da tua conta ObraSignal.</Text>
          </View>
          <Pressable accessibilityRole="button" onPress={() => setOpen(false)} style={styles.close}><Text style={styles.closeText}>Fechar</Text></Pressable>
        </View>
        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.card}>
            <Text style={styles.heading}>Estado de eliminação</Text>
            {statusLoading ? <View style={styles.loading}><ActivityIndicator color="#5E8BFF"/><Text style={styles.muted}>A carregar o estado da conta…</Text></View> : <Text style={styles.body}>{stateCopy(status)}</Text>}
            {statusError ? <Text accessibilityRole="alert" style={styles.error}>{statusError}</Text> : null}
            <Pressable disabled={statusLoading} onPress={refreshStatus} style={styles.secondary}><Text style={styles.secondaryText}>Atualizar estado</Text></Pressable>
          </View>

          <View style={styles.card}>
            <Text style={styles.heading}>Exportar os meus dados</Text>
            <Text style={styles.body}>A exportação inclui apenas os dados canónicos atuais do servidor pertencentes à conta. Não inclui dados públicos partilhados de contratação, identidade do fornecedor de autenticação, registos-fonte do fornecedor de faturação nem cache privada local do dispositivo.</Text>
            <Text style={styles.scope}>Escopo esperado: {EXPORT_COMPLETENESS}</Text>
            <Pressable disabled={exportLoading || deletionBlocked} onPress={prepareExport} style={[styles.primary,(exportLoading || deletionBlocked)&&styles.disabled]}><Text style={styles.primaryText}>{exportLoading?'A preparar…':'Exportar os meus dados'}</Text></Pressable>
            {exportError ? <Text accessibilityRole="alert" style={styles.error}>{exportError}</Text> : null}
            {exportData ? <View style={styles.exportBox}>
              <Text style={styles.success}>Exportação preparada · {exportData.schema_version}</Text>
              <Text style={styles.muted}>O conteúdo é apresentado abaixo para consulta e cópia. Este build não afirma que criou um ficheiro no dispositivo.</Text>
              <Text selectable style={styles.exportText}>{exportText}</Text>
            </View> : null}
          </View>

          <View style={[styles.card,styles.dangerCard]}>
            <Text style={styles.dangerHeading}>Eliminar dados privados da conta</Text>
            <Text style={styles.body}>Esta ação elimina os dados privados canónicos do produto quando as pré-condições são provadas. Não elimina os dados públicos de contratação. Mesmo após a limpeza do produto, a revogação externa de identidade, sessões, dispositivo e reconciliação de faturação pode continuar pendente.</Text>
            <Text style={styles.warning}>Para pedir a eliminação, escreve exatamente:</Text>
            <Text selectable style={styles.confirmation}>{DELETE_CONFIRMATION}</Text>
            <TextInput
              accessibilityLabel="Confirmação de eliminação"
              value={confirmation}
              onChangeText={setConfirmation}
              autoCapitalize="characters"
              autoCorrect={false}
              placeholder="Escreve a confirmação exata"
              placeholderTextColor="#9BA8C0"
              style={styles.input}
            />
            <Pressable disabled={deleteLoading || deletionBlocked || confirmation !== DELETE_CONFIRMATION} onPress={requestDeletion} style={[styles.deleteButton,(deleteLoading || deletionBlocked || confirmation !== DELETE_CONFIRMATION)&&styles.disabled]}><Text style={styles.deleteText}>{deleteLoading?'A processar…':'Pedir eliminação dos dados privados'}</Text></Pressable>
            {deleteError ? <Text accessibilityRole="alert" style={styles.error}>{deleteError}</Text> : null}
            {status?.state === 'PENDING' ? <Text style={styles.pending}>PENDING — a conta não é apresentada como totalmente eliminada enquanto a revogação externa não estiver provada.</Text> : null}
          </View>
        </ScrollView>
      </View>
    </Modal>
  </View>
}

const styles = StyleSheet.create({
  shell:{flex:1},launcher:{position:'absolute',right:14,bottom:68,minHeight:38,paddingHorizontal:12,paddingVertical:9,borderRadius:19,borderWidth:1,borderColor:'#42597D',backgroundColor:'#10182B',zIndex:100},launcherText:{color:'#C8D3E8',fontSize:10,fontWeight:'900'},modal:{flex:1,backgroundColor:'#070C18'},header:{paddingTop:20,paddingHorizontal:18,paddingBottom:14,borderBottomWidth:1,borderBottomColor:'#253553',flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:12},headerCopy:{flex:1},title:{color:'#F3F6FF',fontSize:24,fontWeight:'900'},muted:{color:'#9BA8C0',fontSize:11,lineHeight:16},close:{paddingHorizontal:12,paddingVertical:9,borderRadius:10,borderWidth:1,borderColor:'#253553'},closeText:{color:'#F3F6FF',fontSize:11,fontWeight:'800'},content:{padding:16,paddingBottom:48,gap:14},card:{borderWidth:1,borderColor:'#253553',backgroundColor:'#10182B',borderRadius:14,padding:14},dangerCard:{borderColor:'#7A3A45'},heading:{color:'#F3F6FF',fontSize:15,fontWeight:'900'},dangerHeading:{color:'#FF8998',fontSize:15,fontWeight:'900'},body:{color:'#C8D3E8',fontSize:12,lineHeight:18,marginTop:7},scope:{color:'#9BA8C0',fontSize:9,marginTop:8},loading:{flexDirection:'row',alignItems:'center',gap:8,marginTop:10},primary:{marginTop:12,minHeight:44,borderRadius:10,backgroundColor:'#5E8BFF',alignItems:'center',justifyContent:'center',paddingHorizontal:12},primaryText:{color:'#FFFFFF',fontWeight:'900',fontSize:12},secondary:{alignSelf:'flex-start',marginTop:10,paddingVertical:8,paddingHorizontal:11,borderWidth:1,borderColor:'#5E8BFF',borderRadius:9},secondaryText:{color:'#5E8BFF',fontSize:11,fontWeight:'800'},disabled:{opacity:.45},error:{color:'#FF8998',fontSize:11,lineHeight:16,marginTop:9},success:{color:'#6FE39A',fontSize:11,fontWeight:'900'},exportBox:{marginTop:12,borderTopWidth:1,borderTopColor:'#253553',paddingTop:12},exportText:{marginTop:10,color:'#C8D3E8',fontFamily:'monospace',fontSize:9,lineHeight:13},warning:{color:'#FFD66B',fontSize:11,fontWeight:'800',marginTop:12},confirmation:{color:'#F3F6FF',fontFamily:'monospace',fontSize:11,marginTop:6},input:{marginTop:10,borderWidth:1,borderColor:'#7A3A45',borderRadius:10,color:'#F3F6FF',backgroundColor:'#070C18',padding:12},deleteButton:{marginTop:11,minHeight:44,borderRadius:10,borderWidth:1,borderColor:'#FF8998',alignItems:'center',justifyContent:'center',paddingHorizontal:12},deleteText:{color:'#FF8998',fontSize:12,fontWeight:'900'},pending:{color:'#FFD66B',fontSize:10,lineHeight:15,marginTop:10}
})
