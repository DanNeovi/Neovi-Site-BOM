import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const SOURCE_MODES = Object.freeze(["DIRECT", "CALCULATED", "FIXED", "MANUAL"]);
export const SCOPES = Object.freeze(["SITE", "FACTORY", "BOTH"]);
export const RULE_STATUSES = Object.freeze(["NEEDS_REVIEW", "READY_FOR_TEST", "APPROVED"]);
export const INPUT_KEY_PATTERN = /^[a-z][a-z0-9_]*$/;
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.:-]*$/;

const moduleDir = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_CONFIG_PATH = path.resolve(moduleDir, "../config/site-bom.template.json");
export const DEFAULT_CONTRACT_PATH = path.resolve(moduleDir, "../config/site-bom.contract.json");

export async function readJson(filePath) {
  const absolutePath = path.resolve(filePath);
  return JSON.parse(await fs.readFile(absolutePath, "utf8"));
}

export async function loadTemplateConfig(filePath = DEFAULT_CONFIG_PATH) {
  const rawConfig = await readJson(filePath);
  const contractPath = path.resolve(path.dirname(path.resolve(filePath)), rawConfig.contractRef ?? DEFAULT_CONTRACT_PATH);
  const contract = await loadSiteBomContract(contractPath);
  const config = applySiteBomContract(rawConfig, contract);
  const validation = validateTemplateConfig(config);
  if (contract.catalog.expectedRowCount !== validation.lineCount) {
    validation.errors.push(
      `Contract expects ${contract.catalog.expectedRowCount} catalog rows but the template defines ${validation.lineCount}.`,
    );
  }
  if (validation.errors.length) {
    throw new Error(formatValidationErrors(validation.errors, filePath));
  }

  const lines = flattenBomLines(config);
  return {
    config,
    lines,
    items: buildItemCatalog(lines),
    warnings: validation.warnings,
    contract,
    contractPath,
  };
}

export async function loadSiteBomContract(filePath = DEFAULT_CONTRACT_PATH) {
  const contract = await readJson(filePath);
  const errors = validateSiteBomContract(contract);
  if (errors.length) throw new Error(formatValidationErrors(errors, filePath));
  return contract;
}

export function applySiteBomContract(rawConfig, contract) {
  const config = structuredClone(rawConfig);
  const settings = config.settings ?? (config.settings = {});
  const categoryCodes = Object.fromEntries(contract.categories.map(({ name, code }) => [name, code]));
  const categoryTeams = Object.fromEntries(contract.categories.map(({ name, siteTeam }) => [name, siteTeam]));
  const categoryTeamScopes = Object.fromEntries(contract.categories.map(({ name, teamScope }) => [name, teamScope]));
  settings.contractVersion = contract.contractVersion;
  settings.catalogVersion = contract.catalogVersion;
  settings.schemaId = contract.schemas.projectInputs.id;
  settings.schemaVersion = contract.schemas.projectInputs.version;
  settings.catalogSchemaId = contract.schemas.catalog.id;
  settings.catalogSchemaVersion = contract.schemas.catalog.version;
  settings.visiblePhases = [...contract.phases];
  settings.siteStages = [...contract.siteStages];
  settings.categories = contract.categories.map(({ name }) => name);
  settings.categoryCodes = categoryCodes;
  settings.categoryTeams = categoryTeams;
  settings.categoryTeamScopes = categoryTeamScopes;
  settings.units = [...contract.units];
  settings.sourceTypes = [...contract.sourceTypes];
  settings.recordTypes = [...contract.recordTypes];
  settings.inputUnits = Object.fromEntries(contract.projectInputs.map(({ inputKey, unit }) => [inputKey, unit]));
  settings.inputDefinitions = structuredClone(contract.projectInputs);
  config.contract = structuredClone(contract);
  return config;
}

