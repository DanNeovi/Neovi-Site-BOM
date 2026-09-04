import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadTemplateConfig } from "../src/template-model.mjs";

const moduleDir = path.dirname(fileURLToPath(import.meta.url));
const revitRoot = path.resolve(readOption("--revit-root") ?? path.join(moduleDir, "../../NeoviRevitEnergyExport"));
const destination = path.join(revitRoot, "NeoviEnergyExport", "config");
const { config, contract, contractPath, lines } = await loadTemplateConfig();

await import("./build-no-quantity-inputs.mjs");
await fs.mkdir(destination, { recursive: true });

const catalogName = "Neovi-Site-BOM-All-Discussed-Items-No-Quantities.csv";
const catalogSource = path.resolve(moduleDir, `../outputs/site-bom-v${config.settings.templateVersion}/${catalogName}`);
const catalogDestination = path.join(destination, catalogName);
const contractDestination = path.join(destination, "NeoviSiteBom.contract.json");
await fs.copyFile(catalogSource, catalogDestination);
await fs.copyFile(contractPath, contractDestination);

const catalogBytes = await fs.readFile(catalogDestination);
const manifest = {
  format: "neovi-site-bom-release",
  contractVersion: contract.contractVersion,
  catalogVersion: contract.catalogVersion,
  projectInputSchema: contract.schemas.projectInputs,
  catalogSchema: contract.schemas.catalog,
  templateVersion: config.settings.templateVersion,
  catalogRowCount: lines.length,
  catalogSha256: crypto.createHash("sha256").update(catalogBytes).digest("hex"),
};
await fs.writeFile(path.join(destination, "NeoviSiteBom.release.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

console.log(`Synchronized Site BOM ${manifest.catalogVersion} to ${destination}`);
console.log(`Catalog rows: ${manifest.catalogRowCount}; SHA-256: ${manifest.catalogSha256}`);

function readOption(name) {
  const index = process.argv.indexOf(name);
  if (index < 0) return undefined;
  const value = process.argv[index + 1];
  if (!value || value.startsWith("--")) throw new Error(`${name} requires a path.`);
  return value;
}
