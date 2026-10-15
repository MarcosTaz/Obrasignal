import test from 'node:test';
import assert from 'node:assert/strict';
import {APPROVED_SCENES,APPROVED_SCENE_SIZE,CHAMPAGNE_WINDOWS,sceneGeometry,normalizedVertices} from './my-office-geometry.mjs';
test('seven distinct scenes are tracked without inventing six geometry maps',()=>{
  assert.equal(APPROVED_SCENES.length,7);
  assert.equal(new Set(APPROVED_SCENES.map(x=>x.id)).size,7);
  assert.equal(CHAMPAGNE_WINDOWS.length,7);
  for(const s of APPROVED_SCENES.slice(1)) assert.equal(sceneGeometry(s.id),null);
});
test('V23 coordinates and quadrilaterals preserve reference bounds',()=>{
  assert.deepEqual(APPROVED_SCENE_SIZE,{width:1672,height:941});
  assert.deepEqual(CHAMPAGNE_WINDOWS[0],[[37,247],[266,289],[266,675],[37,719]]);
  assert.deepEqual(CHAMPAGNE_WINDOWS[6],[[1401,290],[1611,247],[1611,721],[1401,678]]);
  for(const quad of CHAMPAGNE_WINDOWS){
    assert.equal(quad.length,4);
    for(const [x,y] of quad){assert.ok(x>=0&&x<=1672);assert.ok(y>=0&&y<=941);}
  }
});
test('responsive scaling preserves vertices and rejects invalid bounds',()=>{
  const transformed=normalizedVertices(0,1672,941);
  transformed.forEach((p,i)=>p.forEach((n,k)=>assert.ok(Math.abs(n-CHAMPAGNE_WINDOWS[0][i][k])<1e-9)));
  assert.equal(normalizedVertices(-1,1672,941),null);
  assert.equal(normalizedVertices(0,0,941),null);
});
