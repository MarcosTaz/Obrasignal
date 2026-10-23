import { BRAND } from './brand-palette.mjs';

/** Master geometry recreated as clean flat vectors from the approved brand study.
 * These paths, not the full presentation image, are the image source of truth.
 * Maintain identical geometry in static exported .svg files. */
export const BRAND_MARK_PATHS = Object.freeze({
  left: 'M8 56 L37 39 L37 92 L8 110 Z',
  centreDark: 'M43 21 L61 10 L61 75 L43 89 Z',
  centreLight: 'M61 10 L77 20 L77 88 L61 75 Z',
  right: 'M84 40 L108 55 L108 110 L84 94 Z',
  decision: 'M61 91 L98 113 L24 113 Z',
});
export const BRAND_MARK_VIEWBOX = '0 0 116 120';
export function buildBrandMarkSvg({ inverse=false, background=null }={}) {
  const p=BRAND_MARK_PATHS;
  const slate=inverse?BRAND.paper:BRAND.slate;
  const middle=inverse?'#D6E0E8':BRAND.mineral;
  const right=inverse?BRAND.fog:BRAND.slate;
  const bg=background?'<rect x="0" y="0" width="116" height="120" rx="20" fill="'+background+'"/>':'';
  return '<svg xmlns="http://www.w3.org/2000/svg" width="116" height="120" viewBox="'+BRAND_MARK_VIEWBOX+'" role="img" aria-label="ObraSignal — símbolo de seleção e decisão">'+bg
    +'<path d="'+p.left+'" fill="'+slate+'"/>'
    +'<path d="'+p.centreDark+'" fill="'+slate+'"/>'
    +'<path d="'+p.centreLight+'" fill="'+middle+'"/>'
    +'<path d="'+p.right+'" fill="'+right+'"/>'
    +'<path d="'+p.decision+'" fill="'+BRAND.copper+'"/>'
    +'</svg>';
}
export const brandMarkDataUri='data:image/svg+xml,'+encodeURIComponent(buildBrandMarkSvg({background:BRAND.paper}));
