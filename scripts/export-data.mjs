// Public software/review exports share one validated snapshot.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import ExcelJS from 'exceljs';
import { loadTemplateConfig } from '../src/template-model.mjs';
import { quantityBasis } from '../src/quantity-explanations.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'outputs/NeoviBOM');
const read = async name => JSON.parse(await fs.readFile(path.join(root, name), 'utf8'));
const quantityFields = ['required','spare','baseKit','kit','totalItemDemand','onHand','committed','targetStock','net','packSize','minimumOrder','order','unitCost','cost','planningEstimate','planningSpare','planningBaseKit'];
const labels = {
  required:'Required Quantity', spare:'Spare Quantity', baseKit:'Base Kit Quantity', kit:'Final Kit Quantity',
  totalItemDemand:'Total Item Demand', onHand:'On Hand', committed:'Already Committed', targetStock:'Target Stock',
  net:'Net Quantity', packSize:'Pack Size', minimumOrder:'Minimum Order', order:'Order Quantity', unitCost:'Unit Cost', cost:'Extended Cost',
  planningEstimate:'Planning Estimate', planningSpare:'Planning Spare', planningBaseKit:'Planning Base Kit',
};
function fullFormula(text = '') {
  if (text === null) return null;
  const names={R:'Required Quantity',S:'Spare Quantity',K:'Kit Quantity',E:'Manual Extra',D:'Total Item Demand',N:'Net Quantity',O:'Order Quantity'};
  return text.replace(/\b[RSKEDNO]\b/g, value => names[value] ?? value).replace(/\bup\(/g,'Round up(');
}
export function validateSnapshot(snapshot) {
  const catalog = new Map(snapshot.items.map(item => [item.lineId,item]));
  if (catalog.size !== snapshot.items.length || new Set(snapshot.items.map(i=>i.catalogId)).size !== catalog.size) throw new Error('Duplicate item identity');
  for (const project of snapshot.projects) {
    if (project.rows.length !== catalog.size || new Set(project.rows.map(r=>r.lineId)).size !== catalog.size) throw new Error(`Incomplete project: ${project.name}`);
    for (const row of project.rows) {
      const item=catalog.get(row.lineId);
      if (!item || row.catalogId!==item.catalogId || row.unit!==item.unit || row.item!==item.description || row.categoryPath!==item.categoryPath.join(' > ')) throw new Error(`Stale project row: ${row.lineId}; rebuild project reports first`);
      for (const field of quantityFields) if (row[field]!==null && (typeof row[field]!=='number' || !Number.isFinite(row[field]))) throw new Error(`Invalid ${field}: ${row.lineId}`);
    }
  }
  return snapshot;
}
export async function createSnapshot() {
  const { config, lines } = await loadTemplateConfig();
  assert.deepEqual(await read('outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json'),lines,'Catalog changed since project calculations; rebuild project reports before exporting');
  const calculations = await read('outputs/NeoviBOM/_Internal/Model-Data/full-project-calculations.json');
  const planning = await read('config/planning-allowances.json');
  return validateSnapshot({
    schemaId:'neovi.site-bom.export', schemaVersion:'1.0', generatedAt:new Date().toISOString(),
    catalogVersion:config.settings.templateVersion,
    semantics:{
      missingQuantity:'null means unknown or unavailable; zero means a calculated or explicitly supplied zero.',
      identity:'catalogId is permanent; lineId is the legacy line reference; categoryPath is an ordered array.',
      quantities:'required includes model measurements, derived allowances and confirmed standards; inspect mappingStatus and sourceReferences.',
      estimates:'planningEstimate is separate from required; it is not a measured quantity or an order.',
      formulas:'Human-readable explanations; calculations use the repository rules. Workbook exports are review snapshots, not an editable purchasing model.',
      units:'Numeric quantities use each item unit; do not sum unlike units.',
    },
    items:lines.map(line=>({...line,quantityBasis:quantityBasis(line)})),
    projects:calculations.projects.map(project=>({
      id:project.project.includes('Santa Rita')?'santa-rita':'franklin',
      name:project.project.includes('Santa Rita')?'Santa Rita':'Franklin',
      modelName:project.project, source:project.source, sourceBytes:project.bytes,
      exportedAt:project.exportedAt, elementCount:project.elementCount,
      rows:project.rows.map(row=>Object.fromEntries(Object.entries(row).map(([key,value])=>[key,key.endsWith('Formula')?fullFormula(value):value]))),
    })),
    planningAssumptions:planning,
    confirmedStandards:await read('config/confirmed-site-standards.json'),
  });
}
// Excel's cell limit must not truncate JSON evidence. Long Excel cells point to it.
function cell(value) {
  if (value===null || value===undefined) return 'N/A';
  if (typeof value==='object') value=JSON.stringify(value);
  return typeof value==='string' && value.length>32000 ? value.slice(0,31800)+'\n[Full evidence in NeoviBOM.json]' : value;
}
function table(book, name, headers, rows, widths={}) {
  const sheet=book.addWorksheet(name,{views:[{state:'frozen',xSplit:2,ySplit:1,showGridLines:false}]});
  sheet.addTable({name:name.replace(/[^A-Za-z0-9]/g,''),ref:'A1',headerRow:true,
    style:{theme:'TableStyleMedium2',showRowStripes:true},
    columns:headers.map(name=>({name,filterButton:true})), rows:rows.map(row=>row.map(cell))});
  sheet.columns.forEach((column,index)=>{column.width=widths[headers[index]] ?? (/Item|Formula|Reason|Notes|Assumption|Source|Specification|Path/.test(headers[index])?48:22);column.alignment={vertical:'top',wrapText:true};});
  sheet.eachRow((row,index)=>{
    row.height=index===1?42:42;
    row.eachCell(c=>{c.font={name:'Calibri',size:11,color:{argb:index===1?'FFFFFFFF':'FF223347'},bold:index===1};if(typeof c.value==='number')c.numFmt='0.###';});
  });
  sheet.pageSetup={orientation:'landscape',fitToPage:true,fitToWidth:1,fitToHeight:0,printTitlesRow:'1:1'};
  return sheet;
}
export async function createWorkbook(snapshot) {
  const book=new ExcelJS.Workbook();book.creator='NeoviBOM';book.created=new Date(snapshot.generatedAt);
  const about=book.addWorksheet('Read Me',{views:[{showGridLines:false}]});
  about.columns=[{width:27},{width:105}];
  const instructions=[['NeoviBOM','Catalog and project data'],['Generated',snapshot.generatedAt],['Contents',`${snapshot.items.length} catalog items; ${snapshot.projects.length} projects. Filter any table by category, phase, stage or item ID.`],['Master Catalog','Permanent IDs, nested categories, units, specifications and complete quantity explanations.'],['Project Comparison','Required quantities and planning estimates side by side. N/A means unavailable; 0 is a real zero.'],['Project tabs','Full quantities, status and formula explanations. Source details are retained in the JSON export.'],['Needs Review','Rows missing takeoffs, purchasing inputs or approved specifications/rules; an estimate does not clear review.'],['Assumptions','Reference snapshot of planning rates. Edit config/planning-allowances.json and rebuild to change the source assumptions.'],['Editing','This workbook is an exported snapshot. Spreadsheet edits are not imported into the software and do not recalculate the source model.'],['JSON','NeoviBOM.json contains typed numbers, nulls, complete project rows, evidence references and the same catalog.'],['Lifting straps','RIG-2 has no confirmed length variants. Example sizes are not catalog requirements.']];
  for(const values of instructions){const row=about.addRow(values);row.height=48;row.alignment={vertical:'top',wrapText:true};row.font={name:'Calibri',size:11};row.getCell(1).font={name:'Calibri',size:11,bold:true};}
  about.getRow(1).font={name:'Calibri',size:18,bold:true,color:{argb:'FF1F4E78'}};
  table(book,'Master Catalog',['Catalog ID','Item','Legacy Line ID','Unit','Category','Subcategory','Category Path','Phase','Stage','Section','Work Area','System','Procurement','Optional','Specification','Specification Approved','Rule Status','Quantity Formula','Spare Percent','Quantity Increment','Minimum Kit','Pack Size','Notes'],snapshot.items.map(i=>[
    i.catalogId,i.description,i.lineId,i.unit,i.categoryPath[0],i.categoryPath[1],i.categoryPath.join(' > '),i.phase,i.deliveryStage,i.categorySection,i.stage,i.system,i.procurementMethod,i.optional,i.specification,i.specificationApproved,i.ruleStatus,i.quantityBasis,i.sparePercent,i.quantityIncrement,i.minimumKitQty,i.packSize,[i.itemNotes,i.ruleNotes,i.lineNotes].filter(Boolean).join('; '),
  ]));
  book.getWorksheet('Master Catalog').getColumn(19).numFmt='0%';
  const projectMaps=snapshot.projects.map(p=>new Map(p.rows.map(r=>[r.lineId,r])));
  table(book,'Project Comparison',['Catalog ID','Item','Unit','Category','Subcategory','Phase','Stage',...snapshot.projects.flatMap(p=>[`${p.name} Required`,`${p.name} Planning Estimate`,`${p.name} Base Kit`,`${p.name} Status`])],snapshot.items.map(i=>[
    i.catalogId,i.description,i.unit,i.categoryPath[0],i.categoryPath[1],i.phase,i.deliveryStage,...projectMaps.flatMap(p=>{const r=p.get(i.lineId);return [r.required,r.planningEstimate,r.baseKit,r.mappingStatus];}),
  ]));
  const review=[];
  const byId=new Map(snapshot.items.map(i=>[i.lineId,i]));
  const formulaFields=['requiredFormula','spareFormula','baseKitFormula','kitFormula','totalFormula','netFormula','orderFormula','costFormula','planningFormula'];
  for(const p of snapshot.projects){
    table(book,p.name,['Catalog ID','Item','Legacy Line ID','Unit','Category Path','Phase','Stage','Section',...quantityFields.map(f=>labels[f]),'Mapping Status','Reason',...formulaFields.map(f=>f.replace(/([A-Z])/g,' $1').replace(/^./,c=>c.toUpperCase())),'Source References','Planning Assumption','Planning Sources'],p.rows.map(r=>[
      r.catalogId,r.item,r.lineId,r.unit,r.categoryPath,r.phase,r.deliveryStage,r.categorySection,...quantityFields.map(f=>r[f]),r.mappingStatus,r.reason,...formulaFields.map(f=>r[f]),r.sourceReferences,r.planningAssumption,r.planningSources,
    ]));
    for(const r of p.rows){
      const i=byId.get(r.lineId), issues=[];
      if(r.required===null)issues.push('Required quantity unavailable');
      if(r.order===null)issues.push('Order quantity unavailable');
      if(r.cost===null)issues.push('Cost unavailable');
      if(!i.specificationApproved)issues.push('Specification not approved');
      if(i.ruleStatus!=='APPROVED')issues.push(`Rule: ${i.ruleStatus}`);
      if(issues.length)review.push([r.catalogId,r.item,p.name,r.unit,r.required,r.planningEstimate,issues.join('; '),r.mappingStatus,r.reason]);
    }
  }
  table(book,'Needs Review',['Catalog ID','Item','Project','Unit','Required Quantity','Planning Estimate','Review Reason','Mapping Status','Source Reason'],review);
  table(book,'Assumptions',['Catalog ID','Item','Legacy Line ID','Unit','Driver','Rate','Planning Assumption'],Object.entries(snapshot.planningAssumptions.rules).filter(([id])=>byId.has(id)).map(([id,r])=>{const i=byId.get(id);return[i.catalogId,i.description,id,i.unit,r.driver,r.rate,r.assumption];}));
  return book;
}
export async function exportData(){
  const snapshot=await createSnapshot();
  await fs.mkdir(output,{recursive:true});
  await fs.writeFile(path.join(output,'NeoviBOM.json'),JSON.stringify(snapshot,null,2)+'\n');
  const workbook=await createWorkbook(snapshot);
  await workbook.xlsx.writeFile(path.join(output,'NeoviBOM.xlsx'));
  const { verifyExports } = await import('./verify-data-exports.mjs');
  await verifyExports(snapshot);
  console.log(`Exported NeoviBOM.xlsx and NeoviBOM.json: ${snapshot.items.length} items, ${snapshot.projects.length} projects.`);
}
if(process.argv[1]===fileURLToPath(import.meta.url))await exportData();
