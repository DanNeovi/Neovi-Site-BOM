# Neovi Site BOM

## Canonical location

The Git source checkout remains connected to `https://github.com/DanNeovi/Neovi-Site-BOM.git`. On this workstation, `outputs/NeoviBOM` is a directory junction to `G:\My Drive\SiteBOM`, so every normal build writes the current deliverables directly to My Drive. There is no separate active output copy in Documents. Run `npm.cmd run link:drive-output` after a fresh checkout to recreate the junction; the command stops if an existing output directory needs reconciliation. Google Drive must be mounted as `G:` before building.

The HTML viewer is a local catalog with browser-only progress edits. It is not a shared Google Drive editing application; the native Google Sheet workflow below is the editable multiuser option.

## Current Files

For a simple visual overview, open [Site Bill of Material](outputs/NeoviBOM/NeoviBOM.html) in a browser. Two views are available: a combined ordering list and a phase checklist. Site Setup is separate; Foundation has shared equipment/supplemental items and Helical Piles/Bedframe packages with Materials, Tools, and Consumables columns. Click items for details. Use Print / Save PDF for a complete phase or combined list.

The user-supplied BOM Skeleton and later directions are recorded in `config/site-bom-checklist.json`. The viewer builder layers these entries and listed quantities over the catalog without changing model-derived project quantities. Quantity labels distinguish user-provided numbers from Monroe planning estimates. A blank sheet entry with one clear catalog mapping can show its Monroe estimate; unlinked or repeated ambiguous entries remain N/A. When repeated sheet uses share one Monroe item, the combined list shows that estimate once as a shared total. Explicit repeated sheet part types (such as 9/16-inch cutters) combine across work areas, with their supplied quantities summed. Other entries combine by matching part numbers/vendor/unit, complete specifications/prefix/unit, or identical descriptions/unit. The checklist is a layout guide, not an exhaustive inventory. Foundation catalog items not named in the sheet remain fully visible in Shared Foundation Support, Helical Piles, or Bedframe; Panels and Finishing likewise show their full inventories. Open a viewer row to see the calculation and assumption first; expand its evidence or catalog details only when needed. Hoses, string spools, cutting fluid, cleaner, sealants, glue and propane count as complete EA packages with assumed sizes stated in their descriptions and calculations. Installed cable, pipe, rod, board and other measured materials retain length, area, volume or weight units. Keep the HTML in the output folder for document links to work.

As of October 14, 2026, the Foundation checklist places the two-week John Deere rental and named crew tools under Helical Piles, counts one digger motor, ten orange-handle magnets and ten leveling-string sets, and removes nylon chokers. Mud mats appear in Foundation supplemental; the Shared Foundation Support Materials section is intentionally empty. The rental shows 14 calendar days as a planning conversion from two weeks. FND-003 and FND-005 are retired placeholders; their catalog IDs remain reserved.

Run `npm run build:viewer` to regenerate the viewer from the existing JSON snapshot. `npm run export:data` and normal package rebuilds refresh it automatically.

All current generated files live in [outputs/NeoviBOM](outputs/NeoviBOM/). Open [START-HERE.md](outputs/NeoviBOM/START-HERE.md) for direct links to the PDFs and CSVs.

The main exports are [NeoviBOM.xlsx](outputs/NeoviBOM/NeoviBOM.xlsx) for filtering and review and [NeoviBOM.json](outputs/NeoviBOM/NeoviBOM.json) for software. Both contain the same catalog and Franklin/Santa Rita results. The workbook is a review snapshot, not an editable calculation model. JSON quantities are numeric, missing values are `null`, category paths are arrays, and permanent IDs join project rows to catalog items. Planning estimates remain separate from required quantities. Formula explanations and full evidence references are included in JSON; oversized Excel evidence cells point to it.

Install exporter dependencies with `npm ci`. Run `npm run export:data` after rebuilding project results; `npm run verify:data` checks the exported JSON against the source and reopens the workbook to compare every project quantity. Normal `--package` rebuilds also produce both exports.

