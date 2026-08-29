import {makeContract} from '../lib/contracts.mjs';
import {makeEvidence} from '../lib/evidence.mjs';
const companies=[
 ['Alpha Automotive','alpha-automotive'],['Nova Electronics','nova-electronics'],['Titan Industrial Systems','titan-industrial-systems'],['Precision Motion','precision-motion'],['Legacy Components','legacy-components'],['Redteam Supplier','redteam-supplier']
];
const patterns=[
 {state:'SUPPORTED',extra:{responsibility:'SUPPLIER'}},{state:'DISPUTABLE',extra:{responsibility:'CUSTOMER'}},{state:'PARTIALLY_SUPPORTED',extra:{responsibility:'SHARED',responsibilityShare:.4}},{state:'UNKNOWN',extra:{responsibility:'SUPPLIER',part:null},unknown:true},{state:'DISPUTABLE',extra:{responsibility:'SUPPLIER',warrantyEligible:false}},{state:'SUPPORTED',extra:{responsibility:'SUPPLIER'}},{state:'UNKNOWN',extra:{responsibility:'SUPPLIER',rootCauseKnown:false},unknown:true},{state:'DISPUTABLE',extra:{responsibility:'SUPPLIER',wrongPart:true}},{state:'PARTIALLY_SUPPORTED',extra:{responsibility:'SUPPLIER',costCap:2500}},{state:'UNKNOWN',extra:{responsibility:'SUPPLIER',program:null},unknown:true},{state:'DISPUTABLE',extra:{responsibility:'THIRD_PARTY'}},{state:'SUPPORTED',extra:{responsibility:'SUPPLIER'}},{state:'UNKNOWN',extra:{responsibility:'SUPPLIER',asset:null},unknown:true},{state:'DISPUTABLE',extra:{responsibility:'NO_FAULT_FOUND'}},{state:'DISPUTABLE',extra:{responsibility:'SUPPLIER',costEligible:false}},{state:'DISPUTABLE',extra:{responsibility:'SUPPLIER',duplicateConfirmed:true}},{state:'PARTIALLY_SUPPORTED',extra:{responsibility:'SUPPLIER',ineligibleCost:3000}},{state:'SUPPORTED',extra:{responsibility:'SUPPLIER'}}
];
export function buildPortfolio(){
 const out=[];
 for(let i=0;i<18;i++){
  const [company,tenantId]=companies[Math.floor(i/3)], id=`${tenantId.slice(0,2).toUpperCase()}-${i%3+1}`, customer='OEM-1';
  const p=patterns[i];
  const debit={tenantId,id,customer,amount:10000,currency:'EUR',failureDate:'2026-06-15',part:'PART-1',program:'PROGRAM-1',asset:`ASSET-${i+1}`,rootCauseKnown:true,warrantyEligible:true,costEligible:true,...p.extra};
  const contract=makeContract({id:`C-${tenantId}`,tenantId,customer,effectiveFrom:'2026-01-01',effectiveTo:'2027-01-01',rules:{warrantyEligible:true,costEligible:true,...(debit.responsibility==='NO_FAULT_FOUND'?{noFaultFoundSupplierLiable:false}:{})},sourceText:`contract ${tenantId}`});
  const claims=['WARRANTY','COST_ELIGIBILITY'];if(debit.rootCauseKnown)claims.push('ROOT_CAUSE');if(debit.responsibility)claims.push('RESPONSIBILITY');if(debit.wrongPart||debit.wrongProgram||debit.wrongAsset||debit.wrongCustomer)claims.push('MAPPING');if(debit.duplicateConfirmed)claims.push('DUPLICATE');if(debit.priorCredit)claims.push('PRIOR_CREDIT');
  const evidence=makeEvidence({id:`E-${id}`,tenantId,debitId:id,claims});
  out.push({company,tenantId,debit,contracts:[contract],evidence:[evidence],expectedState:p.state});
 }
 return out;
}
