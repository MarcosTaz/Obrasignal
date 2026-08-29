import fs from 'node:fs';import path from 'node:path';import {analyzeCsv} from '../lib/pipeline.mjs';import {sha256} from '../lib/utils.mjs';
const args=Object.fromEntries(process.argv.slice(2).map((v,i,a)=>v.startsWith('--')?[v.slice(2),a[i+1]]:null).filter(Boolean));
for(const k of ['tenant','csv','contracts','evidence','out'])if(!args[k]){console.error(`MISSING_ARG_${k.toUpperCase()}`);process.exit(2);}
const read=p=>fs.readFileSync(p,'utf8'); const csv=read(args.csv),contracts=JSON.parse(read(args.contracts)),evidence=JSON.parse(read(args.evidence));
const result=analyzeCsv({tenantId:args.tenant,csv,contracts,evidence,requireContext:true});fs.mkdirSync(args.out,{recursive:true});
const sources={csv:{path:path.basename(args.csv),sha256:sha256(csv)},contracts:{path:path.basename(args.contracts),sha256:sha256(read(args.contracts))},evidence:{path:path.basename(args.evidence),sha256:sha256(read(args.evidence))}};
fs.writeFileSync(path.join(args.out,'analysis.json'),JSON.stringify({...result,sources},null,2));
fs.writeFileSync(path.join(args.out,'dispute-packs.json'),JSON.stringify(result.packages,null,2));
let md=`# DebitProof assisted analysis\n\nTenant: \`${args.tenant}\`\n\nCases: ${result.summary.cases}  \nUNKNOWN: ${result.summary.unknown}  \nDraft dispute packs: ${result.packages.length}\n\n## Economic summary\n`;
for(const [c,v] of Object.entries(result.summary.byCurrency))md+=`- ${c}: received ${v.received}; supported ${v.supported}; known disputable ${v.knownDisputable}\n`;
md+=`\nUNKNOWN values are excluded from economic totals. Draft packages are not recoveries.\n`;
fs.writeFileSync(path.join(args.out,'REPORT.md'),md);console.log(JSON.stringify({ok:true,summary:result.summary,packages:result.packages.length,out:args.out}));
