# SiteBOM project workspace audit — 2026-11-01

## Tested setup

- Local website: `http://127.0.0.1:8765/dashboard`, bound to loopback. The Windows task `Neovi-SiteBOM-Local` was running. Its last source check returned exit code 0. The server polls every 300 seconds while the signed-in computer is on.
- Private Drive mount: `G:\My Drive\SiteBOM`, account `danielb@neovi.co`. The project registry is `_Internal/project-registry.json`. It contains Monroe, Franklin, and Santa Rita. Private raw/model, PDF, report, and audit folders exist for each.
- Monroe: private Drive has a 1,967,113,869-byte model and four AI Core PDFs. Its processed HTML export exists. The Monroe processor reported “Already current; no processing needed.” It selects the model by exact Revit project name and number. The current BOM remains a review pipeline, not an approved purchase order.
- Franklin and Santa Rita: each has two saved report files. Neither has a connected model in its private project folder; both intake states say `waiting_for_model`. Their saved reports are snapshots, not results of the new intake pipeline.
- Google Sheet: read-only live API check returned revision 6 with 301 items and 167 categories. The GitHub Pages homepage and editor each returned HTTP 200. A successful shared edit/save was not exercised in this audit. The local project registry and files do not automatically publish to that Sheet or GitHub Pages.

## Changes made

- Replaced the Monroe-only local dashboard with a project menu and separate detail page for each project.
- Added private Drive project registration and folder setup. New projects can start with a selected NeoviOne export or connect/upload a model later. PDF uploads go to that project's AI Core folder.
- Added project identity checks (name, project number, and cloud model GUID when available) and duplicate-model assignment checks. Raw files are not served through local preview routes.
- Added a project intake worker. It copies a connected model to the correct private Drive folder, verifies the staged copy, and streams a category/source census. The result is labeled raw model coverage and does not become a BOM quantity.
- Kept Monroe's existing calculation/export pipeline. The combined worker checks Monroe and registered intake projects independently.

## Test evidence

| Check | Result |
| --- | --- |
| Python unit and HTTP integration tests | 53 passed; isolated create, duplicate rejection, cross-origin rejection, model/PDF uploads, private raw route, and category census covered |
| JavaScript validation and unit tests (`npm run check`) | 65 passed; template validator still reports approval/manual-input warnings |
| Data export verifier | PASS: 276 items, 2 generated report projects, 7 sheets, 9,384 quantity checks, 268 zero checks, 8,571 unknown checks, source parity true |
| Live local API | `/api/projects`, all three `/api/projects/<id>`, and `/api/model-exports` returned HTTP 200; raw `/preview/00-Raw/...` returned 404 |
| Browser rendering | Project menu and Monroe/Franklin detail pages opened in a real browser; project cards, Drive links, reports, and model choices rendered |
| Processing | `python scripts/auto_process_projects.py` exited 0 and checked three projects without repeating Monroe's heavy scan |

## Limits requiring future work

1. **New-project quantities:** the generic intake counts source elements only. Each project's material classification, formulas, drawings, and source authority still need review before a reliable BOM can be calculated. Franklin and Santa Rita have saved reports, but the new worker has not regenerated them.
2. **Exports:** Revit or NeoviOne must still create a fresh model export. The local worker discovers and stages it after it appears; it cannot run Revit's exporter itself.
3. **Public sharing:** the GitHub Pages site and shared Sheet still serve Monroe's existing catalog. The new project menu is local to this computer. New projects are not automatically made public or collaborative.
4. **AI:** the local worker indexes the current Monroe drawing set; it does not call Gemini or classify arbitrary drawings automatically.
5. **Availability:** the local menu is available only while this PC, its Drive mount, and the scheduled task are running. Browser HTTP success and a read-only Sheet response do not prove shared write access.

## Operator path

Open the local project menu, enter a name, select an existing model export if available, and select **Create project**. The new workspace appears immediately. Add or connect the model and current PDFs from its page; processing checks on a five-minute interval or by pressing **Check sources now**. Review the raw model coverage and add project-specific BOM rules before treating element counts as quantities.
