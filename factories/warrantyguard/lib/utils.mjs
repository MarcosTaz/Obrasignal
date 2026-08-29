import crypto from 'node:crypto';
export const MAX_AMOUNT=1_000_000_000_000;
export function normalizeAmount(v,{allowNull=false}={}){
  if((v===null||v===undefined||v==='')&&allowNull)return null;
  const n=Number(v);
  if(!Number.isFinite(n)||n<0||n>MAX_AMOUNT)throw new Error('INVALID_AMOUNT');
  return Math.round((n+Number.EPSILON)*100)/100;
}
export function strictBool(v,{allowNull=true}={}){
  if(v===true||v==='true'||v==='TRUE'||v===1||v==='1')return true;
  if(v===false||v==='false'||v==='FALSE'||v===0||v==='0')return false;
  if((v===null||v===undefined||v==='')&&allowNull)return null;
  throw new Error('INVALID_BOOLEAN');
}
export function validCurrency(v){return typeof v==='string'&&/^[A-Z]{3}$/.test(v);}
export function parseIsoDate(v){
  if(typeof v!=='string'||!(/^(\d{4})-(\d{2})-(\d{2})$/).test(v))throw new Error('INVALID_DATE');
  const [y,m,d]=v.split('-').map(Number); const dt=new Date(Date.UTC(y,m-1,d));
  if(dt.getUTCFullYear()!==y||dt.getUTCMonth()!==m-1||dt.getUTCDate()!==d)throw new Error('INVALID_DATE');
  return v;
}
export function parseIsoTimestamp(v){
  const m=typeof v==='string'&&v.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,3})?(Z|([+-])(\d{2}):(\d{2}))$/);
  if(!m)throw new Error('INVALID_TIMESTAMP');
  const [y,mo,d,h,mi,se]=m.slice(1,7).map(Number);const dt=new Date(Date.UTC(y,mo-1,d,h,mi,se));
  if(dt.getUTCFullYear()!==y||dt.getUTCMonth()!==mo-1||dt.getUTCDate()!==d||dt.getUTCHours()!==h||dt.getUTCMinutes()!==mi||dt.getUTCSeconds()!==se)throw new Error('INVALID_TIMESTAMP');
  if(m[7]!=='Z'&&(Number(m[9])>23||Number(m[10])>59))throw new Error('INVALID_TIMESTAMP');
  const t=Date.parse(v);if(!Number.isFinite(t))throw new Error('INVALID_TIMESTAMP');return v;
}
export function sha256(v){return crypto.createHash('sha256').update(typeof v==='string'?v:stableStringify(v)).digest('hex');}
export function stableStringify(v){
  if(v===null||typeof v!=='object')return JSON.stringify(v);
  if(Array.isArray(v))return '['+v.map(stableStringify).join(',')+']';
  return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stableStringify(v[k])).join(',')+'}';
}
export function requiredText(v,name){if(typeof v!=='string'||!v.trim())throw new Error(`MISSING_${name.toUpperCase()}`);return v.trim();}
export function round2(v){return Math.round((v+Number.EPSILON)*100)/100;}
