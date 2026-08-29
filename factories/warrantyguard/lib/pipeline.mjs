import {parseCsv,normalizeDebitRow} from './csv.mjs';
import {analyzeDebit,findDuplicates,findPotentialDuplicates,summarize,createDisputePackage} from './engine.mjs';
import {selectContract} from './contracts.mjs';
export function analyzeCsv({tenantId,csv,contracts=[],evidence=[],requireContext=true}){
  if(!tenantId)throw new Error('TENANT_REQUIRED');
  if(!Array.isArray(contracts)||contracts.length>100)throw new Error('CONTRACT_LIMIT');
  if(!Array.isArray(evidence)||evidence.length>5000)throw new Error('EVIDENCE_LIMIT');
  const rows=parseCsv(csv).map(r=>normalizeDebitRow(r,tenantId));
  const dup=findDuplicates(rows); const dupIds=new Set(dup.map(x=>x.duplicateId));
  const results=[],packages=[];
  for(const d0 of rows){const d={...d0,duplicateConfirmed:d0.duplicateConfirmed===true||dupIds.has(d0.id)};const a=analyzeDebit(d,{contracts,evidence,requireContext});results.push({debit:d,analysis:a});const c=selectContract(contracts,d);const linked=evidence.filter(e=>e.debitId===d.id);const p=createDisputePackage(d,a,{contract:c.ok?c.contract:null,evidence:linked});if(p)packages.push(p);}
  return {tenantId,results,packages,duplicates:dup,potentialDuplicates:findPotentialDuplicates(rows),summary:summarize(results.map(x=>x.analysis))};
}
