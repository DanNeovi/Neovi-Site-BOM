// Append-only identity allocation. Decimal strings/BigInt have no fixed digit width.
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
export function assignIdentities(items, registry = { schemaVersion: 1, next: {}, entries: {} }) {
  const active = new Set(items.map(item => item.id));
  const used = new Set(Object.values(registry.entries).map(e => e.catalogId));
  if (active.size !== items.length) throw new Error('Duplicate legacy item IDs');
  if (used.size !== Object.keys(registry.entries).length) throw new Error('Duplicate permanent catalog IDs in registry');
  for (const item of items) {
    if (!/^[A-Z]+$/.test(item.inventoryPrefix ?? '') || !Array.isArray(item.categoryPath) || item.categoryPath.length < 2) {
      throw new Error(`${item.id}: specify inventoryPrefix and categoryPath before allocating an identifier`);
    }
    let entry = registry.entries[item.id];
    if (!entry) {
      const prefix = item.inventoryPrefix;
      let number = BigInt(registry.next[prefix] ?? '1');
      while (used.has(`${prefix}-${number}`)) number++;
      entry = registry.entries[item.id] = { catalogId: `${prefix}-${number}`, status: 'active' };
      registry.next[prefix] = String(number + 1n);
      used.add(entry.catalogId);
    }
    entry.status = 'active';
    entry.description = item.description;
    entry.categoryPath = item.categoryPath;
    item.catalogId = entry.catalogId;
    // Variant identifiers derive from immutable keys, never the display order.
    for (const variant of item.variants ?? []) variant.catalogId = `${item.catalogId}-${variant.key}`;
  }
  for (const [id, entry] of Object.entries(registry.entries)) if (!active.has(id)) entry.status = 'retired';
  return registry;
}
async function main() {
  const configUrl = new URL('../config/site-bom.template.json', import.meta.url);
  const registryUrl = new URL('../config/catalog-identities.json', import.meta.url);
  const config = JSON.parse(await fs.readFile(configUrl, 'utf8'));
  let registry;
  try { registry = JSON.parse(await fs.readFile(registryUrl, 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const items = config.phases.flatMap(p => p.stages.flatMap(s => s.categories.flatMap(c => c.items)));
  const revision = JSON.parse(await fs.readFile(new URL('../config/catalog-revision-2026-09-15.json', import.meta.url), 'utf8'));
  const retired = new Set([...Object.keys(revision.retired), 'FND-013']);
  for (const item of items) if (retired.has(item.id)) throw new Error(`${item.id} was retired; use a new legacy ID for a new item`);
  registry = assignIdentities(items, registry);
  await fs.writeFile(registryUrl, JSON.stringify(registry, null, 2) + '\n');
  await fs.writeFile(configUrl, JSON.stringify(config, null, 2) + '\n');
  const contractUrl = new URL('../config/site-bom.contract.json', import.meta.url);
  const contract = JSON.parse(await fs.readFile(contractUrl, 'utf8'));
  contract.catalog.expectedRowCount = items.length;
  await fs.writeFile(contractUrl, JSON.stringify(contract, null, 2) + '\n');
  console.log(`${items.length} catalog identities synchronized; retired numbers remain reserved.`);
}
if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