- `01-Catalog`: checklist CSV, formula guide, related-items PDF and folder index.
- `02-Projects`: separate Franklin and Santa Rita PDFs, CSVs and supporting evidence.
- `03-Categories`: related-items PDFs and nested item folders.
- `04-Audits`: change log, completeness and model checks, and earlier-addition history.
- `05-Google-Sheet`: current Apps Script builder and project-input CSV.
- `_Internal`: model scan caches and rebuild/cleanup provenance.

Run `python scripts/rebuild-project-reports.py --package` to refresh this same folder. Normal builds do not create dated copies, a second source tree or ZIP archives. Editable source remains in this repository's `config/`, `src/`, `scripts/` and `test/`; original model exports remain in Downloads.

Obsolete generated files were moved to `_Internal/Superseded-Archive/` because automatic approval review blocked deletion. That archive is excluded from the current deliverables and rebuilds.

## Google Sheet Deliverable

The operational deliverable is one native Google Sheet with exactly three visible tabs:

1. **Foundation**
2. **Panels**
3. **Finishing**

Each phase tab contains its own work areas, categories, kits, items, quantities, purchasing information, status, and review issues. The offline HTML viewer complements the Sheet for review; it requires no database, server, API, or live Google/Revit connection.

The Google Sheet workflow uses these file types; the PDF and CSV review package is retained in the current output folder above:

| File | Purpose | Permanent deliverable? |
|---|---|---|
| Native Google Sheet | Master template and project Site BOM | Yes |
| `.gs` | One-time builder pasted into the master Sheet's Apps Script | No |
| `.csv` | Temporary project inputs exported from Revit | No |

A CSV is one flat data table. It cannot store multiple worksheet tabs, protected ranges, dropdowns, checkboxes, formatting, or a workbook formula model. The formulas live permanently in the Google Sheet; importing a CSV only replaces the project facts used by those formulas.

## Implemented Architecture

```text
versioned Site BOM contract + catalog seed
        |
        +----> native Google Sheets builder
        |
        +----> versioned human shipping checklist
        |
        +----> pinned Revit contract/release bundle
                       |
Revit Site BOM button |
        |
        +----> no-quantity Project Inputs checklist (19 populated input rows)
        |
        +----> revision-stamped populated Project Inputs CSV
        |
        v
hidden Project Inputs + Import Audit
        |
        v
line-level calculation rules
        |
        +----> Foundation / Panels / Finishing kit demand
        |
        +----> item-level Procurement Summary
               inventory -> net need -> minimum order -> pack rounding
```

The hidden support tables are deliberately separated:

| Sheet | Responsibility |
|---|---|
| Template Settings | Template version, active project/revision, dropdown lists, and visible phase names |
| Items | One row per purchasable SKU or controlled item |
| BOM Lines | One row per phase/work-area/category/system/delivery-stage/kit occurrence |
| Rules | One calculation rule per BOM Line |
| Project Inputs | Current revision's imported Revit/structural facts |
| Import Audit | Schema, revision, numeric-value, required-field, and duplicate-source checks |
| Procurement Summary | Item totals, inventory, minimum orders, packs, costs, and purchasing status |

After the native Google setup is applied, all support sheets are hidden and only the three phase tabs remain visible.

## Why Item ID and Line ID Are Separate

`Item ID` identifies something purchasing can buy. `Line ID` identifies where and why that item is needed.

For example, one approved screw SKU may be used in multiple stages or kits:

```text
Item ID: SCREW-10X2

Line ID: PAN-WALL-FASTENER-001 -> Panels / Walls / Wall Kit
Line ID: FIN-DOOR-FASTENER-004 -> Finishing / Doors / Door Kit
```

The two Line IDs keep their own kit quantities. Procurement groups both lines by `Item ID`, subtracts inventory once, and creates one order quantity. In `config/site-bom.template.json`, existing `id` values are treated as Line IDs and also default to the Item ID. To share a purchasable item, give each occurrence a unique `lineId` and the same `itemId`.

Use `itemNotes` for purchasing/specification notes shared by every occurrence of that Item ID. Use `lineNotes` for phase-, kit-, or installation-specific notes.

## Quantity Logic

