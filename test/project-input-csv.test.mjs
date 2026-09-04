import test from "node:test";
import assert from "node:assert/strict";
import { projectInputsFromCsv, projectInputsToCsv } from "../src/project-input-csv.mjs";

test("project input CSV round-trips quoted text and numeric values", () => {
  const source = {
    schemaId: "neovi.site-bom.project-inputs",
    schemaVersion: "2.0",
    project: "House, A",
    revision: "R01",
    rows: [{
      recordType: "FACT",
      inputKey: "wall_connection_count",
      value: 12,
      unit: "EA",
      source: "REVIT",
      sourceReference: "Wall \"A\"",
      location: "Level 1",
      notes: "Reviewed",
    }],
  };
  const csv = projectInputsToCsv(source);
  const result = projectInputsFromCsv(csv).projectInputs;
  assert.equal(result.project, "House, A");
  assert.equal(result.rows[0].value, 12);
  assert.equal(result.rows[0].sourceReference, 'Wall "A"');
});

test("CSV export neutralizes spreadsheet formula injection in text fields", () => {
  const source = {
    schemaId: "neovi.site-bom.project-inputs",
    schemaVersion: "2.0",
    project: "House A",
    revision: "R01",
    rows: [{
      recordType: "FACT",
      inputKey: "connections",
      value: 1,
      unit: "EA",
      source: "REVIT",
      sourceReference: "=HYPERLINK(\"bad\")",
      location: "Level 1",
      notes: "",
    }],
  };
  assert.match(projectInputsToCsv(source), /'=HYPERLINK/);
});

test("CSV import rejects missing required columns", () => {
  assert.throws(() => projectInputsFromCsv("Project,Value\r\nA,1\r\n"), /exactly 12 columns/i);
});

test("CSV import rejects a blank quantity instead of treating it as zero", () => {
  const csv = [
    "Schema Version,Project,Revision,Record Type,Input Key,Value,Unit,Source,Source Reference,Location,Notes,Schema ID",
    "2.0,House A,R01,FACT,connections,,EA,REVIT,wall-1,Level 1,,neovi.site-bom.project-inputs",
  ].join("\r\n");
  assert.throws(() => projectInputsFromCsv(csv), /Value must be numeric/i);
});

test("CSV import rejects reordered or extra columns and malformed quote placement", () => {
  const reordered = [
    "Project,Schema Version,Revision,Record Type,Input Key,Value,Unit,Source,Source Reference,Location,Notes,Schema ID",
    "House A,2.0,R01,FACT,count,1,EA,REVIT,A,,,neovi.site-bom.project-inputs",
  ].join("\r\n");
  const extra = [
    "Schema Version,Project,Revision,Record Type,Input Key,Value,Unit,Source,Source Reference,Location,Notes,Schema ID,Extra",
    "2.0,House A,R01,FACT,count,1,EA,REVIT,A,,,neovi.site-bom.project-inputs,unexpected",
  ].join("\r\n");
  assert.throws(() => projectInputsFromCsv(reordered), /column 1 must be Schema Version/i);
  assert.throws(() => projectInputsFromCsv(extra), /exactly 12 columns/i);
  assert.throws(() => projectInputsFromCsv('Project,"bad"tail\r\n'), /unexpected text after a closing quote/i);
});
