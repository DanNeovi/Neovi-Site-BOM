import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const code=fs.readFileSync(new URL('../apps-script/LiveSiteBom.gs',import.meta.url),'utf8');
const item={lineId:'A-1',description:'Pile',phase:'Foundation',stage:'Site',unit:'EA',categoryPath:['Foundation']};
const initialMeta=['State_v11',11,'old-nonce','2026-11-09T00:00:00Z','Editor','Source_v1','a'.repeat(64)];

function fixture(options={}) {
  const sheets=new Map();
  const deleted=[];
  let nextId=1;
  let meta=[...initialMeta];
  const workbook={
    getSheetByName(name){return sheets.get(name)||null},
    getSheets(){return [...sheets.values()]},
    insertSheet(name){
      if(sheets.has(name))throw new Error('Sheet exists');
      const sheet={
        name,id:nextId++,rows:[],
        getName(){return this.name},
        getSheetId(){return this.id},
        getLastRow(){return this.rows.length},
        getRange(row,_column,_height,_width){
          return {
            getValues:()=>name==='Meta'?[meta.slice()]:sheet.rows.slice(row-1),
            setValues:values=>{
              if(options.failSet?.(name,row))throw new Error('Simulated Sheet write failure');
              if(name==='Meta')meta=[...values[0]];
              else values.forEach((value,index)=>{sheet.rows[row-1+index]=value});
            },
          };
        },
        hideSheet(){},
      };
      sheets.set(name,sheet);
      return sheet;
    },
    deleteSheet(sheet){
      assert.equal(sheets.get(sheet.getName())?.getSheetId(),sheet.getSheetId());
      deleted.push(sheet.getName());
      sheets.delete(sheet.getName());
    },
  };
  workbook.insertSheet('Meta');
  const state=workbook.insertSheet('State_v11');
  state.rows=[['Type','ID or path','JSON'],['item','A-1',JSON.stringify(item)],['category','Foundation',JSON.stringify({path:['Foundation']})]];
  const source=workbook.insertSheet('Source_v1');
  source.rows=[['Type','ID or path','JSON'],['item','A-1',JSON.stringify(item)]];
  const context=vm.createContext({
    SpreadsheetApp:{getActiveSpreadsheet:()=>workbook,flush(){if(options.failFlush)throw new Error('Simulated flush failure')}},
    ContentService:{createTextOutput:text=>({text})},
  });
  vm.runInContext(code,context);
  return {context,workbook,deleted,getMeta:()=>meta.slice()};
}

{
  const {context,workbook,deleted,getMeta}=fixture({failSet:(name,row)=>name==='State_v12'&&row===2});
  assert.throws(()=>context.writeState_({items:[item],categories:[{path:['Foundation']}]},12,'next-nonce','Editor'),/Simulated Sheet write failure/);
  assert.equal(workbook.getSheetByName('State_v12'),null,'A newly created unreferenced state is removed');
  assert.deepEqual(deleted,['State_v12']);
  assert.deepEqual(getMeta(),initialMeta,'Meta remains on the prior revision');
}

{
  const {context,workbook,deleted,getMeta}=fixture({failFlush:true});
  assert.throws(()=>context.writeState_({items:[item],categories:[{path:['Foundation']}]},12,'next-nonce','Editor'),/Simulated flush failure/);
  assert.ok(workbook.getSheetByName('State_v12'),'A state referenced by Meta is retained even after a flush error');
  assert.deepEqual(deleted,[]);
  assert.equal(getMeta()[0],'State_v12');
}

{
  const {context,workbook,deleted,getMeta}=fixture({failSet:(name,row)=>name==='Source_v12'&&row===2});
  assert.throws(()=>context.source_({revision:'11',nonce:'next-nonce-12',sourceHash:'b'.repeat(64),payload:JSON.stringify({items:[item]})}),/Simulated Sheet write failure/);
  assert.equal(workbook.getSheetByName('Source_v12'),null,'A newly created unreferenced source is removed');
  assert.deepEqual(deleted,['Source_v12']);
  assert.deepEqual(getMeta(),initialMeta);
}

{
  const {context,workbook,deleted,getMeta}=fixture({failSet:(name,row)=>name==='State_v12'&&row===2});
  assert.throws(()=>context.source_({revision:'11',nonce:'next-nonce-12',sourceHash:'b'.repeat(64),payload:JSON.stringify({items:[item]})}),/Simulated Sheet write failure/);
  assert.equal(workbook.getSheetByName('State_v12'),null);
  assert.equal(workbook.getSheetByName('Source_v12'),null);
  assert.deepEqual(deleted,['State_v12','Source_v12']);
  assert.deepEqual(getMeta(),initialMeta);
}

{
  const {context,workbook,deleted,getMeta}=fixture({failFlush:true});
  assert.throws(()=>context.source_({revision:'11',nonce:'next-nonce-12',sourceHash:'b'.repeat(64),payload:JSON.stringify({items:[item]})}),/Simulated flush failure/);
  assert.ok(workbook.getSheetByName('State_v12'),'A committed state is never deleted');
  assert.ok(workbook.getSheetByName('Source_v12'),'A source referenced by Meta is never deleted');
  assert.deepEqual(deleted,[]);
  assert.equal(getMeta()[0],'State_v12');
  assert.equal(getMeta()[5],'Source_v12');
}

{
  const {context,workbook,deleted}=fixture();
  const actual=workbook.insertSheet('State_v12');
  const wrongIdentity={getName:()=>actual.getName(),getSheetId:()=>actual.getSheetId()+1};
  assert.equal(context.rollbackCreatedSheetIfUnreferenced_(wrongIdentity,context.meta_()),false);
  assert.ok(workbook.getSheetByName('State_v12'),'Cleanup never deletes a same-named sheet it did not create');
  assert.deepEqual(deleted,[]);
}

console.log('PASS: failed Sheet writes remove only newly created, unreferenced revision tabs.');
