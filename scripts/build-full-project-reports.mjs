import fs from "node:fs/promises";
import path from "node:path";
import { loadTemplateConfig } from "../src/template-model.mjs";
import { projectQuantityRows } from "../src/project-quantity-report.mjs";
import { roundUpTo } from "../src/calculations.mjs";

const { lines } = await loadTemplateConfig();
const folder = path.resolve("outputs/NeoviBOM/_Internal/Model-Data");
// Use current scan metadata, never the old synthetic arithmetic-test snapshot.
const audit = {projects: await Promise.all(['franklin','santa-rita'].map(async slug => {
  const scan = JSON.parse(await fs.readFile(path.join(folder, `${slug}-evidence.json`), 'utf8'));
  return {project:scan.metadata['project.title'],source:scan.source,bytes:scan.bytes,
    exportedAt:scan.metadata.exportedAtUtc,elementCount:scan.elementCount,
    bomTaggedElements:scan.bomTaggedElements.length,candidates:scan.roofAreaTestCandidates,
    duplicateElementKeys:scan.duplicateElementKeys,roofExclusions:scan.roofExclusions};
}))};
const fields = [
  ['Catalog ID','catalogId'], ['Category Path','categoryPath'],
  ['Planning Estimate Qty','planningEstimate'], ['Planning Estimate Formula','planningFormula'], ['Planning Assumption','planningAssumption'], ['Planning Base Kit','planningBaseKit'], ['Planning Driver Sources','planningSources'],
  ["Project", "project"], ["Phase", "phase"], ["Stage", "deliveryStage"], ["Category Section", "categorySection"],
  ["Work Area", "workArea"], ["Category", "category"], ["Specific Category", "system"], ["Line ID", "lineId"], ["Item ID", "itemId"],
  ["Item", "item"], ["Unit", "unit"], ["Model Source", "sourceReferences"],
  ["Required Formula", "requiredFormula"], ["Required Qty", "required"],
  ["Spare Formula", "spareFormula"], ["Spare Qty", "spare"], ["Kit Formula", "kitFormula"], ["Kit Qty", "kit"],
  ["Base Kit Formula (excludes extras)", "baseKitFormula"], ["Base Kit Qty (excludes extras)", "baseKit"],
  ["Item Demand Formula", "totalFormula"], ["Total Item Demand", "totalItemDemand"],
  ["On Hand", "onHand"], ["Committed", "committed"], ["Target Stock", "targetStock"],
  ["Net Formula", "netFormula"], ["Net Need", "net"], ["Pack Size", "packSize"], ["Minimum Order", "minimumOrder"],
  ["Order Formula", "orderFormula"], ["Order Qty", "order"], ["Unit Cost", "unitCost"],
  ["Cost Formula", "costFormula"], ["Extended Cost", "cost"], ["Catalog Assumptions", "assumptions"], ["N/A Reason", "reason"],
  ["Mapping Status", "mappingStatus"], ["Candidate Elements (not quantity)", "candidateCount"], ["Takeoff Requirement", "takeoffRequirement"], ["Catalog Allowance (not model quantity)", "catalogAllowance"],
];
const csvCell = value => `"${String(value ?? "N/A").replaceAll('"', '""')}"`;
const display = value => Number(value.toFixed(6)).toString();
const projects = [];
const specificReasons = {
  'PAN-007': 'Froth-Pak fills 1/2-inch floor cassette gaps; joint length and fill depth must be established.',
  'PAN-008': 'Catalog allows 1 lifting rig; model does not establish crew equipment needs. Allowance remains visible in formula.',
  'PAN-009': 'Wall framing/connection families exist, but their mapping to the four-screws-per-connection rule is unresolved.',
  'PAN-010': 'Temporary bracing connection count and 4-inch screws per connection are needed.',
  'PAN-011': 'Angle/clip families exist; which need these nuts and the nuts-per-angle rule are unresolved.',
  'PAN-012': 'Temporary site bracing is not identified in the inspected families; count needs a bracing layout.',
  'PAN-014': 'Floor plates and other clips exist; a separate wall-to-wall plate selection has not been established.',
  'PAN-015': 'Corner foam requires joint height, gap width and depth; no complete volume takeoff established.',
  'PAN-016': 'Truss members exist, but member count is not screw count. Connection/fastener selection is unresolved.',
  'PAN-017': 'Angle/clip families exist; the truss-angle subset has not been established.',
  'PAN-018': 'Truss framing exists; stitch-piece families and quantities have not been identified.',
};
for (const project of audit.projects) {
  // The scan found no BOM-tagged input rows. Roof candidates are deliberately
  // not treated as verified quantities for the catalog's slope-material item.
  if (project.bomTaggedElements !== 0) throw new Error("New BOM evidence must be mapped and reviewed before building this report.");
  const evidenceSlug = project.project.includes("Santa Rita") ? "santa-rita" : "franklin";
  const mapped = JSON.parse(await fs.readFile(path.join(folder, `${evidenceSlug}-mapped-takeoffs.json`), "utf8"));
  const openingTakeoffs = JSON.parse(await fs.readFile(path.join(folder, `${evidenceSlug}-opening-takeoffs.json`), "utf8"));
  const mappingAudit = JSON.parse(await fs.readFile(path.join(folder, `${evidenceSlug}-all-item-mapping-audit.json`), "utf8"));
  const planning = JSON.parse(await fs.readFile(path.join(folder, `${evidenceSlug}-planning-estimates.json`), 'utf8'));
  if (mappingAudit.length !== lines.length) throw new Error('Incomplete item mapping audit');
  const auditByLine = new Map(mappingAudit.map(entry => [entry.lineId, entry]));
  let purchasing = {};
  try {
    purchasing = JSON.parse(await fs.readFile(path.join(folder, `${evidenceSlug}-purchasing-inputs.json`), "utf8"));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const rows = projectQuantityRows(lines, new Map(Object.entries(mapped)), new Map(Object.entries(purchasing))).map(row => {
    const evidence = mapped[row.lineId];
    if (specificReasons[row.lineId]) row.reason = specificReasons[row.lineId];
    if (evidence) {
      row.requiredFormula = `R = ${evidence.formula} = ${display(evidence.value)} ${row.unit}`;
      const rule = lines.find(line => line.lineId === row.lineId);
      row.spareFormula = `S = up(${display(row.required)} x ${rule.sparePercent * 100}%, ${rule.quantityIncrement}) = ${row.spare}`;
      row.baseKitFormula = `Base kit = up(MAX(${display(row.required)} + ${row.spare}, ${rule.minimumKitQty}), ${rule.quantityIncrement}) = ${row.baseKit}; excludes extras`;
      row.reason = `Model quantity from ${evidence.description}; confirm installation scope/specification. Extras, inventory, packs and prices unavailable.`;
      row.assumptions += " Spare is a catalog-rule calculation, not an approved allowance.";
      if (row.lineId === 'PAN-013') {
        row.reason = `Derived from ${evidence.value} modeled hold-downs x 1 complete washer/nut assembly per catalog. Spare = ceil(${evidence.value} x 10%) = ${row.spare}. Hardware sizes and project extras need confirmation.`;
      }
    }
    const review = auditByLine.get(row.lineId);
    if (!review) throw new Error(`Missing mapping audit for ${row.lineId}`);
    row.reason = review.reason;
    if (row.lineId==='FIN-085' && openingTakeoffs.exteriorDoorJointLength !== null) {
      row.requiredFormula=`R = ${openingTakeoffs.exteriorDoorJointLength.toFixed(3)} FT joint x gap width IN x fill depth IN / 144`;
      row.reason='Door joint length calculated from opening dimensions. Only installation gap width and fill depth are missing; door leaf/frame clearance is not the foam gap.';
    }
    if (['FIN-089','FIN-090'].includes(row.lineId) && openingTakeoffs.windowPerimeter !== null) {
      const n=openingTakeoffs.windowPerimeter.toFixed(3);
      row.requiredFormula=row.lineId==='FIN-090'?`R = ${n} FT joint x gap width IN x fill depth IN / 144`:`R = ceil(${n} FT joint x bead area SQIN x 12 / 1.8046875 FL OZ / selected cartridge FL OZ) EA`;
      row.reason='Window joint perimeter calculated from opening dimensions. Fill/bead cross-section still required; window trim side multiplier does not multiply the physical gap.';
    }
    const estimate = row.required === null ? planning.estimates[row.lineId] : null;
    const rule=lines.find(line=>line.lineId===row.lineId);
    const planningEstimate=estimate ? roundUpTo(estimate.value,rule.quantityIncrement) : null;
    const planningSpare=estimate ? roundUpTo(planningEstimate*rule.sparePercent,rule.quantityIncrement) : null;
    const planningBaseKit=estimate ? roundUpTo(Math.max(planningEstimate+planningSpare,rule.minimumKitQty),rule.quantityIncrement) : null;
    return { ...row, planningEstimate, planningSpare, planningBaseKit,
      planningFormula:estimate ? `Estimate = up(${estimate.formula}, ${rule.quantityIncrement}) = ${planningEstimate}; spare = ${planningSpare}; base kit = ${planningBaseKit}` : null,
      planningAssumption:estimate?.assumption ?? null, planningSources:estimate?.references.join('; ') ?? null,
      project: project.project, mappingStatus:review.status, candidateCount:review.candidateCount,
      takeoffRequirement:review.requirement, sourceGroups:review.sourceGroups, catalogAllowance:review.catalogAllowance };
  }).sort((a,b) => a.deliveryStage - b.deliveryStage || a.categorySection.localeCompare(b.categorySection, undefined, {numeric: true}) || a.lineId.localeCompare(b.lineId));
  const slug = project.project.includes("Santa Rita") ? "Santa-Rita" : "Franklin";
  const csv = [fields.map(([title]) => title), ...rows.map(row => fields.map(([, key]) => row[key]))]
    .map(row => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
  await fs.writeFile(path.join(folder, `${slug}-All-Items-Calculations.csv`), csv);
  const circuits=[['Line','Source Key','Panel','Circuit','Load','Cable Size','Cable Type','Length FT','Runs','Poles','Rating'],
    ...Object.entries(mapped).flatMap(([lid,e])=>(e.circuitDetails??[]).map(c=>[lid,c.key,c.panel,c.circuit,c.load,c.cableSize,c.cableType,c.lengthFt,c.runs,c.poles,c.rating]))];
  await fs.writeFile(path.join(folder,`${slug}-Circuit-Evidence.csv`),circuits.map(r=>r.map(csvCell).join(',')).join('\r\n'));
  const dimensionRows=[['Source Element','Category','Type','Host Wall','Wall Function (0 interior, 1 exterior)','Sides','Width FT','Height FT','Head + Jambs FT','Perimeter FT'],
    ...openingTakeoffs.openings.map(e=>[e.key,e.category,e.type,e.hostWall,e.wallFunction,e.sides,e.width,e.height,e.headAndJambLength,e.perimeter])];
  await fs.writeFile(path.join(folder,`${slug}-Opening-Dimensions.csv`),dimensionRows.map(r=>r.map(csvCell).join(',')).join('\r\n'));
  const wallRows=[['Source Element','Wall Type','Classification','Length FT','Sides','Trim Length FT'],
    ...(openingTakeoffs.supplemental['WALL-TRIM']?.wallDetails ?? []).map(w=>[w.key,w.type,w.classification,w.length,w.sides,w.trimLength])];
  await fs.writeFile(path.join(folder,`${slug}-Wall-Trim.csv`),wallRows.map(r=>r.map(csvCell).join(',')).join('\r\n'));
  projects.push({ ...project, rows, mapped, mappingAudit, openingTakeoffs, planning });
}
await fs.writeFile(path.join(folder, "full-project-calculations.json"), JSON.stringify({ projects }, null, 2));
console.log(`Built full reports: ${projects.length} projects, ${lines.length} items each; unresolved results remain N/A.`);
