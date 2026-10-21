import {readFile,stat} from 'node:fs/promises';
import {extname,basename} from 'node:path';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execFileP=promisify(execFile);
const hash=b=>createHash('sha256').update(b).digest('hex');

export async function textFileToDocument(path,{documentId,type,sourceName,supersedes=[],metadata={},maxBytes=10*1024*1024}={}){
  const st=await stat(path); if(!st.isFile())throw Error('source is not a file'); if(st.size>maxBytes)throw Error('source file too large');
  const bytes=await readFile(path); const text=bytes.toString('utf8'); if(!text.trim())throw Error('source text empty');
  const pages=text.split('\f').map((t,i)=>({pageNumber:i+1,text:t.trim()})).filter(p=>p.text);
  if(!pages.length)throw Error('source text empty');
  return {documentId,type,sourceName:sourceName||basename(path),pages,sourceSha256:hash(bytes),supersedes,metadata:{...metadata,adapter:'native-document-adapter-v1',sourceFormat:'text'}};
}

export async function pdfFileToDocument(path,{documentId,type,sourceName,supersedes=[],metadata={},maxBytes=20*1024*1024,maxPages=500,pdftotextPath='pdftotext',timeoutMs=20000}={}){
  if(extname(path).toLowerCase()!=='.pdf')throw Error('pdf extension required');
  const st=await stat(path); if(!st.isFile())throw Error('source is not a file'); if(st.size>maxBytes)throw Error('source file too large');
  const bytes=await readFile(path); if(bytes.subarray(0,5).toString('ascii')!=='%PDF-')throw Error('invalid PDF magic');
  let stdout;
  try{
    ({stdout}=await execFileP(pdftotextPath,['-layout','-enc','UTF-8','-eol','unix',path,'-'],{encoding:'utf8',timeout:timeoutMs,maxBuffer:16*1024*1024,windowsHide:true}));
  }catch(e){
    const msg=e?.killed?'PDF extraction timeout':'PDF extraction failed';throw Object.assign(Error(msg),{cause:e});
  }
  const raw=String(stdout||'');
  const pages=raw.split('\f').map((t,i)=>({pageNumber:i+1,text:t.trim()})).filter(p=>p.text);
  if(!pages.length)throw Error('PDF contains no extractable text; OCR/review required');
  if(pages.length>maxPages)throw Error('PDF page limit exceeded');
  return {documentId,type,sourceName:sourceName||basename(path),pages,sourceSha256:hash(bytes),supersedes,metadata:{...metadata,adapter:'native-document-adapter-v1',sourceFormat:'pdf',textExtractor:'pdftotext'}};
}

export async function sourceFileToDocument(path,opts){
  const ext=extname(path).toLowerCase();
  if(ext==='.pdf')return pdfFileToDocument(path,opts);
  if(ext==='.txt'||ext==='.md')return textFileToDocument(path,opts);
  throw Error(`unsupported source extension: ${ext||'(none)'}`);
}
