import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import ExcelJS from 'exceljs';

const output=new URL('../outputs/NeoviBOM/',import.meta.url);
export async function verifyExports(expected){
  const json=JSON.parse(await fs.readFile(new URL('NeoviBOM.json',output),'utf8'));
  if (!expected) {
    const { createSnapshot } = await import('./export-data.mjs');
    expected=await createSnapshot();
  }
  expected.generatedAt=json.generatedAt;
  assert.deepEqual(json,expected,'JSON must preserve all source values and evidence');
  const book=new ExcelJS.Workbook();
  await book.xlsx.readFile(fileURLToPath(new URL('NeoviBOM.xlsx',output)));
  const master=book.getWorksheet('Master Catalog');
  assert.equal(master.rowCount,json.items.length+1);
  for(const [index,item] of json.items.entries()){
    const row=master.getRow(index+2);
    assert.equal(row.getCell(1).value,item.catalogId);
    assert.equal(row.getCell(2).value,item.description);
    assert.equal(row.getCell(4).value,item.unit);
    assert.equal(row.getCell(7).value,item.categoryPath.join(' > '));
    assert.equal(row.getCell(18).value,item.quantityBasis);
  }
  let quantityChecks=0,zeroChecks=0,unknownChecks=0;
  const fields=['required','spare','baseKit','kit','totalItemDemand','onHand','committed','targetStock','net','packSize','minimumOrder','order','unitCost','cost','planningEstimate','planningSpare','planningBaseKit'];
  for(const project of json.projects){
    const sheet=book.getWorksheet(project.name);
    assert.equal(sheet.rowCount,project.rows.length+1);
    for(const [index,row] of project.rows.entries()){
      assert.equal(sheet.getCell(index+2,1).value,row.catalogId);
      assert.equal(sheet.getCell(index+2,4).value,row.unit);
      for(const [fieldIndex,key] of fields.entries()){
        assert.equal(sheet.getCell(index+2,9+fieldIndex).value,row[key]??'N/A',`${project.name}/${row.lineId}/${key}`);
        quantityChecks++;if(row[key]===0)zeroChecks++;if(row[key]===null)unknownChecks++;
      }
    }
  }
  const comparison=book.getWorksheet('Project Comparison');
  assert.equal(comparison.rowCount,json.items.length+1);
  for(const [i,item] of json.items.entries())for(const [j,p] of json.projects.entries()){
    const row=p.rows.find(r=>r.lineId===item.lineId);
    for(const [k,field] of ['required','planningEstimate','baseKit','mappingStatus'].entries())assert.equal(comparison.getCell(i+2,8+j*4+k).value,row[field]??'N/A');
  }
  for(const sheet of book.worksheets.filter(s=>s.name!=='Read Me')){
    assert.equal(Object.keys(sheet.tables).length,1,`${sheet.name} needs a filter table`);
    assert.equal(sheet.views[0].ySplit,1);assert.equal(sheet.views[0].xSplit,2);
  }
  assert.equal(book.getWorksheet('Assumptions').rowCount,Object.keys(json.planningAssumptions.rules).filter(id=>json.items.some(i=>i.lineId===id)).length+1);
  assert(zeroChecks>0 && unknownChecks>0,'Exercise both real zeros and unknown quantities');
  const result={status:'PASS',items:json.items.length,projects:json.projects.length,sheets:book.worksheets.length,quantityChecks,zeroChecks,unknownChecks,completeJsonSourceParity:true};
  await fs.writeFile(new URL('04-Audits/Data-Export-Verification.json',output),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result));
}
if(process.argv[1]===fileURLToPath(import.meta.url))await verifyExports();
