// Original measured V23 Champagne polygons from 1672x941 approved scene.
// Co-ordinates copied verbatim; DO NOT transpose onto the six other architectures.
export const APPROVED_SCENE_SIZE = Object.freeze({width:1672,height:941});
export const CHAMPAGNE_WINDOWS = Object.freeze([
  [[37,247],[266,289],[266,675],[37,719]],
  [[297,289],[486,325],[486,645],[297,688]],
  [[508,325],[696,350],[696,622],[508,642]],
  [[732,355],[920,355],[920,622],[732,624]],
  [[958,349],[1141,325],[1141,648],[958,624]],
  [[1170,321],[1353,293],[1353,678],[1170,643]],
  [[1401,290],[1611,247],[1611,721],[1401,678]]
].map(p => Object.freeze(p.map(v => Object.freeze(v)))));
export const APPROVED_SCENES = Object.freeze([
  {id:'champagne',label:'Champanhe',geometry:CHAMPAGNE_WINDOWS,assetStatus:'original-in-library'},
  {id:'copper',label:'Cobre',geometry:null,assetStatus:'not-imported'},
  {id:'cobalt',label:'Cobalto',geometry:null,assetStatus:'not-imported'},
  {id:'emerald',label:'Esmeralda',geometry:null,assetStatus:'not-imported'},
  {id:'ivory',label:'Marfim',geometry:null,assetStatus:'not-imported'},
  {id:'crimson',label:'Crimson',geometry:null,assetStatus:'not-imported'},
  {id:'violet',label:'Violeta',geometry:null,assetStatus:'not-imported'}
]);
export function sceneGeometry(id){
  const scene=APPROVED_SCENES.find(s=>s.id===id);
  return scene?.geometry || null;
}
export function normalizedVertices(index,width,height){
  if(!Number.isInteger(index)||index<0||index>=CHAMPAGNE_WINDOWS.length||!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0) return null;
  return CHAMPAGNE_WINDOWS[index].map(([x,y])=>[x/APPROVED_SCENE_SIZE.width*width,y/APPROVED_SCENE_SIZE.height*height]);
}