export function validateSiteBomContract(contract) {
  const errors = [];
  if (!contract || typeof contract !== "object" || Array.isArray(contract)) return ["Site BOM contract must be an object."];
  for (const field of ["contractVersion", "catalogVersion"]) {
    if (!String(contract[field] ?? "").trim()) errors.push(`${field} is required.`);
  }
  for (const name of ["projectInputs", "catalog"]) {
    const schema = contract.schemas?.[name];
    if (!String(schema?.id ?? "").trim()) errors.push(`schemas.${name}.id is required.`);
    if (!String(schema?.version ?? "").trim()) errors.push(`schemas.${name}.version is required.`);
  }
  if (!Number.isInteger(contract.catalog?.expectedRowCount) || contract.catalog.expectedRowCount <= 0) {
    errors.push("catalog.expectedRowCount must be a positive integer.");
  }
  for (const field of ["phases", "siteStages", "categories", "units", "sourceTypes", "recordTypes", "projectInputs"]) {
    if (!Array.isArray(contract[field]) || contract[field].length === 0) errors.push(`${field} must be a non-empty array.`);
  }
  const stages = new Set((contract.siteStages ?? []).map(String));
  if (stages.size !== (contract.siteStages ?? []).length) errors.push("siteStages cannot contain duplicates.");
  const categoryNames = new Set();
  const categoryCodes = new Set();
  for (const category of contract.categories ?? []) {
    const name = String(category?.name ?? "").trim();
    const code = String(category?.code ?? "").trim();
    const siteTeam = String(category?.siteTeam ?? "").trim();
    const teamScope = String(category?.teamScope ?? "").trim();
    if (!name || !code || !siteTeam || !teamScope) errors.push("Every category requires a code, name, siteTeam, and teamScope.");
    if (categoryNames.has(name.toLowerCase())) errors.push(`Duplicate category name: ${name}.`);
    if (categoryCodes.has(code.toLowerCase())) errors.push(`Duplicate category code: ${code}.`);
    categoryNames.add(name.toLowerCase());
    categoryCodes.add(code.toLowerCase());
  }
  const units = new Set(contract.units ?? []);
  const sources = new Set(contract.sourceTypes ?? []);
  const recordTypes = new Set(contract.recordTypes ?? []);
  const inputKeys = new Set();
  for (const input of contract.projectInputs ?? []) {
    const key = String(input?.inputKey ?? "").trim();
    if (!INPUT_KEY_PATTERN.test(key)) errors.push(`Invalid contract Input Key: ${key || "<blank>"}.`);
    if (inputKeys.has(key)) errors.push(`Duplicate contract Input Key: ${key}.`);
    inputKeys.add(key);
    if (!stages.has(String(input?.deliveryStage ?? ""))) errors.push(`Input ${key} has invalid deliveryStage.`);
    if (!units.has(input?.unit)) errors.push(`Input ${key} has invalid unit ${input?.unit ?? "<blank>"}.`);
    if (!sources.has(input?.source)) errors.push(`Input ${key} has invalid source ${input?.source ?? "<blank>"}.`);
    if (!recordTypes.has(input?.recordType)) errors.push(`Input ${key} has invalid recordType ${input?.recordType ?? "<blank>"}.`);
    for (const field of ["sourceReference", "location", "notes"]) {
      if (!String(input?.[field] ?? "").trim()) errors.push(`Input ${key} is missing ${field}.`);
    }
  }
  return [...new Set(errors)];
}

