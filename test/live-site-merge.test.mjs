import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const code=fs.readFileSync(new URL('../apps-script/LiveSiteBom.gs',import.meta.url),'utf8');
const context=vm.createContext({});
vm.runInContext(code,context);
const merge=(before,edited,incoming)=>JSON.parse(vm.runInContext(`JSON.stringify(mergeSource_(${JSON.stringify(before)},${JSON.stringify(edited)},${JSON.stringify(incoming)}))`,context));
const before=[
  {lineId:'A',description:'Pile',listedQuantity:4,phase:'Foundation'},
  {lineId:'B',description:'Drill',listedQuantity:2,phase:'Foundation'},
  {lineId:'C',description:'Old item',listedQuantity:1,phase:'Foundation'},
];
const edited=[
  {lineId:'A',description:'Renamed pile',listedQuantity:4,siteQuantity:5,phase:'Foundation'},
  {lineId:'C',description:'Old item',listedQuantity:1,phase:'Foundation'},
  {lineId:'SITE-1',description:'Site added',siteQuantity:3,phase:'Foundation'},
];
const incoming=[
  {lineId:'A',description:'Pile',listedQuantity:6,phase:'Foundation'},
  {lineId:'B',description:'Drill',listedQuantity:3,phase:'Foundation'},
  {lineId:'D',description:'New from model',listedQuantity:2,phase:'Foundation'},
];
const result=merge(before,edited,incoming);
assert.deepEqual(result.find(i=>i.lineId==='A'),{lineId:'A',description:'Renamed pile',listedQuantity:6,phase:'Foundation',siteQuantity:5});
assert.equal(result.some(i=>i.lineId==='B'),false,'Website deletion stays deleted');
assert.equal(result.find(i=>i.lineId==='C').sourceMissing,true,'Removed source stays visible for review');
assert.equal(result.find(i=>i.lineId==='D').listedQuantity,2);
assert.equal(result.find(i=>i.lineId==='SITE-1').siteQuantity,3);
assert.throws(()=>merge([],[],[{lineId:'D'},{lineId:'D'}]),/Duplicate source ID/);
console.log('PASS: source refresh preserves site edits, deletions and additions without freezing fresh model quantities.');
