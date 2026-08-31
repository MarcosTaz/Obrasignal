import fs from 'node:fs';
import { createClient } from '@supabase/supabase-js';

const url = (process.env.SUPABASE_URL || '').trim();
const key = (process.env.SUPABASE_KEY || '').trim();
const envFile = process.env.GITHUB_ENV || '';
if (!url || !key || !envFile) {
  throw new Error('SUPABASE_URL, SUPABASE_KEY and GITHUB_ENV are required');
}

const supabase = createClient(url, key, {
  auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
});
const { data, error } = await supabase.auth.signInAnonymously();
if (error) throw error;
const token = data?.session?.access_token;
const userId = data?.user?.id;
if (!token || !userId) throw new Error('anonymous auth returned no access token/user id');

// Never print the token in clear text. GitHub masks it before subsequent output.
console.log(`::add-mask::${token}`);
fs.appendFileSync(envFile, `E2E_ACCESS_TOKEN_B=${token}\nE2E_USER_ID_B=${userId}\n`, 'utf8');
console.log(`Provisioned distinct ephemeral tenant B ${userId}`);