export function flattenBomLines(config) {
  const defaults = config.defaults ?? {};
  const lines = [];

  for (const [phaseIndex, phase] of (config.phases ?? []).entries()) {
    for (const [stageIndex, stage] of (phase.stages ?? []).entries()) {
      for (const [categoryIndex, category] of (stage.categories ?? []).entries()) {
        for (const [itemIndex, item] of (category.items ?? []).entries()) {
          const rule = { ...(defaults.rule ?? {}), ...(category.rule ?? {}), ...(item.rule ?? {}) };
          const specification = item.specification ?? defaults.specification ?? "TBD - approve exact specification";
          const lineId = item.lineId ?? item.id;
          const itemId = item.itemId ?? item.id;
          lines.push({
            phase: phase.name,
            phaseCode: phase.code,
            phaseOrder: phaseIndex + 1,
            phaseColor: phase.color,
            stage: stage.name,
            stageOrder: stageIndex + 1,
            category: category.name,
            categoryCode: config.settings?.categoryCodes?.[category.name] ?? "",
            siteTeam: config.settings?.categoryTeams?.[category.name] ?? "",
            teamScope: config.settings?.categoryTeamScopes?.[category.name] ?? "",
            categoryOrder: categoryIndex + 1,
            system: item.system ?? category.system ?? "",
            deliveryStage: String(item.deliveryStage ?? category.deliveryStage ?? stage.deliveryStage ?? phase.deliveryStage ?? ""),
            kitId: item.kitId ?? category.kitId ?? stage.kitId ?? `${phase.code}-UNASSIGNED`,
            lineId,
            itemId,
            scope: item.scope ?? category.scope ?? defaults.scope ?? "SITE",
            description: item.description,
            specification,
            specificationApproved: (item.specificationApproved ?? defaults.specificationApproved ?? false) === true,
            unit: item.unit ?? category.unit ?? defaults.unit ?? "EA",
            owner: item.owner ?? category.owner ?? defaults.owner ?? "Unassigned",
            sourceMode: rule.sourceMode ?? "MANUAL",
            inputKey: rule.inputKey ?? "",
            inputUnit: rule.inputUnit ?? config.settings?.inputUnits?.[rule.inputKey] ?? "",
            multiplier: numberOrDefault(rule.multiplier, 1),
            fixedQty: numberOrDefault(rule.fixedQty, 0),
            sparePercent: numberOrDefault(rule.sparePercent, 0),
            quantityIncrement: positiveNumberOrDefault(rule.quantityIncrement, 1),
            minimumKitQty: numberOrDefault(rule.minimumKitQty, 0),
            ruleStatus: rule.status ?? "NEEDS_REVIEW",
            ruleNotes: rule.notes ?? "",
            procurementMethod: item.procurementMethod ?? defaults.procurementMethod ?? "TBD",
            vendor: item.vendor ?? "",
            partNumber: item.partNumber ?? "",
            unitCost: nullableNumber(item.unitCost ?? defaults.unitCost),
            packSize: positiveNumberOrDefault(item.packSize ?? rule.packSize ?? defaults.packSize, 1),
            minimumOrderQty: numberOrDefault(item.minimumOrderQty ?? defaults.minimumOrderQty, 0),
            targetStockQty: numberOrDefault(item.targetStockQty ?? defaults.targetStockQty, 0),
            itemNotes: item.itemNotes ?? item.notes ?? "",
            lineNotes: item.lineNotes ?? "",
            sourcePath: `${phase.name} > ${stage.name} > ${category.name} > ${item.system ?? category.system ?? "<system>"} > ${item.description}`,
            sourceOrdinal: [phaseIndex, stageIndex, categoryIndex, itemIndex],
          });
        }
      }
    }
  }

  return lines;
}

export function buildItemCatalog(lines) {
  const items = new Map();
  for (const line of lines) {
    if (items.has(line.itemId)) continue;
    items.set(line.itemId, {
      itemId: line.itemId,
      description: line.description,
      specification: line.specification,
      specificationApproved: line.specificationApproved,
      unit: line.unit,
      owner: line.owner,
      procurementMethod: line.procurementMethod,
      vendor: line.vendor,
      partNumber: line.partNumber,
      unitCost: line.unitCost,
      packSize: line.packSize,
      minimumOrderQty: line.minimumOrderQty,
      targetStockQty: line.targetStockQty,
      notes: line.itemNotes,
    });
  }
  return [...items.values()];
}

