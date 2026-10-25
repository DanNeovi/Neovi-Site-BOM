import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
export async function buildViewer(snapshot) {
  const output = path.join(root, 'outputs/NeoviBOM');
  snapshot ??= JSON.parse(await fs.readFile(path.join(output, 'NeoviBOM.json'), 'utf8'));
  const monroeText = await fs.readFile(path.join(output, '05-Monroe/Monroe-Item-Formulas.json'), 'utf8')
    .catch(error => { if (error.code === 'ENOENT') return null; throw error; });
  const monroeById = new Map((monroeText ? JSON.parse(monroeText).items : []).map(item => [item.lineId, {
    quantity: item.quantity, unit: item.unit, basis: item.basis,
    formula: item.formula, assumption: item.assumption,
    baseKitQuantity: item.baseKitQuantity,
    averageMetrics: item.averageMetrics, storyAllocation: item.storyAllocation || null,
  }]));
  const checklist = JSON.parse(await fs.readFile(path.join(root, 'config/site-bom-checklist.json'), 'utf8'));
  const originals = new Map(snapshot.items.map(item => [item.lineId, item]));
  const allowedStages = new Set(['Site Setup','Shared Foundation Support','Helical Piles','Bedframe']);
  const allowedGroups = new Set(['Site services','Equipment','Supplemental','Materials','Tools','Consumables']);
  const rowIds = new Set();
  const partTypes = new Map();
  for (const row of checklist.rows) {
    if (!row.id || rowIds.has(row.id) || originals.has(row.id)) throw new Error('Duplicate checklist ID: ' + row.id);
    rowIds.add(row.id);
    if (!allowedStages.has(row.stage) || !allowedGroups.has(row.group)) throw new Error('Invalid checklist hierarchy: ' + row.id);
    if (!row.description?.trim() || !row.unit?.trim()) throw new Error('Incomplete checklist entry: ' + row.id);
    if (row.purchaseType) {
      const signature = JSON.stringify([row.description, row.unit, row.specification]);
      if (partTypes.has(row.purchaseType) && partTypes.get(row.purchaseType) !== signature) throw new Error('Conflicting shared part type: ' + row.purchaseType);
      partTypes.set(row.purchaseType, signature);
    }
  }
  for (const id of checklist.additionalRepresentedReferences) if (!originals.has(id)) throw new Error('Unknown represented reference: ' + id);
  const represented = new Set([...checklist.rows.map(row => row.reference).filter(Boolean), ...checklist.additionalRepresentedReferences]);
  const sheetItems = checklist.rows.map((row, index) => {
    const base = originals.get(row.reference) || {};
    if (row.reference && !originals.has(row.reference)) throw new Error('Unknown checklist reference: ' + row.reference);
    if (row.quantity !== null && (!Number.isFinite(row.quantity) || row.quantity < 0)) throw new Error('Invalid checklist quantity: ' + row.id);
    const phase = row.stage === 'Site Setup' ? 'Site Setup' : 'Foundation';
    const stageOrder = ['Site Setup', 'Shared Foundation Support', 'Helical Piles', 'Bedframe'].indexOf(row.stage);
    return {...base, lineId: row.id, itemId: row.id, catalogId: row.id, sourceCatalogId: base.catalogId || null,
      description: row.description, phase, phaseOrder: phase === 'Site Setup' ? 0 : 1,
      stage: row.stage, stageOrder, categoryOrder: index, sourceOrdinal: [phase === 'Site Setup' ? 0 : 1, stageOrder, index, 0],
      categoryPath: base.categoryPath || [row.group, row.stage],
      inventoryPrefix: base.inventoryPrefix || ({Equipment:'EQUIP', Tools:'TOOL', Consumables:'SUP', Supplemental:'TOOL'})[row.group] || 'MAT',
      system: row.group, checklistGroup: row.group, unit: row.unit,
      specification: row.specification || base.specification || 'N/A',
      listedQuantity: row.quantity, purchaseType: row.purchaseType,
      checklistSource: checklist.source, quantityMeaning: checklist.quantityMeaning,
      originalLineId: row.reference || null, kitId: 'N/A', sourceKitId: base.kitId || null,
      monroeEstimate: monroeById.get(row.reference) || null,
      itemNotes: base.itemNotes || '', lineNotes: base.lineNotes || ''};
  });
  // The sheet provides a layout and reference entries, not an exhaustive phase inventory.
  // Keep every other catalog item in its active work package.
  const foundationStages = {
    'Site Setup and Support': ['Shared Foundation Support', 1],
    'Helical Piles': ['Helical Piles', 2],
    'Steel Bedframe': ['Bedframe', 3],
  };
  const remaining = snapshot.items.filter(item => !represented.has(item.lineId)).map(item => {
    const stage = item.phase === 'Foundation' && foundationStages[item.stage];
    const withEstimate = {...item, monroeEstimate: monroeById.get(item.lineId) || null};
    return stage ? {...withEstimate, originalStage:item.stage, stage:stage[0], stageOrder:stage[1]} : withEstimate;
  });
  const viewerItems = [...sheetItems, ...remaining];
  if (new Set(viewerItems.map(i=>i.catalogId)).size !== viewerItems.length) throw new Error('Duplicate viewer catalog identity');
  const documents = [];
  async function walk(dir) {
    for (const entry of await fs.readdir(path.join(output, dir), { withFileTypes: true })) {
      const relative = path.posix.join(dir, entry.name);
      if (entry.isDirectory()) await walk(relative);
      else if (entry.name.toLowerCase() !== 'desktop.ini') documents.push({ path: relative, name: entry.name, group: dir.split('/')[0] });
    }
  }
  for (const dir of ['01-Catalog', '02-Projects', '03-Categories', '04-Audits', '05-Google-Sheet']) await walk(dir);
  if (await fs.stat(path.join(output, '05-Monroe')).catch(() => null)) await walk('05-Monroe');
  const template = await fs.readFile(path.join(root, 'viewer/index.html'), 'utf8');
  const payload = JSON.stringify({ ...snapshot, items: viewerItems, checklist, viewerGeneratedAt: new Date().toISOString(), documents }).replaceAll('<', '\\u003c');
  await fs.writeFile(path.join(output, 'NeoviBOM.html'), template.replace('/*__SNAPSHOT__*/', () => payload));
  console.log(`Built offline viewer: ${viewerItems.length} checklist/catalog entries, ${snapshot.projects.length} projects, ${documents.length} documents.`);
}
if (process.argv[1] === fileURLToPath(import.meta.url)) await buildViewer();
