import test from 'node:test';import assert from 'node:assert/strict';
import {makeAdapterProfile,normalizeWithAdapter} from '../lib/adapters.mjs';
const profile=()=>makeAdapterProfile({id:'oem-alpha',version:'1.0',customer:'OEM-ALPHA',headerMap:{TENANT:'tenantId',CLAIM_ID:'id',VALUE:'amount',CCY:'currency',FAIL_DATE:'failureDate',PART_NO:'part'}});

test('adapter profile is hashed and versioned',()=>{const p=profile();assert.equal(p.id,'oem-alpha');assert.equal(p.version,'1.0');assert.equal(p.profileHash.length,64);});
test('adapter rejects unknown canonical target',()=>assert.throws(()=>makeAdapterProfile({id:'x',version:'1',customer:'c',headerMap:{A:'nope'}}),/ADAPTER_MAPPING_INVALID/));
test('adapter rejects duplicate canonical target',()=>assert.throws(()=>makeAdapterProfile({id:'x',version:'1',customer:'c',headerMap:{A:'id',B:'id',C:'amount',D:'currency',E:'failureDate',F:'tenantId'}}),/ADAPTER_DUPLICATE_TARGET_id/));
test('adapter requires core fields',()=>assert.throws(()=>makeAdapterProfile({id:'x',version:'1',customer:'c',headerMap:{A:'id'}}),/ADAPTER_REQUIRED_MAPPING_MISSING/));
test('adapter normalizes OEM headers and injects customer',()=>{const p=profile();const csv='TENANT,CLAIM_ID,VALUE,CCY,FAIL_DATE,PART_NO\nt1,C1,1200,EUR,2026-08-01,P-1';const r=normalizeWithAdapter(csv,p,{tenantId:'t1'});assert.equal(r.rows[0].customer,'OEM-ALPHA');assert.equal(r.rows[0].id,'C1');assert.equal(r.quality.status,'PASS');});
test('adapter reports unknown source headers without discarding mapped data',()=>{const p=profile();const csv='TENANT,CLAIM_ID,VALUE,CCY,FAIL_DATE,PART_NO,NEW_FIELD\nt1,C1,1200,EUR,2026-08-01,P-1,x';const r=normalizeWithAdapter(csv,p,{tenantId:'t1'});assert.deepEqual(r.quality.unknownHeaders,['NEW_FIELD']);assert.equal(r.quality.status,'REVIEW_REQUIRED');});
test('adapter fails closed on tenant mismatch',()=>{const p=profile();const csv='TENANT,CLAIM_ID,VALUE,CCY,FAIL_DATE,PART_NO\nevil,C1,1200,EUR,2026-08-01,P-1';assert.throws(()=>normalizeWithAdapter(csv,p,{tenantId:'t1'}),/ADAPTER_TENANT_MISMATCH_ROW_2/);});
test('adapter constants cannot collide with mapped fields',()=>assert.throws(()=>makeAdapterProfile({id:'x',version:'1',customer:'c',headerMap:{A:'id',B:'amount',C:'currency',D:'failureDate',E:'tenantId'},constants:{id:'fixed'}}),/ADAPTER_CONSTANT_COLLISION_id/));