For complete Franklin/Santa Rita reports, run `node scripts/build-full-project-reports.mjs` and `python scripts/build-project-test-pdf.py` after the export audit. The resulting PDF and per-project CSVs include all 276 items, each formula and an explicit N/A reason. Unknown quantities and purchasing inputs remain N/A. Generic roof measurements are retained as evidence but do not become slope-material demand without a verified mapping; prior synthetic pack/inventory/price examples are not project quantities.

### Monroe planning formulas

Run `python scripts/scan-monroe-model.py` once to stream the current Monroe JSON from Downloads, then `python scripts/build-monroe-estimates.py` and `python scripts/audit-monroe-values.py`. The readable 276-row quantity report is `outputs/NeoviBOM/05-Monroe/Monroe-Item-Formulas.md`; the matching JSON includes quantities, formulas, source element keys, assumptions, spares and base kit quantities. `Monroe-Value-Audit.md` and `.json` independently recompute each quantity, spare and base kit, verify catalog and model references, label which values are measured or assumed, and rank the design and scope decisions with the largest quantity effect. Passing arithmetic does not approve installation scope or procurement. The scanner checks source size and modification time before using its cached physical elements. It uses Shapely to union the floor meshes and verify that their projected areas match Revit's typed areas. Rates are editable in `config/planning-allowances.json` and `config/monroe-planning-overrides.json`.

The offline `outputs/NeoviBOM/NeoviBOM.html` viewer shows the Monroe quantity, formula, assumption, average rates, base kit and applicable story allocation inside each represented item's expanded details. The full Monroe reports remain under Documents > Monroe; the catalog's second total-station row is intentionally suppressed in the viewer because the supplied sheet already represents that tool.

Monroe has overlapping first-story livable floor takeoffs. The scanner unions their XY meshes, then subtracts the portion shared with the modeled garage room; the report records the excluded areas and uses net first- and second-story measurements. Host stud-wall lengths are split into interior, exterior and garage runs, with first- and second-story interior/exterior comparisons. Wall area uses the model's typed Area after openings for 71 of 72 selected stud walls and gross length x height for the one wall without Area. The site wall CB estimate assumes 10% of this net exterior-wall face proxy, while truss-stage board screws assume 10% of roof sheathing area and ten screws per covered SQFT. The separate 2-FT concrete-board band and its finish screws share one band-area driver at eight screws per covered SQFT. These board scopes need reconciliation. Wall-run and livable-area planning quantities have first- and second-story budget allocations where their driver supports it; door and window screw allocations use the modeled story of each opening. Every defined catalog item has a quantity-per-livable-SQFT comparison in addition to its controlling formula and driver; project-only tool averages are comparisons, not purchasing rates. Truss-connection screws use 50 modeled truss labels, two assumed bearings per truss and four screws per bearing, or 0.142086 screws per roof SQFT as an early area proxy. Linked pile-cap saddles provide pile-position proxies, and room areas drive dry-floor finishes. Every modeled ordinary, quad, stacked, high-amperage and exterior outlet has a cover class. Operable windows drive screen and handle allowances; fixed windows are excluded. LED profile runs are spatially reconciled across two model families. Model-linked quantities and confirmed fixed standards remain distinct from planning estimates. Undefined catalog placeholders get a labeled zero planning allowance; zero is not a measured quantity. Inventory and product ordering still require project review.

Work categories now have stable delivery-stage numbers: `2.1 Floors`, `2.2 Walls`, `3.10 Truss Area Finish`, `3.11 Gutter / Fascia`. The first number is the delivery stage; the named phase is shown separately. The PDF groups items beneath numbered category headings with phase and trade. The CSV and phase tabs prefix **Work Area** with the same section number while retaining the controlled trade **Category**. Numbers remain text, so `3.10` is distinct from `3.1`. The registry is `CATEGORY_SECTIONS` in `src/workbook-formulas.mjs`; new unmapped work categories display `Unnumbered` until assigned a permanent section.

Every phase row's **Calculation** cell now shows the live arithmetic for required quantity, rounded spares, manual extras, minimum kit quantity, inventory deductions, and the final pack-rounded order. The order is shared across all occurrences of an Item ID and must only be purchased once. Review issues label the explanation as a preview. The shipping checklist's **Quantity Basis** contains the corresponding item-specific formula even before quantities are entered; manual rows explicitly identify the takeoff that is still needed.