export function validateTemplateConfig(config) {
  const errors = [];
  const warnings = [];
  if (!config || typeof config !== "object") {
    return { errors: ["Template configuration must be an object."], warnings };
  }

  const settings = config.settings;
  if (!settings || typeof settings !== "object" || Array.isArray(settings)) {
    return { errors: ["settings must be an object."], warnings };
  }
  for (const field of ["templateName", "templateVersion", "schemaId", "schemaVersion", "catalogVersion", "catalogSchemaId", "catalogSchemaVersion"]) {
    if (!String(settings[field] ?? "").trim()) errors.push(`settings.${field} is required.`);
  }
  for (const field of ["visiblePhases", "siteStages", "categories", "statuses", "owners", "units", "procurementMethods", "sourceTypes", "recordTypes", "ruleStatuses"]) {
    if (!Array.isArray(settings[field]) || settings[field].length === 0) {
      errors.push(`settings.${field} must be a non-empty array.`);
    } else {
      const values = settings[field].map((value) => String(value).trim());
      if (values.some((value) => !value)) errors.push(`settings.${field} cannot contain blank values.`);
      if (new Set(values.map((value) => value.toLowerCase())).size !== values.length) {
        errors.push(`settings.${field} cannot contain duplicates.`);
      }
      if (["units", "sourceTypes", "recordTypes", "ruleStatuses"].includes(field)
        && values.some((value) => value !== value.toUpperCase())) {
        errors.push(`settings.${field} values must be uppercase.`);
      }
    }
  }
  const requiredSettingValues = {
    statuses: ["Needs Review"],
    owners: ["Unassigned"],
    units: ["EA"],
    procurementMethods: ["TBD", "Order"],
    sourceTypes: ["REVIT"],
    recordTypes: ["FACT", "DIRECT_ITEM"],
    ruleStatuses: ["NEEDS_REVIEW", "APPROVED"],
  };
  for (const [field, requiredValues] of Object.entries(requiredSettingValues)) {
    const actualValues = Array.isArray(settings[field]) ? settings[field] : [];
    for (const requiredValue of requiredValues) {
      if (!actualValues.includes(requiredValue)) errors.push(`settings.${field} must include ${requiredValue}.`);
    }
  }
  if (!settings.inputUnits || typeof settings.inputUnits !== "object" || Array.isArray(settings.inputUnits)) {
    errors.push("settings.inputUnits must map every imported Input Key to one expected unit.");
  }
  for (const field of ["categoryCodes", "categoryTeams", "categoryTeamScopes"]) {
    if (!settings[field] || typeof settings[field] !== "object" || Array.isArray(settings[field])) {
      errors.push(`settings.${field} must be an object map.`);
    }
  }
  if (config.defaults?.specificationApproved !== undefined
    && typeof config.defaults.specificationApproved !== "boolean") {
    errors.push("defaults.specificationApproved must be a boolean.");
  }

  const allowedPhases = new Set(settings.visiblePhases ?? []);
  const allowedCategories = new Set(settings.categories ?? []);
  const allowedUnits = new Set(settings.units ?? []);
  const allowedOwners = new Set(settings.owners ?? []);
  const allowedProcurementMethods = new Set(settings.procurementMethods ?? []);
  const allowedRuleStatuses = new Set(settings.ruleStatuses ?? []);
  const allowedDeliveryStages = new Set((settings.siteStages ?? []).map(String));
  const phaseNames = new Set();
  const lineIds = new Set();
  const inputKeys = new Set();
  const unitByInputKey = new Map();

  if (!Array.isArray(config.phases) || config.phases.length === 0) {
    errors.push("At least one phase is required.");
    return { errors, warnings };
  }

  for (const phase of config.phases) {
    if (!phase.name) errors.push("Every phase requires a name.");
    if (!phase.code) errors.push(`Phase ${phase.name ?? "<unknown>"} requires a code.`);
    if (phaseNames.has(phase.name)) errors.push(`Duplicate phase name: ${phase.name}`);
    phaseNames.add(phase.name);
    if (allowedPhases.size && !allowedPhases.has(phase.name)) {
      errors.push(`Phase ${phase.name} is not listed in settings.visiblePhases.`);
    }
    if (!Array.isArray(phase.stages) || !phase.stages.length) {
      errors.push(`Phase ${phase.name} must contain at least one stage.`);
      continue;
    }

    for (const stage of phase.stages) {
      if (!stage.name) errors.push(`Phase ${phase.name} has a stage without a name.`);
      if (!Array.isArray(stage.categories) || !stage.categories.length) {
        errors.push(`Stage ${phase.name} > ${stage.name ?? "<unknown>"} must contain a category.`);
        continue;
      }

      const categorySystems = new Set();
      for (const category of stage.categories) {
        if (!category.name) errors.push(`Phase ${phase.name} > ${stage.name} has a category without a name.`);
        if (category.name && allowedCategories.size && !allowedCategories.has(category.name)) {
          errors.push(`Category ${phase.name} > ${stage.name} > ${category.name} is not listed in settings.categories.`);
        }
        if (!String(settings.categoryTeams?.[category.name] ?? "").trim()) {
          errors.push(`Category ${category.name ?? "<unknown>"} requires a Site Team mapping.`);
        }
        if (!String(settings.categoryTeamScopes?.[category.name] ?? "").trim()) {
          errors.push(`Category ${category.name ?? "<unknown>"} requires a Team Scope mapping.`);
        }
        if (!Array.isArray(category.items) || !category.items.length) {
          errors.push(`Category ${phase.name} > ${stage.name} > ${category.name ?? "<unknown>"} must contain an item.`);
          continue;
        }
        const system = String(category.system ?? "").trim();
        if (!system) errors.push(`Category ${phase.name} > ${stage.name} > ${category.name} requires a System.`);
        const categoryDeliveryStage = String(category.deliveryStage ?? stage.deliveryStage ?? phase.deliveryStage ?? "");
        const categorySystemKey = `${category.name}\u0000${system}\u0000${categoryDeliveryStage}`.toLowerCase();
        if (categorySystems.has(categorySystemKey)) {
          errors.push(`Duplicate Category/System in ${phase.name} > ${stage.name}: ${category.name} / ${system}.`);
        }
        categorySystems.add(categorySystemKey);

        for (const item of category.items) {
          const lineId = item.lineId ?? item.id;
          const itemId = item.itemId ?? item.id;
          const location = `${phase.name} > ${stage.name} > ${category.name} > ${item.description ?? "<unknown>"}`;
          if (!lineId) errors.push(`Missing line ID: ${location}`);
          if (!itemId) errors.push(`Missing item ID: ${location}`);
          if (!item.description) errors.push(`Missing item description: ${location}`);
          if (lineId && !ID_PATTERN.test(lineId)) errors.push(`Invalid line ID ${lineId}: ${location}`);
          if (itemId && !ID_PATTERN.test(itemId)) errors.push(`Invalid item ID ${itemId}: ${location}`);
          if (lineIds.has(lineId)) errors.push(`Duplicate line ID: ${lineId}`);
          lineIds.add(lineId);
          const deliveryStage = String(item.deliveryStage ?? category.deliveryStage ?? stage.deliveryStage ?? phase.deliveryStage ?? "");
          if (!allowedDeliveryStages.has(deliveryStage)) errors.push(`Invalid or missing deliveryStage ${deliveryStage || "<blank>"}: ${location}`);

          const rule = { ...(config.defaults?.rule ?? {}), ...(category.rule ?? {}), ...(item.rule ?? {}) };
          const sourceMode = rule.sourceMode ?? "MANUAL";
          const scope = item.scope ?? category.scope ?? config.defaults?.scope ?? "SITE";
          if (!SOURCE_MODES.includes(sourceMode)) errors.push(`Invalid source mode ${sourceMode}: ${location}`);
          if (!SCOPES.includes(scope)) errors.push(`Invalid scope ${scope}: ${location}`);
          if (["DIRECT", "CALCULATED"].includes(sourceMode) && !rule.inputKey) {
            errors.push(`Source mode ${sourceMode} requires an inputKey: ${location}`);
          }
          if (rule.inputKey) {
            inputKeys.add(rule.inputKey);
            if (!INPUT_KEY_PATTERN.test(rule.inputKey)) errors.push(`Invalid inputKey ${rule.inputKey}: ${location}`);
            const inputUnit = String(rule.inputUnit ?? settings.inputUnits?.[rule.inputKey] ?? "").trim().toUpperCase();
            if (!inputUnit) errors.push(`Input key ${rule.inputKey} requires an expected input unit: ${location}`);
            else if (!allowedUnits.has(inputUnit)) errors.push(`Input key ${rule.inputKey} uses unknown input unit ${inputUnit}: ${location}`);
            const existingUnit = unitByInputKey.get(rule.inputKey);
            if (existingUnit && existingUnit !== inputUnit) {
              errors.push(`Input key ${rule.inputKey} has conflicting expected units ${existingUnit} and ${inputUnit}.`);
            } else if (inputUnit) {
              unitByInputKey.set(rule.inputKey, inputUnit);
            }
          }

          const unit = item.unit ?? category.unit ?? config.defaults?.unit ?? "EA";
          const owner = item.owner ?? category.owner ?? config.defaults?.owner ?? "Unassigned";
          const procurementMethod = item.procurementMethod ?? config.defaults?.procurementMethod ?? "TBD";
          const ruleStatus = rule.status ?? "NEEDS_REVIEW";
          if (!allowedUnits.has(unit)) errors.push(`Unknown unit ${unit}: ${location}`);
          if (!allowedOwners.has(owner)) errors.push(`Unknown owner ${owner}: ${location}`);
          if (!allowedProcurementMethods.has(procurementMethod)) errors.push(`Unknown procurement method ${procurementMethod}: ${location}`);
          if (!RULE_STATUSES.includes(ruleStatus) || !allowedRuleStatuses.has(ruleStatus)) {
            errors.push(`Invalid rule status ${ruleStatus}: ${location}`);
          }
          if (item.specificationApproved !== undefined && typeof item.specificationApproved !== "boolean") {
            errors.push(`specificationApproved must be a boolean: ${location}`);
          }

          const numericFields = {
            multiplier: rule.multiplier ?? 1,
            fixedQty: rule.fixedQty ?? 0,
            sparePercent: rule.sparePercent ?? 0,
            quantityIncrement: rule.quantityIncrement ?? 1,
            minimumKitQty: rule.minimumKitQty ?? 0,
            packSize: item.packSize ?? rule.packSize ?? config.defaults?.packSize ?? 1,
            minimumOrderQty: item.minimumOrderQty ?? config.defaults?.minimumOrderQty ?? 0,
            targetStockQty: item.targetStockQty ?? config.defaults?.targetStockQty ?? 0,
          };
          if (item.unitCost !== undefined && item.unitCost !== null && item.unitCost !== "") {
            numericFields.unitCost = item.unitCost;
          }
          for (const [field, value] of Object.entries(numericFields)) {
            if (!Number.isFinite(Number(value))) errors.push(`${field} must be numeric: ${location}`);
          }
          for (const field of ["multiplier", "fixedQty", "sparePercent", "minimumKitQty", "minimumOrderQty", "targetStockQty", "unitCost"]) {
            if (field in numericFields && Number(numericFields[field]) < 0) errors.push(`${field} cannot be negative: ${location}`);
          }
          if (Number(numericFields.quantityIncrement) <= 0) errors.push(`quantityIncrement must be positive: ${location}`);
          if (Number(numericFields.packSize) <= 0) errors.push(`packSize must be positive: ${location}`);

          const specification = item.specification ?? config.defaults?.specification ?? "";
          const specificationApproved = item.specificationApproved ?? config.defaults?.specificationApproved ?? false;
          if (!specificationApproved || specification.startsWith("TBD")) {
            warnings.push(`Specification requires approval: ${location}`);
          }
        }
      }
    }
  }

  if (allowedPhases.size !== phaseNames.size || [...allowedPhases].some((phase) => !phaseNames.has(phase))) {
    errors.push("settings.visiblePhases must match the configured phase names exactly.");
  }
  for (const [key, unit] of Object.entries(settings.inputUnits ?? {})) {
    if (!INPUT_KEY_PATTERN.test(key)) errors.push(`settings.inputUnits contains invalid Input Key ${key}.`);
    if (!allowedUnits.has(String(unit).toUpperCase())) errors.push(`settings.inputUnits.${key} uses unknown unit ${unit}.`);
    if (!inputKeys.has(key)) errors.push(`settings.inputUnits contains unused Input Key: ${key}`);
  }
  for (const key of inputKeys) {
    if (!(key in (settings.inputUnits ?? {}))) errors.push(`settings.inputUnits is missing ${key}.`);
  }

  if (!errors.length) {
    const lines = flattenBomLines(config);
    const firstByItem = new Map();
    for (const line of lines) {
      const signature = itemSignature(line);
      const existing = firstByItem.get(line.itemId);
      if (existing && existing.signature !== signature) {
        errors.push(`Shared item ID ${line.itemId} has conflicting purchasing data: ${existing.path} <> ${line.sourcePath}`);
      } else if (!existing) {
        firstByItem.set(line.itemId, { signature, path: line.sourcePath });
      }
    }
  }

  return {
    errors,
    warnings,
    lineCount: lineIds.size,
    inputKeys: [...inputKeys].sort(),
  };
}

