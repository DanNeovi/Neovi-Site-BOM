import {
  DEFAULT_CONFIG_PATH,
  buildProjectInputExpectations,
  buildProjectInputMap,
  loadTemplateConfig,
  summarizeCatalog,
} from "../src/template-model.mjs";
import { DEFAULT_PROJECT_INPUT_CSV_PATH, loadProjectInputCsv } from "../src/project-input-csv.mjs";
import { calculateSiteBom } from "../src/calculations.mjs";

const configPath = process.argv[2] ?? DEFAULT_CONFIG_PATH;
const inputsPath = process.argv[3] ?? DEFAULT_PROJECT_INPUT_CSV_PATH;
const { config, lines, items, warnings } = await loadTemplateConfig(configPath);
const expectations = buildProjectInputExpectations(config, lines);
const { projectInputs, warnings: inputWarnings } = await loadProjectInputCsv(inputsPath, expectations);
const inputMap = buildProjectInputMap(projectInputs, expectations);
const summary = summarizeCatalog(lines, items);
const calculated = calculateSiteBom(lines, items, inputMap);
const inputKeysNotSupplied = summary.inputKeys.filter((key) => !inputMap.has(key));
const issueCounts = new Map();
for (const result of calculated.lineResults) {
  for (const issue of result.issues) issueCounts.set(issue, (issueCounts.get(issue) ?? 0) + 1);
}
for (const result of calculated.procurementResults) {
  for (const issue of result.issues) issueCounts.set(issue, (issueCounts.get(issue) ?? 0) + 1);
}

console.log(`Template: ${configPath}`);
console.log(`Project inputs: ${inputsPath}`);
console.log(`BOM lines: ${summary.totalLines}`);
console.log(`Purchasable items: ${summary.totalItems}`);
for (const [phase, count] of Object.entries(summary.byPhase)) console.log(`  ${phase}: ${count}`);
console.log(`Input keys: ${summary.inputKeys.length}`);
console.log(`Configuration warnings: ${warnings.length}`);
console.log(`Input warnings: ${inputWarnings.length}`);
console.log(`Missing sample input keys: ${inputKeysNotSupplied.length}`);
for (const key of inputKeysNotSupplied) console.log(`  - ${key}`);
console.log("Review summary:");
for (const [issue, count] of [...issueCounts].sort((a, b) => b[1] - a[1])) console.log(`  ${count}: ${issue}`);

const showcaseIds = ["FND-006", "PAN-002", "PAN-003", "PAN-009"];
console.log("Calculation checks:");
for (const lineId of showcaseIds) {
  const line = lines.find((candidate) => candidate.lineId === lineId);
  const result = calculated.lineResults.find((candidate) => candidate.lineId === lineId);
  if (!line || !result) continue;
  const procurement = calculated.procurementResults.find((candidate) => candidate.itemId === line.itemId);
  console.log(`  ${lineId}: ${result.calculation}; kit=${result.kitDemandQty}; order=${procurement?.orderQty ?? 0}`);
}
