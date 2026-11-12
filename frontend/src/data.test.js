import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { closeRing, selectedCameras, coveredZones, validateResult, validBBox } from './data.js';
const result = n => JSON.parse(readFileSync(new URL(`../../data/results/result_sector_${n}.json`,import.meta.url)));
for (const n of [8,12,16]) test(`${n}-qubit saved result renders all methods by IDs`,()=>{
  const d=validateResult(result(n));
  for (const m of ['qaoa','exact','greedy']) {
    assert.deepEqual(selectedCameras(d,m).map(c=>c.id),d.solutions[m].selected);
    assert.equal(coveredZones(d,m).filter(z=>z.isCovered).length,d.solutions[m].zones_covered);
  }
});
test('coverage follows active selected IDs rather than saved coverage flags',()=>{
  const d=result(8);d.solutions.qaoa.selected=[];
  assert.equal(coveredZones(d,'qaoa').filter(z=>z.isCovered).length,0);
  assert.equal(d.zones[0].covered.qaoa,true);
});
test('candidate lookup works with sparse IDs and shuffled candidate order',()=>{
  const d=result(8);d.candidates.reverse();
  d.candidates.forEach(c=>c.id+=100);
  d.solutions.qaoa.selected=d.solutions.qaoa.selected.map(id=>id+100);
  assert.deepEqual(selectedCameras(d,'qaoa').map(c=>c.id),d.solutions.qaoa.selected);assert.ok(d.solutions.qaoa.selected.every(id=>id>=100));
});
test('polygon closure copies data without mutating original',()=>{
  const p=[[0,0],[1,0],[1,1]];assert.equal(closeRing(p).length,4);assert.equal(p.length,3);
  assert.equal(closeRing(closeRing(p)).length,4);
});
test('reject invalid references and malformed result before rendering',()=>{
  const d=result(12);d.solutions.qaoa.selected[0]=999;
  assert.throws(()=>validateResult(d),/selected IDs/);
  assert.throws(()=>validateResult({}),/sector/);
});
test('bbox validates finite increasing coordinates',()=>{
  assert.ok(validBBox([-74,40,-73,41]));
  for (const b of [[0,0,0,1],[0,0,1,90],[NaN,0,1,1],['0',0,1,1],[]]) assert.equal(validBBox(b),false);
});