export function validateProjectInputs(projectInputs, expected = {}) {
  const errors = [];
  const warnings = [];
  const rows = projectInputs?.rows;
  if (!Array.isArray(rows)) return { errors: ["Project inputs must contain a rows array."], warnings, normalizedRows: [] };

  const normalizedRows = rows.map((row, index) => normalizeProjectInputRow(projectInputs, row, index));
  const seenSources = new Set();
  const allowedRecordTypes = new Set(["FACT", "DIRECT_ITEM"]);
  const allowedInputKeys = expected.allowedInputKeys ? new Set(expected.allowedInputKeys) : null;
  const allowedUnits = expected.allowedUnits ? new Set(expected.allowedUnits) : null;
  const allowedSources = expected.allowedSources ? new Set(expected.allowedSources) : null;
  const expectedInputUnits = expected.inputUnits ?? {};
  const unitsByKey = new Map();

  for (const row of normalizedRows) {
    const label = `Project input row ${row.rowNumber}`;
    if (!row.schemaId) errors.push(`${label} is missing Schema ID`);
    if (!row.schemaVersion) errors.push(`${label} is missing Schema Version`);
    if (!row.project) errors.push(`${label} is missing Project`);
    if (!row.revision) errors.push(`${label} is missing Revision`);
    if (!allowedRecordTypes.has(row.recordType)) errors.push(`${label} has invalid Record Type: ${row.recordType || "<blank>"}`);
    if (!row.inputKey) errors.push(`${label} is missing Input Key`);
    else if (!INPUT_KEY_PATTERN.test(row.inputKey)) errors.push(`${label} has invalid Input Key: ${row.inputKey}`);
    else if (allowedInputKeys && !allowedInputKeys.has(row.inputKey)) errors.push(`${label} uses unknown Input Key: ${row.inputKey}`);
    if (!Number.isFinite(row.value)) errors.push(`${label} Value must be numeric`);
    else if (row.value < 0) errors.push(`${label} Value cannot be negative`);
    if (!row.unit) errors.push(`${label} is missing Unit`);
    else if (allowedUnits && !allowedUnits.has(row.unit)) errors.push(`${label} has invalid Unit: ${row.unit}`);
    if (!row.source) errors.push(`${label} is missing Source`);
    else if (allowedSources && !allowedSources.has(row.source)) errors.push(`${label} has invalid Source: ${row.source}`);
    if (!row.sourceReference) errors.push(`${label} is missing Source Reference`);

    if (row.inputKey && row.unit) {
      const priorUnit = unitsByKey.get(row.inputKey);
      if (priorUnit && priorUnit !== row.unit) {
        errors.push(`Project inputs use mixed units for ${row.inputKey}: ${priorUnit}, ${row.unit}`);
      } else {
        unitsByKey.set(row.inputKey, row.unit);
      }
      const expectedUnit = String(expectedInputUnits[row.inputKey] ?? "").toUpperCase();
      if (expectedUnit && row.unit !== expectedUnit) {
        errors.push(`${label} unit ${row.unit} does not match expected ${expectedUnit} for ${row.inputKey}`);
      }
    }

    const sourceIdentity = [row.schemaId, row.schemaVersion, row.project, row.revision, row.inputKey, row.source, row.sourceReference]
      .map((value) => value.toLowerCase())
      .join("\u0000");
    if (row.inputKey && row.sourceReference && seenSources.has(sourceIdentity)) {
      errors.push(`${label} duplicates an existing source row for ${row.inputKey}: ${row.sourceReference}`);
    }
    seenSources.add(sourceIdentity);

    if (expected.schemaId && row.schemaId !== String(expected.schemaId)) {
      errors.push(`${label} schema ID ${row.schemaId} does not match expected ${expected.schemaId}`);
    }
    if (expected.schemaVersion && row.schemaVersion !== String(expected.schemaVersion)) {
      errors.push(`${label} schema ${row.schemaVersion} does not match expected ${expected.schemaVersion}`);
    }
    if (expected.project && row.project !== String(expected.project)) {
      errors.push(`${label} project ${row.project} does not match expected ${expected.project}`);
    }
    if (expected.revision && row.revision !== String(expected.revision)) {
      errors.push(`${label} revision ${row.revision} does not match expected ${expected.revision}`);
    }
  }

  for (const [field, values] of Object.entries({
    "Schema ID": new Set(normalizedRows.map((row) => row.schemaId).filter(Boolean)),
    "Schema Version": new Set(normalizedRows.map((row) => row.schemaVersion).filter(Boolean)),
    Project: new Set(normalizedRows.map((row) => row.project).filter(Boolean)),
    Revision: new Set(normalizedRows.map((row) => row.revision).filter(Boolean)),
  })) {
    if (values.size > 1) errors.push(`Project inputs contain multiple ${field} values: ${[...values].join(", ")}`);
  }

  return { errors: [...new Set(errors)], warnings: [...new Set(warnings)], normalizedRows };
}

