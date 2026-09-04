# Neovi Site BOM

## Final Deliverable

The operational deliverable is one native Google Sheet with exactly three visible tabs:

1. **Foundation**
2. **Panels**
3. **Finishing**

Each phase tab contains its own work areas, categories, kits, items, quantities, purchasing information, status, and review issues. There is no Site BOM website, database, server, API, or live Google/Revit connection.

The workflow uses two temporary file types for specific purposes:

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
        +----> no-quantity Project Inputs checklist (22 populated input rows)
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

1. **Save bundled Site BOM checklist template** writes the pinned 21-column, 168-item Site-only shipping checklist with stages `1`, `2`, and `3`, nine predetermined Site Teams and trade categories, detailed Systems, fixed Team Scopes, and blank Project, Revision, and Quantity. It is a versioned bundled template, not a model-derived export, and does not require an open project.
2. **Export blank Project Inputs template** writes the 12 required columns plus the 22 current contract-defined input rows. Input Key, Record Type, Unit, Source, Source Reference, Location, Notes, Schema ID, and Schema Version are populated; Project, Revision, and Value are intentionally blank. It does not inspect the model and does not require `BOM Revision` or installed parameters.
3. **Export populated Revit inputs** exports the real project data and enforces the revision and parameter requirements below.
4. **Install or refresh Site BOM parameters** prepares the active host or linked source model for populated exports.

The no-quantity CSV is a fill-in checklist for the current project-input contract while the model takeoff is not ready. It may replace the Google Sheet's Project Inputs tab, but it cannot pass final approval validation until Project, Revision, and Value are completed.

To regenerate the filled no-quantity files directly from this repository, run:

```powershell
npm.cmd run build:no-quantity-inputs
```

This creates two CSVs in `outputs/site-bom-v0.4.0/`:

- `Neovi-Site-BOM-Project-Inputs-No-Quantities.csv` contains the 22 operational input rows currently consumed by the Google Sheet rules. Its `Location` begins with `1`, `2`, or `3`.
- `Neovi-Site-BOM-All-Discussed-Items-No-Quantities.csv` is the human-facing shipping checklist. It contains the 168 Site BOM lines only: items that must be delivered, rented, or brought to the jobsite. Factory equipment, factory consumables, and factory-production takeoff facts are intentionally excluded. Every row retains `Schema ID`, `Schema Version`, `Catalog Version`, `Project`, and `Revision`. `Stage` uses exactly `1`, `2`, or `3`. `Site Team` and `Team Scope` are predetermined by the contract rather than selected by field crews. Blank `Quantity` remains beside `Item`. `Category` uses nine broad controlled trade groups, while `System` preserves details such as Hot Water, Solar, Purlins, or Exterior Doors. `Line ID` identifies the occurrence and `Item ID` identifies the purchasable product.

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
outputs/site-bom-v0.4.0/Neovi-Site-BOM-Builder.gs
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

- 168 BOM Lines;
- 19 Foundation lines;
- 24 Panels lines;
- 125 Finishing lines;
- 22 project Input Keys.

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
