import assert from 'node:assert/strict';
import { sourceItemsHash } from '../src/live-source-hash.mjs';

const items=[
  {lineId:'A',description:'Pile',categoryPath:['Foundation','Piles'],listedQuantity:48},
  {lineId:'B',description:'Drill',categoryPath:['Foundation','Tools'],listedQuantity:4},
];

assert.match(sourceItemsHash(items),/^[a-f0-9]{64}$/);
assert.equal(sourceItemsHash(items),sourceItemsHash([
  {listedQuantity:48,categoryPath:['Foundation','Piles'],description:'Pile',lineId:'A'},
  {categoryPath:['Foundation','Tools'],lineId:'B',listedQuantity:4,description:'Drill'},
]),'Object property order does not change the source hash');
assert.notEqual(sourceItemsHash(items),sourceItemsHash([...items].reverse()),
  'Item order remains part of the source payload');
assert.notEqual(sourceItemsHash(items),sourceItemsHash([{...items[0],listedQuantity:49},items[1]]),
  'A quantity change changes the source hash');
assert.notEqual(sourceItemsHash(items),sourceItemsHash([{...items[0],categoryPath:['Foundation','Steel']},items[1]]),
  'An item category-path change changes the source hash');
assert.throws(()=>sourceItemsHash(null),/array/);
console.log('PASS: source hash tracks applied BOM items, independent of HTML metadata and key order.');