export function buildProjectInputExpectations(config, lines = flattenBomLines(config)) {
  return {
    schemaId: config.settings.schemaId,
    schemaVersion: config.settings.schemaVersion,
    allowedInputKeys: [...new Set(lines.map((line) => line.inputKey).filter(Boolean))],
    inputUnits: Object.fromEntries(lines.filter((line) => line.inputKey).map((line) => [line.inputKey, line.inputUnit])),
    allowedUnits: config.settings.units,
    allowedSources: config.settings.sourceTypes,
  };
}

export function buildProjectInputMap(projectInputs, expected = {}) {
  const validation = validateProjectInputs(projectInputs, expected);
  if (validation.errors.length) {
    throw new Error(["Invalid project inputs:", ...validation.errors.map((error) => `- ${error}`)].join("\n"));
  }

  const result = new Map();
  for (const row of validation.normalizedRows) {
    result.set(row.inputKey, (result.get(row.inputKey) ?? 0) + row.value);
  }
  return result;
}

export function summarizeCatalog(lines, items = buildItemCatalog(lines)) {
  const byPhase = Object.fromEntries(
    [...new Set(lines.map((line) => line.phase))].map((phase) => [phase, lines.filter((line) => line.phase === phase).length]),
  );
  const inputKeys = [...new Set(lines.map((line) => line.inputKey).filter(Boolean))].sort();
  return { totalLines: lines.length, totalItems: items.length, byPhase, inputKeys };
}

