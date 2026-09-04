import {strictBool,normalizeAmount,parseIsoDate,validCurrency,requiredText} from './utils.mjs';
export const PILOT_MAX_ROWS=500;
export const MAX_CSV_BYTES=2_000_000;
export function parseCsv(text){
  if(typeof text!=='string')throw new Error('CSV_REQUIRED');
  if(Buffer.byteLength(text,'utf8')>MAX_CSV_BYTES)throw new Error('CSV_TOO_LARGE');
  const rows=[];let row=[],cell='',q=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(q){if(c==='"'&&text[i+1]==='"'){cell+='"';i++;}else if(c==='"')q=false;else cell+=c;}
    else if(c==='"')q=true; else if(c===','){row.push(cell);cell='';} else if(c==='\n'){row.push(cell.replace(/\r$/,''));rows.push(row);row=[];cell='';} else cell+=c;
  }
  if(q)throw new Error('CSV_UNCLOSED_QUOTE');
  if(cell.length||row.length){row.push(cell.replace(/\r$/,''));rows.push(row);}
  const nonempty=rows.filter(r=>r.some(c=>String(c).trim()!=='')); if(nonempty.length<2)throw new Error('CSV_NO_DATA');
  const header=nonempty[0].map(x=>x.trim()); if(new Set(header).size!==header.length)throw new Error('CSV_DUPLICATE_HEADER');
  const out=nonempty.slice(1).map((r,idx)=>{if(r.length!==header.length)throw new Error(`CSV_COLUMN_COUNT_ROW_${idx+2}`);return Object.fromEntries(header.map((h,i)=>[h,r[i]]));});
  if(out.length>PILOT_MAX_ROWS)throw new Error('PILOT_ROW_LIMIT'); return out;
}
export function normalizeDebitRow(r,tenantId){
  const rowTenant=requiredText(r.tenantId,'tenantId'); if(rowTenant!==tenantId)throw new Error('TENANT_MISMATCH');
  const amount=normalizeAmount(r.amount); const currency=requiredText(r.currency,'currency').toUpperCase(); if(!validCurrency(currency))throw new Error('INVALID_CURRENCY');
  return {tenantId:rowTenant,id:requiredText(r.id,'id'),customer:requiredText(r.customer||r.customerId,'customer'),amount,currency,failureDate:parseIsoDate(requiredText(r.failureDate,'failureDate')),part:(r.part||'').trim()||null,program:(r.program||'').trim()||null,asset:(r.asset||'').trim()||null,caseId:(r.caseId||'').trim()||null,invoice:(r.invoice||'').trim()||null,repairDate:r.repairDate?parseIsoDate(r.repairDate):null,rootCauseKnown:strictBool(r.rootCauseKnown),responsibility:(r.responsibility||'').trim().toUpperCase()||null,responsibilityShare:r.responsibilityShare===''||r.responsibilityShare==null?null:Number(r.responsibilityShare),warrantyEligible:strictBool(r.warrantyEligible),costEligible:strictBool(r.costEligible),wrongPart:strictBool(r.wrongPart),wrongProgram:strictBool(r.wrongProgram),wrongAsset:strictBool(r.wrongAsset),wrongCustomer:strictBool(r.wrongCustomer),duplicateConfirmed:strictBool(r.duplicateConfirmed),currencyMismatch:strictBool(r.currencyMismatch),evidenceContradictory:strictBool(r.evidenceContradictory),ineligibleCost:normalizeAmount(r.ineligibleCost,{allowNull:true}),priorCredit:normalizeAmount(r.priorCredit,{allowNull:true}),priorPayment:normalizeAmount(r.priorPayment,{allowNull:true}),costCap:normalizeAmount(r.costCap,{allowNull:true})};
}