Rebuild with `npm.cmd run check`. For an existing master, replace its Apps Script with the rebuilt builder and run **Site BOM > Sync template changes** to regenerate the explanations while retaining project entries. The local build does not update an existing Google Sheet automatically.

Large Everything exports (`.neovi-model.json`) can be inspected without loading the whole file into memory:

```powershell
python scripts/inspect-everything-export.py "C:\path\project.neovi-model.json" outputs/NeoviBOM/_Internal/Model-Data/project-evidence.json
```

This diagnostic uses Python `ijson` and records category counts, BOM-tagged elements, and sample measured parameters with source IDs. It is not a production takeoff mapping: raw Everything exports include types, annotations, links, and alternative phases. The committed export samples test quantity math only, not a complete project's purchase list.

For the two-pass quantity audit, first inspect the Santa Rita and Franklin exports into `outputs/NeoviBOM/_Internal/Model-Data/santa-rita-evidence.json` and `outputs/NeoviBOM/_Internal/Model-Data/franklin-evidence.json`, then run:

```powershell
npm.cmd run check
node scripts/audit-quantity-math.mjs outputs/NeoviBOM/_Internal/Model-Data/santa-rita-evidence.json outputs/NeoviBOM/_Internal/Model-Data/franklin-evidence.json
python scripts/verify-quantity-audit.py
```

The audit exercises 840 scenarios across the catalog, round-trips all qualifying roof-area records through the CSV importer, and independently verifies the results with Python Decimal arithmetic. It writes a source-by-source Markdown report and clearly labeled test-only CSVs. Roof candidates exclude links, demolition, design options, and non-instance areas; material overlap and applicability still need project review before treating these areas as purchasable roof material.

Phase lines calculate installation/kit demand without vendor-pack rounding:

```text
Required Qty =
  DIRECT or CALCULATED: imported Source Value x Multiplier
  FIXED:                Fixed Qty
  MANUAL:               Manual Base Qty

Rule Spare Qty = CEILING(Required Qty x Spare %, Quantity Increment)

Kit Demand = CEILING(
  MAX(Required Qty + Rule Spare Qty + Manual Extra, Minimum Kit Qty),
  Quantity Increment
)
```

The hidden Procurement Summary groups all three phases by Item ID and then calculates purchasing:

```text
Total Item Demand = SUM(Kit Demand for every line using the Item ID)
Net Need = MAX(0, Total Item Demand + Target Stock - On Hand - Already Committed)
Order Qty = IF(Net Need = 0, 0, CEILING(MAX(Net Need, Minimum Order Qty), Pack Size))
Extended Cost = Order Qty x Unit Cost
```

This ordering is important. Inventory is subtracted before vendor-pack rounding. Minimum Kit Qty and Minimum Order Qty are different business rules and are stored separately.

## Revit Export

The adjacent `NeoviRevitEnergyExport` repository includes one **Site BOM** Revit button. Its popup provides four explicit actions:

1. **Save bundled Site BOM checklist template** writes the pinned 21-column, 276-item Site-only shipping checklist with stages `1`, `2`, and `3`, nine predetermined Site Teams and trade categories, detailed Systems, fixed Team Scopes, and blank Project, Revision, and Quantity. It is a versioned bundled template, not a model-derived export, and does not require an open project.
2. **Export blank Project Inputs template** writes the 12 required columns plus the current contract-defined input rows. Input Key, Record Type, Unit, Source, Source Reference, Location, Notes, Schema ID, and Schema Version are populated; Project, Revision, and Value are intentionally blank. It does not inspect the model and does not require `BOM Revision` or installed parameters.
3. **Export populated Revit inputs** exports the real project data and enforces the revision and parameter requirements below.
4. **Install or refresh Site BOM parameters** prepares the active host or linked source model for populated exports.

The no-quantity CSV is a fill-in checklist for the current project-input contract while the model takeoff is not ready. It may replace the Google Sheet's Project Inputs tab, but it cannot pass final approval validation until Project, Revision, and Value are completed.

To regenerate the filled no-quantity files directly from this repository, run:

```powershell
npm.cmd run build:no-quantity-inputs
```

