import {readFile,writeFile,mkdir,copyFile,access} from 'node:fs/promises';
import {dirname,basename,join} from 'node:path';
import {createHash} from 'node:crypto';
const sha256=b=>createHash('sha256').update(b).digest('hex');
const stamp=()=>new Date().toISOString().replace(/[:.]/g,'-');
export async function createBackup({dataFile,backupDir}){
  const bytes=await readFile(dataFile); JSON.parse(bytes.toString('utf8'));
  await mkdir(backupDir,{recursive:true});
  const name=`${basename(dataFile)}.${stamp()}.bak`;
  const backupPath=join(backupDir,name); await writeFile(backupPath,bytes,{mode:0o600,flag:'wx'});
  const manifest={version:1,createdAt:new Date().toISOString(),sourceFile:basename(dataFile),backupFile:name,bytes:bytes.length,sha256:sha256(bytes)};
  const manifestPath=`${backupPath}.manifest.json`; await writeFile(manifestPath,JSON.stringify(manifest,null,2),{mode:0o600,flag:'wx'});
  return{backupPath,manifestPath,manifest};
}
export async function verifyBackup({backupPath,manifestPath=`${backupPath}.manifest.json`}){
  const [bytes,mraw]=await Promise.all([readFile(backupPath),readFile(manifestPath,'utf8')]);
  const manifest=JSON.parse(mraw); const actual=sha256(bytes);
  if(actual!==manifest.sha256)throw new Error('backup checksum mismatch');
  JSON.parse(bytes.toString('utf8'));
  return{ok:true,sha256:actual,bytes:bytes.length,manifest};
}
export async function restoreBackup({backupPath,manifestPath=`${backupPath}.manifest.json`,targetPath,overwrite=false}){
  await verifyBackup({backupPath,manifestPath});
  if(!overwrite){try{await access(targetPath);throw new Error('target exists; explicit overwrite required')}catch(e){if(e.code!=='ENOENT')throw e}}
  await mkdir(dirname(targetPath),{recursive:true}); await copyFile(backupPath,targetPath);
  const restored=await readFile(targetPath); return{targetPath,sha256:sha256(restored),bytes:restored.length};
}
