import assert from 'node:assert/strict';
import {analyzeCsv} from '../lib/pipeline.mjs';
const csv='tenantId,id,customer,amount,currency,failureDate,part,program,asset,rootCauseKnown,responsibility,warrantyEligible,costEligible\nt,D,OEM,1,EUR,2026-01-01,P,PR,A,true,SUPPLIER,true,true';
assert.throws(()=>analyzeCsv({tenantId:'t',csv,contracts:Array.from({length:101},()=>({})),evidence:[]}),/CONTRACT_LIMIT/);
assert.throws(()=>analyzeCsv({tenantId:'t',csv,contracts:[],evidence:Array.from({length:5001},()=>({}))}),/EVIDENCE_LIMIT/);
console.log(JSON.stringify({ok:true,contractLimit:100,evidenceLimit:5000,csvRows:500,csvBytes:2000000,httpBodyBytes:2000000}));