This creates two CSVs in `outputs/NeoviBOM/`:

- `05-Google-Sheet/Neovi-Site-BOM-Project-Inputs-No-Quantities.csv` contains the 19 operational input rows currently consumed by the Google Sheet rules. Its `Location` begins with `1`, `2`, or `3`.
- `01-Catalog/Neovi-Site-BOM-Checklist.csv` is the human-facing shipping checklist. It contains the 276 Site BOM lines only: items that must be delivered, rented, or brought to the jobsite. Factory equipment, factory consumables, and factory-production takeoff facts are intentionally excluded. Every row retains `Schema ID`, `Schema Version`, `Catalog Version`, `Project`, and `Revision`. `Stage` uses exactly `1`, `2`, or `3`. `Site Team` and `Team Scope` are predetermined by the contract rather than selected by field crews. Blank `Quantity` remains beside `Item`. `Category` uses nine broad controlled trade groups, while `System` preserves details such as Hot Water, Solar, Purlins, or Exterior Doors. `Line ID` identifies the occurrence and `Item ID` identifies the purchasable product. `Catalog ID` is the permanent identifier and `Category Path` gives the nested folder grouping.

After generating and reviewing a release, synchronize the pinned contract, catalog, and checksum manifest into the adjacent Revit repository:

```powershell
npm.cmd run sync:revit
```

Open **Neovi > BOM CSV > Site BOM** and choose **Install or refresh Site BOM parameters** in the host project and each linked source model that will contain tagged elements. The action installs stable-GUID shared parameters from the bundled `NeoviSiteBom.sharedparams.txt` file. It binds `BOM Revision` to Project Information and the other fields as instance parameters on the supported model categories.

Set the `BOM Revision` text parameter in Revit Project Information before exporting. Eligible host-model or loaded-link elements use these parameters:

| Revit parameter | Required? | Purpose |
|---|---:|---|
| `BOM Input Key` | Yes | Stable snake-case key such as `wall_connection_count` |
| `BOM Quantity` | Sometimes | Dimensionless Number contribution expressed in `BOM Unit`; only `EA` defaults to `1` per element |
| `BOM Unit` | No | Purchasing/input unit; defaults to `EA` |
| `BOM Record Type` | No | `FACT` or `DIRECT_ITEM`; defaults to `FACT` |
| `BOM Source Reference` | No | Human-readable mark/reference; Revit UniqueId is always retained |
| `BOM Location` | No | Level, zone, cassette, panel, or delivery location |
| `BOM Notes` | No | Model-side review note |

The exporter reads only the shared parameters installed by the Site BOM setup action, identified by stable GUID. It refuses measured Length/Area parameters masquerading as `BOM Quantity`. For every unit other than `EA`, `BOM Quantity` is required instead of silently assuming one. Multiple elements may use the same Input Key; Google Sheets sums distinct source rows. The exporter includes a stable source reference so exact duplicates can be blocked even if their displayed location changes. Supported bindings include architectural, structural, equipment, plumbing pipe, duct, conduit, and cable-tray categories.

CSV columns, in order:

```text
Schema Version, Project, Revision, Record Type, Input Key, Value,
Unit, Source, Source Reference, Location, Notes, Schema ID
```

Project Inputs schema ID `neovi.site-bom.project-inputs` version `2.0` is the current interchange contract. The shipping checklist uses schema ID `neovi.site-bom.catalog` version `2.0` and catalog version `0.4.0`.

Unit values describe the measured quantity, not the container used to purchase it:

| Kind | Units |
|---|---|
| Count / time | `EA`, `DAY` |
| Length | `IN`, `FT` |
| Area / volume | `SQFT`, `CUFT` |
| Liquid quantity | `OZ`, `QT`, `GAL` |
| Weight / density | `LB`, `PCF` |

Packaging such as roll, bottle, can, bag, sheet, tube, or cylinder belongs in the item specification and pack-size fields. For example, flashing is measured in `FT`, concrete board in `SQFT`, compound in `LB`, sealant in `OZ`, and propane in `LB`.

## Create the Master Google Sheet

Run the repository checks:

```powershell
npm.cmd run check
```

