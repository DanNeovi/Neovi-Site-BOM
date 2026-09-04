import path from "node:path";
import { DEFAULT_PROJECT_INPUT_CSV_PATH, loadProjectInputCsv } from "../src/project-input-csv.mjs";
import { buildProjectInputExpectations, loadTemplateConfig } from "../src/template-model.mjs";

const inputPath = process.argv[2] ?? DEFAULT_PROJECT_INPUT_CSV_PATH;
{
  const absolutePath = path.resolve(inputPath);
  const { config, lines } = await loadTemplateConfig();
  const { projectInputs, warnings } = await loadProjectInputCsv(
    absolutePath,
    buildProjectInputExpectations(config, lines),
  );
  console.log(`Valid Site BOM project-input CSV: ${absolutePath}`);
  console.log(`Schema ID: ${projectInputs.schemaId}`);
  console.log(`Schema: ${projectInputs.schemaVersion}`);
  console.log(`Project: ${projectInputs.project}`);
  console.log(`Revision: ${projectInputs.revision}`);
  console.log(`Rows: ${projectInputs.rows.length}`);
  for (const warning of warnings) console.log(`Warning: ${warning}`);
}
