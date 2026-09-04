import fs from "node:fs/promises";
import path from "node:path";
import {
  DEFAULT_CONFIG_PATH,
  buildProjectInputExpectations,
  loadTemplateConfig,
} from "../src/template-model.mjs";
import { loadMasterSnapshot } from "../src/master-snapshot.mjs";
import { loadProjectInputCsv } from "../src/project-input-csv.mjs";
import { validateGoogleSheetBuilder } from "./validate-google-sheet-builder.mjs";

const args = parseArgs(process.argv.slice(2));
const configPath = path.resolve(args.config ?? DEFAULT_CONFIG_PATH);
const formulasPath = path.resolve("src/workbook-formulas.mjs");
const runtimePath = path.resolve("scripts/google-sheet-builder-runtime.gs");
const setupPath = path.resolve("scripts/google-sheet-setup.gs");

const model = args.snapshot
  ? await loadMasterSnapshot(path.resolve(args.snapshot))
  : await loadTemplateConfig(configPath);
const { config, lines, items, warnings } = model;
const outputPath = path.resolve(
  args.output ?? `outputs/site-bom-v${config.settings.templateVersion}/Neovi-Site-BOM-Builder.gs`,
);
let normalizedProjectInputs = [];
if (args.inputs) {
  const inputsPath = path.resolve(args.inputs);
  const { projectInputs } = await loadProjectInputCsv(
    inputsPath,
    buildProjectInputExpectations(config, lines),
  );
  normalizedProjectInputs = projectInputs.rows;
}

const payload = {
  settings: config.settings,
  warnings,
  lines,
  items,
  projectInputs: normalizedProjectInputs,
};
const [formulaModule, runtime, setup] = await Promise.all([
  fs.readFile(formulasPath, "utf8"),
  fs.readFile(runtimePath, "utf8"),
  fs.readFile(setupPath, "utf8"),
]);
const appsScriptFormulas = formulaModule.replace(/^export /gm, "").trim();
const generated = [
  "/** @OnlyCurrentDoc */",
  "/** GENERATED FILE — rebuild with npm.cmd run build:template. */",
  `const SITE_BOM_BUILD_DATA = ${JSON.stringify(payload, null, 2)};`,
  appsScriptFormulas,
  runtime.trim(),
  setup.trim(),
  "",
].join("\n\n");

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(outputPath, generated, "utf8");
console.log(`Created native Google Sheets builder: ${outputPath}`);
console.log(`BOM lines: ${lines.length}; items: ${items.length}; project inputs: ${payload.projectInputs.length}`);
await validateGoogleSheetBuilder(outputPath);

function parseArgs(values) {
  const result = {};
  const allowed = new Set(["config", "inputs", "output", "snapshot"]);
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (!value.startsWith("--")) throw new Error(`Unexpected argument: ${value}`);
    const name = value.slice(2);
    if (!allowed.has(name)) throw new Error(`Unknown option: --${name}`);
    const optionValue = values[index + 1];
    if (!optionValue || optionValue.startsWith("--")) throw new Error(`Option --${name} requires a value.`);
    result[name] = optionValue;
    index += 1;
  }
  if (result.config && result.snapshot) throw new Error("Use either --config or --snapshot, not both.");
  return result;
}