`build:template` now creates and validates one self-contained native Google Sheets builder without requiring Excel or an `.xlsx` file:

```text
outputs/NeoviBOM/05-Google-Sheet/Neovi-Site-BOM-Builder.gs
```

The generated master starts with blank Active Project, Active Revision, and Project Inputs. The sample project files in `config/` are validation fixtures and are not loaded into the operational master.

Then:

1. Create one blank Google Sheet and name it **Neovi Site BOM - MASTER TEMPLATE**.
2. Open **Extensions > Apps Script**.
3. Delete the default editor contents.
4. Paste the entire generated `Neovi-Site-BOM-Builder.gs` file into the editor and save.
5. Select `buildSiteBomTemplate` and click **Run**.
6. Approve the requested spreadsheet permission.
7. Confirm the build warning. It replaces the blank spreadsheet's sheets with the Site BOM template.
8. Return to the Sheet and reload it once so the **Site BOM** menu appears.

The native builder:

- creates every master, phase, import, audit, and procurement sheet directly in Google Sheets;
- leaves only Foundation, Panels, and Finishing visible;
- converts Accounted For cells into native Google Sheets checkboxes;
- hard-protects formula and identifier ranges while leaving project-entry cells editable;
- rebuilds phase and procurement rows from the editable master tables while preserving project values by stable ID;
- adds a Site BOM menu for project-input imports and admin-sheet access.

The Apps Script is contained inside the native Google Sheet and uses `@OnlyCurrentDoc` so its spreadsheet permission is limited to that file. It is not a website, external service, Excel workbook, or separate application. After the master has been created, normal project refreshes require only the Revit CSV.

## Create or Refresh a Project

1. Open **Neovi > BOM CSV > Site BOM** and choose **Install or refresh Site BOM parameters** once in the host and each tagged linked model.
2. In Revit Project Information, set the approved `BOM Revision`.
3. Open the same **Site BOM** button and choose **Export populated Revit inputs**.
4. Make a copy of the untouched Google Sheet master.
5. Use **Site BOM > Show admin sheets**.
6. In Template Settings, set Active Project and Active Revision to exactly match the CSV.
7. Use **Site BOM > Prepare Project Inputs import**.
8. Choose **File > Import > Upload** and select the CSV.
9. Choose **Replace current sheet**. Do not append, and do not import over a phase tab.
10. Review Import Audit. Its issue count must be zero.
11. Review Foundation, Panels, and Finishing.
12. Enter project-only Manual Base Qty, Manual Extra, Needed By, Status, Accounted For, and adjustment notes in yellow cells. A manual line needs a positive base quantity unless its Status is explicitly `Not Required`.
13. In Procurement Summary, enter On Hand, Already Committed, purchasing status, and notes once per Item ID.
14. Resolve every Needs Review item and complete the required Accounted For checks.
15. Run **Site BOM > Validate before approval**. It blocks approval if the import/master structure is invalid, any review message remains, any phase line is unaccounted, or an orderable procurement row is still unaccounted or marked Needs Review.
16. Run **Site BOM > Apply template setup** to validate the structure again, hard-protect formulas, and hide support sheets.

Refreshing Project Inputs does not overwrite project adjustments, inventory, status, notes, or the master formulas.

## Customizing the Master

`config/site-bom.contract.json` is the canonical interchange contract for schemas, numeric stages, Site Teams, Team Scopes, categories, units, sources, and input definitions. `config/site-bom.template.json` is the canonical catalog seed. The native Google Sheet is the fast operational editor. After changing master Items, BOM Lines, Rules, or list values in Google Sheets, use **Site BOM > Download master snapshot** and save the downloaded JSON with the project/release records. Snapshot format 2 retains System and Delivery Stage; team assignments are rehydrated from the current contract. Format 1 snapshots remain readable through the legacy migration path.

```powershell
npm.cmd run build:template -- --snapshot path\to\neovi-site-bom-master-0.4.0.json
```

