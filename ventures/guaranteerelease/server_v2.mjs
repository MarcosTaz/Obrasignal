import http from 'node:http';
import {readFile,writeFile,rename,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {randomUUID,createHash,timingSafeEqual} from 'node:crypto';
import {assessSecurity} from './engine_v2.mjs';

const DATA_FILE=process.env.GR_DATA_FILE||new URL('./data/guaranteerelease.json',import.meta.url).pathname;
const PORT=Number(process.env.PORT||8787);
const MAX_BODY=256*1024;
const APP_FILE=new URL('./app_v2.html',import.meta.url).pathname;
let writeChain=Promise.resolve();
const now=()=>new Date().toISOString();
const emptyStore=()=>({version:1,instruments:[],audit:[]});
async function loadStore(){try{const raw=await readFile(DATA_FILE,'utf8');const parsed=JSON.parse(raw);if(!Array.isArray(parsed.instruments)||!Array.isArray(parsed.audit))throw new Error('invalid store');return parsed;}catch(e){if(e.code==='ENOENT')return emptyStore();throw e;}}
async function persist(store){await mkdir(dirname(DATA_FILE),{recursive:true});const tmp=`${DATA_FILE}.${process.pid}.${Date.now()}.tmp`;await writeFile(tmp,JSON.stringify(store,null,2),{encoding:'utf8',mode:0o600});await rename(tmp,DATA_FILE);}
function enqueueWrite(fn){const next=writeChain.then(fn,fn);writeChain=next.catch(()=>{});return next;}
function json(res,status,payload){const body=JSON.stringify(payload);res.writeHead(status,{'content-type':'application/json; charset=utf-8','content-length':Buffer.byteLength(body),'cache-control':'no-store'});res.end(body);}
async function bodyJson(req){let size=0,chunks=[];for await(const chunk of req){size+=chunk.length;if(size>MAX_BODY)throw Object.assign(new Error('body too large'),{status:413});chunks.push(chunk);}if(!chunks.length)return{};try{return JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{throw Object.assign(new Error('invalid json'),{status:400});}}
function apiKeys(){try{const v=JSON.parse(process.env.GR_API_KEYS_JSON||'{}');return v&&typeof v==='object'?v:{};}catch{return{};}}
function constEq(a,b){const ah=createHash('sha256').update(String(a)).digest(),bh=createHash('sha256').update(String(b)).digest();return timingSafeEqual(ah,bh);}
function auth(req){const h=req.headers.authorization||'';const token=h.startsWith('Bearer ')?h.slice(7):'';if(!token)return null;for(const [key,tenantId] of Object.entries(apiKeys()))if(constEq(key,token))return String(tenantId);return null;}
function publicInstrument(x){const {tenantId,...rest}=x;return rest;}
function validateCreate(input){const required=['instrumentId','company','projectId','contractId','instrumentType','currency','originalAmount','currentAmount'];for(const key of required)if(input[key]===undefined||input[key]===null||input[key]==='')return `${key} required`;if(typeof input.instrumentId!=='string'||input.instrumentId.length>120)return 'instrumentId invalid';if(typeof input.currency!=='string'||!/^[A-Z]{3}$/.test(input.currency))return 'currency invalid';return null;}

export const server=http.createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://localhost');
    if(req.method==='GET'&&(url.pathname==='/'||url.pathname==='/app')){const body=await readFile(APP_FILE,'utf8');res.writeHead(200,{'content-type':'text/html; charset=utf-8','content-length':Buffer.byteLength(body),'cache-control':'no-store'});return res.end(body);}
    if(req.method==='GET'&&url.pathname==='/health')return json(res,200,{ok:true,service:'guaranteerelease',time:now()});
    const tenantId=auth(req);if(!tenantId)return json(res,401,{error:'unauthorized'});
    if(req.method==='GET'&&url.pathname==='/api/instruments'){const store=await loadStore();return json(res,200,{items:store.instruments.filter(x=>x.tenantId===tenantId).map(publicInstrument)});}
    if(req.method==='POST'&&url.pathname==='/api/instruments'){
      const input=await bodyJson(req);const err=validateCreate(input);if(err)return json(res,400,{error:err});
      const result=await enqueueWrite(async()=>{const store=await loadStore();if(store.instruments.some(x=>x.tenantId===tenantId&&x.instrumentId===input.instrumentId))return{status:409,payload:{error:'instrument already exists'}};const ts=now();const record={...input,tenantId,createdAt:ts,updatedAt:ts,assessment:assessSecurity(input)};store.instruments.push(record);store.audit.push({id:randomUUID(),tenantId,at:ts,event:'INSTRUMENT_CREATED',instrumentId:input.instrumentId,assessmentState:record.assessment.state});await persist(store);return{status:201,payload:{item:publicInstrument(record)}};});return json(res,result.status,result.payload);
    }
    const match=url.pathname.match(/^\/api\/instruments\/([^/]+)$/);
    if(match&&req.method==='GET'){const id=decodeURIComponent(match[1]);const store=await loadStore();const found=store.instruments.find(x=>x.tenantId===tenantId&&x.instrumentId===id);return found?json(res,200,{item:publicInstrument(found)}):json(res,404,{error:'not found'});}
    if(match&&req.method==='PATCH'){
      const id=decodeURIComponent(match[1]);const patch=await bodyJson(req);for(const k of ['tenantId','instrumentId','createdAt','assessment'])if(Object.hasOwn(patch,k))return json(res,400,{error:`${k} cannot be patched`});
      const result=await enqueueWrite(async()=>{const store=await loadStore();const idx=store.instruments.findIndex(x=>x.tenantId===tenantId&&x.instrumentId===id);if(idx<0)return{status:404,payload:{error:'not found'}};const prior=store.instruments[idx];const next={...prior,...patch,tenantId,instrumentId:id,createdAt:prior.createdAt,updatedAt:now()};const err=validateCreate(next);if(err)return{status:400,payload:{error:err}};next.assessment=assessSecurity(next);store.instruments[idx]=next;store.audit.push({id:randomUUID(),tenantId,at:next.updatedAt,event:'INSTRUMENT_REASSESSED',instrumentId:id,fromState:prior.assessment?.state||null,toState:next.assessment.state});await persist(store);return{status:200,payload:{item:publicInstrument(next)}};});return json(res,result.status,result.payload);
    }
    if(req.method==='GET'&&url.pathname==='/api/audit'){const store=await loadStore();return json(res,200,{items:store.audit.filter(x=>x.tenantId===tenantId)});}
    return json(res,404,{error:'not found'});
  }catch(e){console.error(e);return json(res,e.status||500,{error:e.status?e.message:'internal error'});}
});
if(import.meta.url===`file://${process.argv[1]}`)server.listen(PORT,()=>console.log(`GuaranteeRelease listening on ${PORT}`));
