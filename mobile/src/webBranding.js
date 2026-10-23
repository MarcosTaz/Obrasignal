import { BRAND } from './brand-palette.mjs';
import { brandMarkDataUri } from './logo-geometry.mjs';

function ensureFavicon() {
  let link=document.querySelector('link[data-obrasignal-favicon]') || document.querySelector('link[rel~="icon"]');
  if (!link) {link=document.createElement('link');link.rel='icon';document.head.appendChild(link);}
  link.setAttribute('data-obrasignal-favicon','true');
  link.type='image/svg+xml';
  link.href=brandMarkDataUri;
}
function ensureHostedTypography(){
  let link=document.querySelector('link[data-obrasignal-typography]');
  if(!link){
    link=document.createElement('link');
    link.setAttribute('data-obrasignal-typography','true');
    link.rel='stylesheet';
    link.href='/fonts.css';
    document.head.appendChild(link);
  }
}
function ensureThemeColor() {
  let node=document.querySelector('meta[name="theme-color"]');
  if(!node){node=document.createElement('meta');node.name='theme-color';document.head.appendChild(node);}
  node.content='#06111D';
}
export function installWebBranding() {
  if(typeof document==='undefined')return ()=>{};
  ensureFavicon();
  ensureThemeColor();
  ensureHostedTypography();
  // The official mark lives in explicit React components, not DOM observers.
  // no unsolicited DOM decoration, no recolouring of user-selected UI themes.
  return ()=>{};
}
export { brandMarkDataUri as obrasignalMarkDataUri };