| Change | Master table |
|---|---|
| Rename or specify a purchasable product | Items |
| Approve a specification | Items → Specification Approved |
| Change vendor, part, cost, pack, or minimum order | Items |
| Move an occurrence between phases/work areas/categories/systems/delivery stages/kits | BOM Lines |
| Reuse one SKU in another kit | New BOM Line with the existing Item ID |
| Change multiplier, spare, increment, or minimum kit | Rules |
| Add or change a Revit input definition | `site-bom.contract.json`, then Rules and `npm.cmd run sync:revit` |
| Change categories, category codes, stages, units, or sources | `site-bom.contract.json` |
| Add statuses or owners | Template Settings |

You may add list values, but keep the sentinel entries used by the formulas: `Needs Review`, `Unassigned`, `EA`, `TBD`, `Order`, `REVIT`, `NEEDS_REVIEW`, and `APPROVED`.

For an existing row, edit the appropriate master table. For a new product occurrence, add one Items row if the Item ID is new, one BOM Lines row, and one Rules row. Every imported Input Key must also have one Expected Input Unit in Rules. Then choose **Site BOM > Sync template changes**. The sync regenerates formulas from code instead of copying an editable phase row, moves or creates phase and procurement rows, and retains project values by stable Line ID or Item ID.

Never overwrite calculated cells on the three phase tabs. They are hard-protected. Change the relevant hidden master row instead, run the sync, test it with a known input, increment the template version, download a master snapshot, and publish a new master copy.

The Sheet owner should run sync, setup, and snapshot commands because those operations rewrite protected formula ranges. Other collaborators can use the unprotected yellow project-entry cells.

The guarded limits are 997 Items/master rows, 993 lines in any one phase, and 1,000 imported Project Input rows. Sync or approval validation fails explicitly if a limit is exceeded; rows are never silently omitted.

## Validation and Safety

The code and workbook logic reject or flag:

- duplicate Line IDs;
- conflicting purchasing data for one shared Item ID;
- invalid source modes or scopes;
- missing Input Keys for calculated rules;
- unknown Input Keys, invalid key syntax, mixed units, or units that do not match the rule contract;
- negative assumptions, quantities, inventory, or minimums;
- mixed schema, project, or revision values;
- duplicate Input Key + Source + Source Reference rows, independent of displayed location;
- missing source references, units, or sources;
- invalid project statuses, checkboxes, dates, manual quantities, inventory values, or duplicated list values;
- zero manual demand unless the line is explicitly marked `Not Required`;
- manual extras without reasons;
- unapproved specifications;
- missing procurement method, vendor, part number, or unit cost when required;
- factory-only lines on the Site BOM.

Only a Rules status of `APPROVED` clears calculation review. `READY_FOR_TEST` remains blocked from purchasing.

Project-input CSVs must contain exactly the 12 documented columns in order. CSV text that begins with `=`, `+`, `-`, or `@` is escaped by the exporters, and approval validation rejects formula cells or unexpected columns introduced by another source.

## Current Seed Status

The normalized starter list contains:

- 276 BOM Lines;
- 50 Foundation lines;
- 41 Panels lines;
- 184 Finishing lines;
- 19 project Input Keys.

The structure is implemented, but the seed is intentionally not approved for purchasing. Exact specifications, owners, vendors, part numbers, costs, pack sizes, minimum orders, and most calculation rules still require operational or engineering approval. The 4 x 3 floor-plate minimum remains explicitly marked for a 100-versus-250 decision.

Run `npm.cmd run readiness` for the strict release gate. It intentionally returns a nonzero result while placeholders, unapproved specifications, unassigned owners, TBD procurement methods, or unapproved rules remain. Do not describe a catalog as purchasing-approved until that command passes.

## Definition of Done

A project revision is ready only when:

- the native Google Sheet shows only the three phase tabs during normal use;
- Import Audit has zero issues;
- every used line has an approved specification, owner, unit, and calculation rule;
- every orderable Item ID has a procurement method and the required vendor/SKU/cost data;
- inventory has been entered once per Item ID;
- all Needs Review cells are clear;
- every phase line is Accounted For and no orderable procurement row remains unaccounted or in Needs Review status;
- phase totals reconcile to the approved Revit/structural takeoff;
- the project and Revit revision shown in Template Settings match the imported CSV.

## References

