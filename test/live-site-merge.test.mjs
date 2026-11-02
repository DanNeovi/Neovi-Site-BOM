import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const code=fs.readFileSync(new URL('../apps-script/LiveSiteBom.gs',import.meta.url),'utf8');
const context=vm.createContext({});
vm.runInContext(code,context);
const merge=(before,edited,incoming,historical=[])=>JSON.parse(vm.runInContext(`JSON.stringify(mergeSource_(${JSON.stringify(before)},${JSON.stringify(edited)},${JSON.stringify(incoming)},${JSON.stringify(historical)}))`,context));
const mergeCategories=(categories,items)=>JSON.parse(vm.runInContext(`JSON.stringify(mergeCategories_(${JSON.stringify(categories)},${JSON.stringify(items)}))`,context));
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
const absent=merge(before,edited,[before[1]]);
const retained=absent.find(i=>i.lineId==='A');
assert.equal(retained.sourceMissing,true);
const revived=merge([before[1]],[{...retained,description:'Field pile',siteQuantity:5},before[1]],
  [{...before[0],listedQuantity:9},before[1]],[before[0]]);
assert.deepEqual(revived.find(i=>i.lineId==='A'),
  {lineId:'A',description:'Field pile',listedQuantity:9,phase:'Foundation',siteQuantity:5});
assert.equal(merge([before[1]],[before[1]],[before[0],before[1]],[before[0]])
  .some(i=>i.lineId==='A'),false,'Earlier site deletion remains deleted after source reappears');
assert.throws(()=>merge([],[{lineId:'SITE-1',createdBySite:true}],
  [{lineId:'SITE-1',description:'Incoming source collision'}]),/Source ID collides/);
assert.deepEqual(mergeCategories([{path:['Custom'],manualOrder:4}],
  [{categoryPath:['Foundation','New']},{categoryPath:['Custom']}]),[
    {path:['Custom'],manualOrder:4},
    {path:['Foundation'],manualOrder:5},
    {path:['Foundation','New'],manualOrder:6},
  ]);
vm.runInContext(`
  spreadsheet_ = () => ({getSheets:()=>['Source_v1','Source_v2','Source_v4','State_v4']
    .map(name=>({getName:()=>name}))});
  readStateSheet_ = name => ({items: name==='Source_v2'
    ? [{lineId:'A',listedQuantity:5}]
    : [{lineId:'A',listedQuantity:4},{lineId:'B',listedQuantity:1}]});
`,context);
assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(priorSourceItems_(new Set(["A","B"]),"Source_v4"))',context)),
  [{lineId:'A',listedQuantity:5},{lineId:'B',listedQuantity:1}],
  'Reappearing items use the most recent historical source baseline');
context.ContentService={MimeType:{JSON:'application/json'},createTextOutput:text=>({text,setMimeType(type){this.type=type;return this}})};
const publicRead=vm.runInContext('output_({name:"<script>"})',context);
assert.equal(publicRead.type,'application/json');
assert.deepEqual(JSON.parse(publicRead.text),{name:'<script>'});
assert.equal(publicRead.text.includes('<script>'),false,'JSON must escape HTML delimiters');
console.log('PASS: source refresh preserves site edits, deletions and additions without freezing fresh model quantities.');
