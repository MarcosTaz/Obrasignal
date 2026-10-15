import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const scene=readFileSync(new URL('../components/MyOfficeScene.js',import.meta.url),'utf8');
const app=readFileSync(new URL('../App.web.js',import.meta.url),'utf8');
test('scene hotspots follow the approved four-point V23 polygon',()=>{
 assert.match(scene,/clipPath:`polygon\(\$\{polygon\}\)`/);
 assert.match(scene,/CHAMPAGNE_WINDOWS\.map/);
 assert.match(scene,/disabled=\{!target\}/);
});
test('no misleading substitute artwork or unauthenticated activation',()=>{
 assert.match(scene,/if\(!sceneSource\)/);
 assert.match(app,/return <AuthGate><WebMain\/><\/AuthGate>/);
 assert.match(app,/MY_OFFICE_ENABLED && tab==='office'/);
});