- [Autodesk: Export a Schedule](https://help.autodesk.com/cloudhelp/2025/ENU/Revit-DocumentPresent/files/GUID-B2CCAC4F-1D38-4D5D-B4D1-95619D1B7EBE.htm)
- [Google: Import data into Sheets](https://support.google.com/docs/answer/12236443)
- [Google: Protect and hide sheets](https://support.google.com/docs/answer/1218656)
- [Google: Add and use checkboxes](https://support.google.com/docs/answer/7684717)

### Rebuild the Franklin and Santa Rita project reports

Run `python scripts/rebuild-project-reports.py --package`. Add `--rescan` to read the original Everything exports again. Named-family mapping rules are saved in `scripts/map-project-takeoffs.py`; absence of BOM tags does not prevent those mappings. Counts retain element keys, include structural links where specified, and exclude view-specific, demolished and design-option elements.

The report engine calculates required, spare and base kit independently of purchasing data. Base kit excludes unentered extras and uses catalog rounding/minimum rules; it is not the final order. Missing takeoffs remain N/A, not zero.

Optional `outputs/NeoviBOM/_Internal/Model-Data/franklin-purchasing-inputs.json` and `santa-rita-purchasing-inputs.json` accept objects keyed by Item ID. Fields are `manualExtra`, `onHand`, `committed`, `targetStock`, `packSize`, `minimumOrder`, and `unitCost`. Enter actual values (including explicit zero where confirmed). Rebuilding then calculates final kit, net, order and cost as their dependencies become available. The PDF shows the base-kit subtotal; the CSV additionally contains final kit demand.

The full mapping register is `config/model-item-mapping-register.json`: every one of the 276 items has explicit source categories, search criteria and measurement requirements. These searches only collect evidence; numeric quantities require the checked selectors in `scripts/map-project-takeoffs.py` and `scripts/model_takeoff_rules.py`.

Each project also exports a 276-row `*-mapping-audit.csv` and a detailed JSON with candidate element keys and source types. Status distinguishes measured values, derived allowances, catalog allowances, conflicting/missing inputs, no identified source, and undefined catalog items. No match means unknown, not zero. Changed source file size/time invalidates the scan cache. Run `npm run test:mappings` for selector tests.
# Category catalog and annotated updates

The current delivery is in `outputs/NeoviBOM/`.
Start with `03-Categories/`: each root has a related-items PDF, and nested
folders contain item CSVs with formulas and separate Franklin/Santa Rita results.
`01-Catalog/Catalog-Folder-Index.csv` links every active item to its folder.

Permanent identifiers (`TOOL-1`, `FAST-1`, `FIX-1`, etc.) are stored in
`config/catalog-identities.json`. The suffix is an arbitrary-length decimal
string, allocated with BigInt. Existing identifiers remain unchanged when
items move, and retired identifiers are never reused. Phase/stage section
numbers and legacy FND/PAN/FIN IDs remain separate from these catalog IDs.

To add an item, give it a new legacy ID, `inventoryPrefix` and a `categoryPath`
array in `config/site-bom.template.json`, then run `npm run catalog:sync`.
Do not edit existing IDs or recycle deleted numbers. The sync also updates
the expected catalog size. Run `npm run check`, then
`python scripts/rebuild-project-reports.py --all-models --package` to refresh
the delivery. Original large model exports stay in Downloads.

The annotated September 15 edits, including retirement/replacement links,
are recorded in `config/catalog-revision-2026-09-15.json` and published as
`04-Audits/Catalog-Changes.pdf` and `.csv`. A missing measurement remains N/A; planning
estimates stay separate. The washer count interpretation is explicitly pending
until the user confirms whether ten washers applies to a bolt/nut pair or to
each component.


## Full list audit

Run `npm run audit:viewer` to rebuild the viewer, test both views, and audit every entry, screenshot quantity, source reference, ordering group, and document link. The item-by-item findings are in [Full-List-Audit.md](outputs/NeoviBOM/04-Audits/Full-List-Audit.md) with machine-readable results alongside it. `npm run check`, `npm run test:mappings`, and `npm run verify:data` cover the underlying catalog/calculations/exports. `npm run readiness` separately identifies purchasing inputs still requiring approval or completion; software tests passing does not clear those findings.
