"""Finalize one canonical delivery; do not duplicate source trees or ZIPs."""
from pathlib import Path
import csv,json,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'outputs/NeoviBOM'
DATA=DEST/'_Internal/Model-Data'
CATALOG=DEST/'01-Catalog'
AUDITS=DEST/'04-Audits'

def route_generated_reports():
    # Move regenerated CSVs to their final location, keeping a single copy.
    for source in DATA.iterdir():
        if source.suffix not in ('.csv','.md'):continue
        name=source.name;key=name.lower()
        if 'TEST-ONLY' in name:target=AUDITS/'Synthetic-Tests'/name
        elif source.suffix=='.md':target=AUDITS/name
        else:
            project='Franklin' if key.startswith('franklin') else 'Santa-Rita' if key.startswith('santa-rita') else None
            if not project:raise ValueError(f'Unclassified report: {source}')
            target=DEST/'02-Projects'/project/('' if 'all-items-calculations' in key else 'Evidence')/name
        assert source.resolve().is_relative_to(DATA.resolve())
        assert target.resolve().is_relative_to(DEST.resolve())
        target.parent.mkdir(parents=True,exist_ok=True)
        source.replace(target)

def build():
    for part in ('01-Catalog','02-Projects','03-Categories','04-Audits','05-Google-Sheet','_Internal'):
        (DEST/part).mkdir(parents=True,exist_ok=True)
    catalog=json.loads((DATA/'catalog-lines.json').read_text())
    rules=json.loads((ROOT/'config/planning-allowances.json').read_text())['rules']
    with (CATALOG/'Planning-Assumptions.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f)
        writer.writerow(['Catalog ID','Category Path','Section','Stage','Phase','Line','Item','Unit','Driver','Rate','Planning assumption'])
        for line in catalog:
            if line['lineId'] in rules:
                rule=rules[line['lineId']]
                writer.writerow([line['catalogId'],' > '.join(line['categoryPath']),line['categorySection'],line['deliveryStage'],line['phase'],line['lineId'],line['description'],line['unit'],rule['driver'],rule['rate'],rule['assumption']])
    route_generated_reports()
    for script in ('build-additions-review.py','build-related-items-pdf.py','build-catalog-changes.py','audit-supplied-item-list.py'):
        subprocess.run([sys.executable,str(ROOT/'scripts'/script)],check=True,cwd=ROOT)
    (DEST/'START-HERE.md').write_text('''# NeoviBOM

This is the single current output folder. Source code and editable catalog settings live once in the repository, two levels above this folder.

| Folder | Contents |
|---|---|
| [01-Catalog](01-Catalog) | Full checklist CSV, formula guide, related-items PDF, folder index and planning assumptions |
| [02-Projects](02-Projects) | Separate Franklin and Santa Rita calculation PDFs/CSVs, with each project's evidence |
| [03-Categories](03-Categories) | Category PDFs and nested item CSVs, grouped by permanent catalog ID |
| [04-Audits](04-Audits) | Changes, completeness checks, model audit, arithmetic tests and prior-addition history |
| [05-Google-Sheet](05-Google-Sheet) | Current Apps Script builder and blank project-input CSV |
| _Internal | Unique model scan data, machine-readable results and cleanup provenance needed for rebuilding |

Open these first:

- [Excel workbook](NeoviBOM.xlsx) - filterable catalog and both projects
- [Software JSON export](NeoviBOM.json) - the same data with full source references
- [Full checklist CSV](01-Catalog/Neovi-Site-BOM-Checklist.csv)
- [Formula guide PDF](01-Catalog/Neovi-Site-BOM-Formula-Guide.pdf)
- [Related items PDF](01-Catalog/Neovi-All-Related-Items-Side-by-Side.pdf)
- [Franklin PDF](02-Projects/Franklin/Franklin-All-Items-Calculations.pdf)
- [Santa Rita PDF](02-Projects/Santa-Rita/Santa-Rita-All-Items-Calculations.pdf)

Catalog IDs do not renumber when items move or are removed. Model quantities and planning estimates remain distinct. The bedframe washer multiplier remains pending clarification (20 versus 40 washers per pile).

Rebuild from the repository root with `python scripts/rebuild-project-reports.py --package`. Add `--all-models` to refresh the ten-model audit. The original model exports remain in Downloads. Edit the repository's `config/` files; the output folder has no separate active source tree.

The one-time `_Internal/Superseded-Archive/` holds obsolete generated files, previews and old source copies. Automatic approval review blocked their deletion, so they were moved here reversibly. These files are excluded from the current deliverables and are not used by rebuilds.

A ZIP is created only when explicitly requested with `python scripts/build-delivery-package.py --zip`. Normal rebuilds update this folder directly.
''',encoding='utf-8')
    subprocess.run([sys.executable,str(ROOT/'scripts/verify-catalog-delivery.py')],check=True,cwd=ROOT)
    subprocess.run(['node',str(ROOT/'scripts/export-data.mjs')],check=True,cwd=ROOT)
    if '--zip' in sys.argv:
        archive=shutil.make_archive(str(DEST),'zip',root_dir=DEST.parent,base_dir=DEST.name)
        print(f'ZIP: {archive}')
    print(f'Current folder: {DEST}')

if __name__=='__main__':build()
