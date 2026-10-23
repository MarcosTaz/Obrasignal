// ObraSignal's identity is constant; each theme is a user preference.
 // Five stops preserve the original submitted palette order (light -> dark).
import { BRAND } from './brand-palette.mjs';
export const DEFAULT_THEME = 'command-night';

export const THEMES = Object.freeze([
  {id:'command-night',name:'Command Night',description:'Deep navy · blue steel · copper',swatches:['#F4F8FE','#BDD0E4','#7294B4','#102A42','#06111D'],accent:'#78BEFB',mode:'dark'},
  {id:'signature',name:'ObraSignal Signature',description:'Slate · mineral · mist blue · copper',swatches:[BRAND.paper,BRAND.fog,BRAND.mistBlue,BRAND.mineral,BRAND.slate],accent:BRAND.slate,mode:'light'},
  {id:'glass-graphite',name:'Glass & Graphite',swatches:['#F5F7FA','#D9DEE7','#AEB7C6','#4B5563','#111827'],accent:'#364D72',mode:'light'},
  {id:'warm-linen',name:'Warm Linen',swatches:['#FAF3E7','#E7D9C6','#C8B39A','#6B5B4B','#2B2621'],accent:'#835034',mode:'light'},
  {id:'sage',name:'Sage',swatches:['#F2F5F1','#D7E2D2','#9BB59A','#4C6A54','#1F2D24'],accent:'#305E49',mode:'light'},
  {id:'modern-moss',name:'Modern Moss',swatches:['#F4F7F3','#D0DDCD','#7B9B7A','#2F5D50','#102A22'],accent:'#2F5D50',mode:'light'},
  {id:'minimal-beige',name:'Minimal Beige',swatches:['#FFFBF5','#EFE3D3','#C9B8A2','#6E6256','#1F1B16'],accent:'#754B36',mode:'light'},
  {id:'slate-circuit',name:'Slate Circuit',swatches:['#F6F8FB','#D3DAE6','#7D8AA3','#2A3650','#0B1220'],accent:'#344E86',mode:'light'},
  {id:'steel-lavender',name:'Steel Lavender',swatches:['#F7F6FB','#DDD8F0','#A7A0C7','#5B5E77','#1A1C2A'],accent:'#625290',mode:'light'},
  {id:'midnight-blue',name:'Midnight Blue',swatches:['#F4F6FB','#C7D2E9','#5B6B8C','#1C2A44','#0A0F1A'],accent:'#87A8E4',mode:'dark'},
  {id:'original-night',name:'Technical Night',description:'Legacy look, official logo retained',swatches:['#F4F7FB','#B1BDCB','#6F829A','#14263A','#07111C'],accent:'#9BB6FF',mode:'dark'},
]);

export function resolveTheme(id) {
  return THEMES.find(item=>item.id===id) || THEMES[0];
}
export function createThemeColors(id) {
  const t=resolveTheme(id);
  const [light,second,third,fourth,dark]=t.swatches;
  const isDark=t.mode==='dark';
  return Object.freeze({
    bg:isDark?dark:light,
    panel:isDark?fourth:'#FFFFFF',
    panel2:isDark?dark:second,
    line:isDark?third:third,
    text:t.id==='signature'?BRAND.ink:(isDark?light:dark),
    muted:isDark?second:fourth,
    muted2:isDark?second:fourth,
    blue:t.accent,
    blueSoft:isDark?fourth:second,
    blueText:isDark?light:dark,
    green:isDark?'#84DAB4':'#23684B',
    amber:isDark?'#F1C87E':'#80500D',
    red:isDark?'#FF9BA5':'#A02B3B',
    onAccent:isDark?dark:'#FFFFFF',
    action:t.id==='signature'?BRAND.copper:t.accent,
    onAction:t.id==='signature'?BRAND.ink:(isDark?dark:'#FFFFFF'),
    brandCopper:BRAND.copper,
    input:isDark?dark:'#FFFFFF',
    subtle:isDark?fourth:second,
    navActive:isDark?fourth:second,
    borderStrong:isDark?second:fourth,
    errorBg:isDark?'#2D161E':'#FFF0F1',
    errorBorder:isDark?'#B76B76':'#B35163',
    errorText:isDark?'#FFD6DC':'#852537',
  });
}