function normalizeProjectInputRow(projectInputs, row, index) {
  return {
    rowNumber: index + 2,
    schemaId: String(row.schemaId ?? projectInputs.schemaId ?? "").trim(),
    schemaVersion: String(row.schemaVersion ?? projectInputs.schemaVersion ?? "").trim(),
    project: String(row.project ?? projectInputs.project ?? "").trim(),
    revision: String(row.revision ?? projectInputs.revision ?? "").trim(),
    recordType: String(row.recordType ?? "").trim().toUpperCase(),
    inputKey: String(row.inputKey ?? "").trim(),
    value: row.value === undefined || row.value === null || String(row.value).trim() === ""
      ? Number.NaN
      : Number(row.value),
    unit: String(row.unit ?? "").trim().toUpperCase(),
    source: String(row.source ?? "").trim().toUpperCase(),
    sourceReference: String(row.sourceReference ?? "").trim(),
    location: String(row.location ?? "").trim(),
    notes: String(row.notes ?? "").trim(),
  };
}

function itemSignature(line) {
  return JSON.stringify([
    line.description,
    line.specification,
    line.specificationApproved,
    line.unit,
    line.owner,
    line.procurementMethod,
    line.vendor,
    line.partNumber,
    line.unitCost,
    line.packSize,
    line.minimumOrderQty,
    line.targetStockQty,
    line.itemNotes,
  ]);
}

function formatValidationErrors(errors, filePath) {
  return [`Invalid Site BOM template: ${path.resolve(filePath)}`, ...errors.map((error) => `- ${error}`)].join("\n");
}

function numberOrDefault(value, fallback) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function positiveNumberOrDefault(value, fallback) {
  const numeric = numberOrDefault(value, fallback);
  return numeric > 0 ? numeric : fallback;
}

function nullableNumber(value) {
  if (value === undefined || value === null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}
