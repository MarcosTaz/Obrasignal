import {requiredText} from './utils.mjs';
export const COMPLETION_GATES=['A_DOCUMENTS','B_EXTRACTION','C_WARRANTY_LOGIC','D_EVIDENCE','E_FALSE_CLAIM_CONTROL','F_CALCULATIONS','G_CASE','H_PRODUCT','I_SECURITY','J_BILLING','K_SUPPORT','L_OPERATIONS','M_PILOT','N_VALUE','O_COMMERCIAL','P_RETENTION','Q_ECONOMICS','R_QUALITY'];
const PASS_STATES=new Set(['PASS','PROVEN','SATISFIED']);
export function evaluateCompletion({scope='ASSISTED_LOCAL',gates={}}={}){
  if(!['ASSISTED_LOCAL','PUBLIC_MULTIUSER'].includes(scope))throw new Error('INVALID_COMPLETION_SCOPE');
  const normalized={},failed=[];
  for(const id of COMPLETION_GATES){const g=gates[id]||{};const state=requiredText(g.state||'NOT_PROVEN','gateState').toUpperCase();const evidence=Array.isArray(g.evidence)?g.evidence.filter(Boolean):[];const applicable=g.applicable!==false;let satisfied=!applicable||(PASS_STATES.has(state)&&evidence.length>0);
    if(id==='I_SECURITY'&&scope==='PUBLIC_MULTIUSER'&&g.publicMultiuserProven!==true)satisfied=false;
    if(['M_PILOT','N_VALUE','O_COMMERCIAL','P_RETENTION','Q_ECONOMICS'].includes(id)&&g.realEvidence!==true)satisfied=false;
    if(id==='R_QUALITY'&&g.openP0>0)satisfied=false;
    normalized[id]={state,evidence,applicable,satisfied,realEvidence:g.realEvidence===true};if(applicable&&!satisfied)failed.push(id);
  }
  return {scope,gates:normalized,failed,projectComplete:failed.length===0,status:failed.length?'PROJECT_INCOMPLETE':'PROJECT_COMPLETE'};
}
export function assertNoFalseCompletion(result){if(!result||typeof result.projectComplete!=='boolean')throw new Error('INVALID_COMPLETION_RESULT');if(result.projectComplete&&result.failed.length)throw new Error('FALSE_COMPLETION');return true;}
