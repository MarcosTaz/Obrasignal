import http from 'node:http';
import {readFile,writeFile,rename,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {randomUUID,createHash,timingSafeEqual} from 'node:crypto';
import {extractDocuments,reviewExtraction,buildCaseAssessment,buildDossier,dossierMarkdown} from './document_pipeline_v2.mjs';

const DATA_FILE=process.env.GR_CASE_DATA_FILE||new URL('./data/guaranteerelease_cases.json',import.meta.url).pathname;
const PORT=Number(process.env.PORT||8791),MAX_BODY=2*1024*1024;let writeChain=Promise.resolve();
const now=()=>new Date().toISOString(),emptyStore=()=>({version:1,cases:[],audit:[]});
const sha=s=>createHash('sha256').update(String(s)).digest('hex');
function eqHex(a,b){if(!/^[0-9a-f]{64}$/i.test(String(a||''))||!/^[0-9a-f]{64}$/i.test(String(b||'')))return false;return timingSafeEqual(Buffer.from(a,'hex'),Buffer.from(b,'hex'))}
function principals(){try{const x=JSON.parse(process.env.GR_AUTH_PRINCIPALS_JSON||'[]');if(!Array.isArray(x)||!x.length)return[];const ids=new Set(),hs=new Set(),out=[];for(const v of x){if(!v||typeof v!=='object'||typeof v.principalId!=='string'||!v.principalId.trim()||typeof v.tenantId!=='string'||!v.tenantId.trim()||!['operator','reviewer'].includes(v.role)||typeof v.tokenSha256!=='string'||!/^[0-9a-f]{64}$/i.test(v.tokenSha256))return[];const id=v.principalId.trim(),h=v.tokenSha256.toLowerCase();if(ids.has(id)||hs.has(h))return[];ids.add(id);hs.add(h);out.push({principalId:id,tenantId:v.tenantId.trim(),role:v.role,tokenSha256:h})}return out}catch{return[]}}
function auth(req){const h=req.headers.authorization||'',token=h.startsWith('Bearer ')?h.slice(7):'';if(!token)return null;const d=sha(token);for(const p of principals())if(eqHex(p.tokenSha256,d))return{principalId:p.principalId,tenantId:p.tenantId,role:p.role};return null}
async function loadStore(){try{const x=JSON.parse(await readFile(DATA_FILE,'utf8'));if(!Array.isArray(x.cases)||!Array.isArray(x.audit))throw Error('invalid store');return x}catch(e){if(e.code==='ENOENT')return emptyStore();throw e}}
async function persist(s){await mkdir(dirname(DATA_FILE),{recursive:true});const tmp=`${DATA_FILE}.${process.pid}.${Date.now()}.tmp`;await writeFile(tmp,JSON.stringify(s,null,2),{encoding:'utf8',mode:0o600});await rename(tmp,DATA_FILE)}
function enqueue(fn){const n=writeChain.then(fn,fn);writeChain=n.catch(()=>{});return n}
function out(res,status,p){const b=JSON.stringify(p);res.writeHead(status,{'content-type':'application/json; charset=utf-8','content-length':Buffer.byteLength(b),'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'no-referrer'});res.end(b)}
async function body(req){let n=0,a=[];for await(const c of req){n+=c.length;if(n>MAX_BODY)throw Object.assign(Error('body too large'),{status:413});a.push(c)}if(!a.length)return{};try{return JSON.parse(Buffer.concat(a).toString('utf8'))}catch{throw Object.assign(Error('invalid json'),{status:400})}}
const caseIdOk=s=>typeof s==='string'&&/^[A-Za-z0-9._-]{1,120}$/.test(s);
function publicMeta(r){return{caseId:r.caseId,status:r.status,createdAt:r.createdAt,updatedAt:r.updatedAt,submittedByPrincipalId:r.submittedByPrincipalId,documentCount:r.extraction.documents.length,factCount:r.extraction.facts.length,assessment:r.current?.result?.assessment||null}}
function publicCase(r){return{...publicMeta(r),documents:r.extraction.documents.map(d=>({documentId:d.documentId,type:d.type,sourceName:d.sourceName,sha256:d.sha256,sourceSha256:d.sourceSha256,pageCount:d.pages.length,supersedes:d.supersedes})),facts:r.extraction.facts.map(({kind,value,confidence,provenance,factId,reviewStatus,reviewedAt,reviewedByPrincipalId})=>({kind,value,confidence,provenance,factId,reviewStatus,reviewedAt,reviewedByPrincipalId})),duplicateGroups:r.extraction.duplicateGroups,current:r.current}}
function decisionsFrom(r){return Object.fromEntries(r.extraction.facts.map(f=>[f.factId,f.reviewStatus||'PENDING']))}
function recompute(r){const reviewed=reviewExtraction(r.extraction,decisionsFrom(r));const result=buildCaseAssessment(reviewed,{asOf:r.asOf});const dossier=buildDossier(result);r.current={result,dossier,markdown:dossierMarkdown(dossier)};r.status=result.pendingFactIds.length?'REVIEW_REQUIRED':result.assessment.state==='UNKNOWN'?'NEEDS_REVIEW':'DOSSIER_READY';return r}
function addAudit(s,p,event,caseId,extra={}){s.audit.push({id:randomUUID(),tenantId:p.tenantId,principalId:p.principalId,role:p.role,at:now(),event,caseId,...extra})}
function sameValue(a,b){return JSON.stringify(a)===JSON.stringify(b)}
function approvedBaseline(r){
  const kinds=['PROJECT_ID','CONTRACT_ID','INSTRUMENT_ID','INSTRUMENT_TYPE','ORIGINAL_AMOUNT','CURRENT_AMOUNT'];const out={};
  for(const kind of kinds){const xs=r.extraction.facts.filter(f=>f.provenance?.documentType==='SECURITY_INSTRUMENT'&&f.kind===kind&&f.reviewStatus==='APPROVED');const vals=[];for(const f of xs)if(!vals.some(v=>sameValue(v,f.value)))vals.push(f.value);if(vals.length!==1)return null;out[kind]=vals[0]}
  return out;
}
function canApproveFact(r,f){
  if(f.provenance?.documentType==='SECURITY_INSTRUMENT'){
    const peers=r.extraction.facts.filter(x=>x.provenance?.documentType==='SECURITY_INSTRUMENT'&&x.kind===f.kind&&x.reviewStatus==='APPROVED');
    if(peers.some(x=>!sameValue(x.value,f.value)))return 'conflicting security-instrument baseline fact';
    return null;
  }
  const b=approvedBaseline(r);if(!b)return 'approved security-instrument baseline required first';
  const docId=f.provenance?.documentId,docFacts=r.extraction.facts.filter(x=>x.provenance?.documentId===docId);
  const projects=[...new Set(docFacts.filter(x=>x.kind==='PROJECT_ID').map(x=>String(x.value)))];
  const contracts=[...new Set(docFacts.filter(x=>x.kind==='CONTRACT_ID').map(x=>String(x.value)))];
  if(projects.length!==1||contracts.length!==1)return 'document project/contract identity evidence required';
  if(projects[0]!==String(b.PROJECT_ID)||contracts[0]!==String(b.CONTRACT_ID))return 'document identity mismatch cannot be approved';
  return null;
}

export const server=http.createServer(async(req,res)=>{try{
 const u=new URL(req.url,'http://localhost');
 if(req.method==='GET'&&u.pathname==='/health')return out(res,200,{ok:true,service:'guaranteerelease-case-v2',time:now()});
 const p=auth(req);if(!p)return out(res,401,{error:'unauthorized'});
 if(req.method==='GET'&&u.pathname==='/api/me')return out(res,200,p);
 if(req.method==='GET'&&u.pathname==='/api/cases'){const s=await loadStore();return out(res,200,{items:s.cases.filter(r=>r.tenantId===p.tenantId).map(publicMeta)})}
 if(req.method==='POST'&&u.pathname==='/api/cases'){
   if(p.role!=='operator')return out(res,403,{error:'operator role required'});
   const x=await body(req);if(!caseIdOk(x.caseId))return out(res,400,{error:'caseId invalid'});if(!Array.isArray(x.documents)||!x.documents.length||x.documents.length>50)return out(res,400,{error:'documents invalid'});if(Object.hasOwn(x,'facts')||Object.hasOwn(x,'assessment')||Object.hasOwn(x,'dossier'))return out(res,400,{error:'derived fields are server-controlled'});
   let extraction;try{extraction=extractDocuments(x.documents)}catch(e){return out(res,400,{error:`document packet invalid: ${e.message}`})}
   const at=now();const z=await enqueue(async()=>{const s=await loadStore();if(s.cases.some(r=>r.tenantId===p.tenantId&&r.caseId===x.caseId))return{status:409,payload:{error:'case already exists'}};for(const f of extraction.facts){f.reviewStatus='PENDING';f.submittedAt=at;f.submittedByPrincipalId=p.principalId}const r={caseId:x.caseId,tenantId:p.tenantId,asOf:typeof x.asOf==='string'&&!Number.isNaN(Date.parse(x.asOf))?x.asOf:at,createdAt:at,updatedAt:at,submittedByPrincipalId:p.principalId,status:'REVIEW_REQUIRED',extraction};recompute(r);s.cases.push(r);addAudit(s,p,'CASE_CREATED',r.caseId,{documentCount:extraction.documents.length,factCount:extraction.facts.length});await persist(s);return{status:201,payload:{item:publicCase(r)}}});return out(res,z.status,z.payload)
 }
 const cm=u.pathname.match(/^\/api\/cases\/([^/]+)$/);
 if(cm&&req.method==='GET'){const id=decodeURIComponent(cm[1]),s=await loadStore(),r=s.cases.find(q=>q.tenantId===p.tenantId&&q.caseId===id);return r?out(res,200,{item:publicCase(r)}):out(res,404,{error:'not found'})}
 const fm=u.pathname.match(/^\/api\/cases\/([^/]+)\/facts\/([^/]+)\/(approve|reject)$/);
 if(fm&&req.method==='POST'){
   if(p.role!=='reviewer')return out(res,403,{error:'reviewer role required'});const id=decodeURIComponent(fm[1]),fid=decodeURIComponent(fm[2]),action=fm[3],x=await body(req);
   const z=await enqueue(async()=>{const s=await loadStore(),r=s.cases.find(q=>q.tenantId===p.tenantId&&q.caseId===id);if(!r)return{status:404,payload:{error:'not found'}};const f=r.extraction.facts.find(q=>q.factId===fid);if(!f)return{status:404,payload:{error:'fact not found'}};if(f.reviewStatus!=='PENDING')return{status:409,payload:{error:'fact already reviewed'}};if(!f.submittedByPrincipalId||f.submittedByPrincipalId===p.principalId)return{status:409,payload:{error:'distinct operator provenance required'}};if(action==='approve'){const gate=canApproveFact(r,f);if(gate)return{status:409,payload:{error:gate}}}f.reviewStatus=action==='approve'?'APPROVED':'REJECTED';f.reviewedAt=now();f.reviewedByPrincipalId=p.principalId;f.reviewNote=typeof x.note==='string'?x.note.slice(0,1000):'';r.updatedAt=f.reviewedAt;recompute(r);addAudit(s,p,action==='approve'?'FACT_APPROVED':'FACT_REJECTED',id,{factId:fid,factKind:f.kind,toState:r.current.result.assessment.state});await persist(s);return{status:200,payload:{fact:{factId:f.factId,kind:f.kind,reviewStatus:f.reviewStatus},item:publicCase(r)}}});return out(res,z.status,z.payload)
 }
 const dossier=u.pathname.match(/^\/api\/cases\/([^/]+)\/dossier$/);
 if(dossier&&req.method==='GET'){const id=decodeURIComponent(dossier[1]),s=await loadStore(),r=s.cases.find(q=>q.tenantId===p.tenantId&&q.caseId===id);if(!r)return out(res,404,{error:'not found'});return out(res,200,{status:r.status,dossier:r.current.dossier,markdown:r.current.markdown})}
 if(req.method==='GET'&&u.pathname==='/api/audit'){const s=await loadStore();return out(res,200,{items:s.audit.filter(a=>a.tenantId===p.tenantId)})}
 return out(res,404,{error:'not found'});
}catch(e){if(!e.status)console.error(e);return out(res,e.status||500,{error:e.status?e.message:'internal error'})}});
if(import.meta.url===`file://${process.argv[1]}`)server.listen(PORT,()=>console.log(`GuaranteeRelease case server listening on ${PORT}`));
