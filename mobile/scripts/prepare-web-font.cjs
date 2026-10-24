/* Build-only copier: the licensed font package stays a dependency. No CDN requests. */
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=path.join(root,'node_modules','@fontsource-variable','manrope','files','manrope-latin-wght-normal.woff2');
const targetDir=path.join(root,'public','fonts');
const target=path.join(targetDir,'manrope-latin-wght-normal.woff2');
if(!fs.existsSync(source))throw new Error('Installed Manrope variable font package is missing its Latin WOFF2 asset');
fs.mkdirSync(targetDir,{recursive:true});
fs.copyFileSync(source,target);
fs.writeFileSync(path.join(root,'public','fonts.css'),`@font-face {
  font-family: "Manrope Variable";
  src: url("/fonts/manrope-latin-wght-normal.woff2") format("woff2");
  font-style: normal;
  font-weight: 200 800;
  font-display: swap;
}
`,'utf8');
console.log('Prepared same-origin Manrope variable font assets');
