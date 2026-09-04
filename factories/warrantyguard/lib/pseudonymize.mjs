import crypto from 'node:crypto';
export function pseudonymize({tenantId,value,key}){if(!tenantId||!value||!key)throw new Error('PSEUDONYM_INPUT_REQUIRED');return crypto.createHmac('sha256',key).update(`${tenantId}\0${value}`).digest('hex').slice(0,24);}
