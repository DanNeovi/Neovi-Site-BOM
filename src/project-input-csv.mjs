import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PROJECT_INPUT_HEADERS } from "./workbook-formulas.mjs";
import { validateProjectInputs } from "./template-model.mjs";

const PROJECT_INPUT_FIELDS = Object.freeze([
  "schemaVersion", "project", "revision", "recordType", "inputKey", "value", "unit", "source",
  "sourceReference", "location", "notes", "schemaId",
]);
const EXPECTED_HEADERS = PROJECT_INPUT_HEADERS.map(normalizeHeader);
const moduleDir = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_PROJECT_INPUT_CSV_PATH = path.resolve(moduleDir, "../config/sample-project-inputs.csv");

export async function loadProjectInputCsv(filePath = DEFAULT_PROJECT_INPUT_CSV_PATH, expected = {}) {
  return projectInputsFromCsv(await fs.readFile(path.resolve(filePath), "utf8"), expected);
}

export function projectInputsFromCsv(csvText, expected = {}) {
  const matrix = parseCsv(csvText);
  if (matrix.length < 2) throw new Error("Project input CSV must contain a header row and at least one data row.");
  const headers = matrix[0].map(normalizeHeader);
  if (headers.length !== EXPECTED_HEADERS.length) {
    throw new Error(`Project input CSV must contain exactly ${EXPECTED_HEADERS.length} columns.`);
  }
  for (let index = 0; index < EXPECTED_HEADERS.length; index += 1) {
    if (headers[index] !== EXPECTED_HEADERS[index]) {
      throw new Error(`Project input CSV column ${index + 1} must be ${PROJECT_INPUT_HEADERS[index]}.`);
    }
  }

  const rows = matrix.slice(1)
    .filter((row) => row.some((value) => String(value).trim() !== ""))
    .map((row, rowIndex) => {
      if (row.length !== PROJECT_INPUT_FIELDS.length) {
        throw new Error(`Project input CSV row ${rowIndex + 2} must contain exactly ${PROJECT_INPUT_FIELDS.length} columns.`);
      }
      return Object.fromEntries(PROJECT_INPUT_FIELDS.map((field, index) => [field, String(row[index] ?? "").trim()]));
    });

  const projectInputs = {
    schemaId: rows[0]?.schemaId ?? "",
    schemaVersion: rows[0]?.schemaVersion ?? "",
    project: rows[0]?.project ?? "",
    revision: rows[0]?.revision ?? "",
    rows,
  };
  const validation = validateProjectInputs(projectInputs, expected);
  if (validation.errors.length) {
    throw new Error(["Invalid project input CSV:", ...validation.errors.map((error) => `- ${error}`)].join("\n"));
  }
  projectInputs.rows = validation.normalizedRows.map(({ rowNumber, ...row }) => row);
  return { projectInputs, warnings: validation.warnings };
}

export function projectInputsToCsv(projectInputs) {
  const validation = validateProjectInputs(projectInputs);
  if (validation.errors.length) {
    throw new Error(["Invalid project inputs:", ...validation.errors.map((error) => `- ${error}`)].join("\n"));
  }
  const rows = validation.normalizedRows.map((row) => [
    row.schemaVersion,
    row.project,
    row.revision,
    row.recordType,
    row.inputKey,
    row.value,
    row.unit,
    row.source,
    row.sourceReference,
    row.location,
    row.notes,
    row.schemaId,
  ]);
  return [PROJECT_INPUT_HEADERS, ...rows]
    .map((row) => row.map(csvCell).join(","))
    .join("\r\n") + "\r\n";
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  let afterQuote = false;
  const source = String(text ?? "").replace(/^\uFEFF/, "");

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (quoted) {
      if (char === '"' && source[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
        afterQuote = true;
      } else {
        field += char;
      }
    } else if (afterQuote) {
      if (char === ",") {
        row.push(field);
        field = "";
        afterQuote = false;
      } else if (char === "\n") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
        afterQuote = false;
      } else if (char !== "\r") {
        throw new Error(`Project input CSV has unexpected text after a closing quote at character ${index + 1}.`);
      }
    } else if (char === '"') {
      if (field !== "") throw new Error(`Project input CSV has a quote inside an unquoted field at character ${index + 1}.`);
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  if (quoted) throw new Error("Project input CSV has an unterminated quoted field.");
  if (field !== "" || row.length) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  return rows;
}

function normalizeHeader(value) {
  return String(value).trim().toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
}

function csvCell(value) {
  const raw = value === null || value === undefined ? "" : String(value);
  const safe = typeof value === "string" && /^[=+@\-\t\r]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replaceAll('"', '""')}"`;
}
