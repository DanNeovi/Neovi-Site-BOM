"""Cross-check every delivered identity, folder, unit and PDF against the source catalog."""
import csv,json,re
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'outputs/NeoviBOM'
def read_csv(path):
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def verify():
 catalog=json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())
 byid={r['catalogId']:r for r in catalog}
 assert len(byid)==len(catalog)
 checklist=read_csv(DEST/'01-Catalog/Neovi-Site-BOM-Checklist.csv')
 assert {r['Catalog ID'] for r in checklist}==set(byid) and len(checklist)==len(byid)
 for r in checklist:
  original=byid[r['Catalog ID']]
  assert (r['Line ID'],r['Item'],r['Unit'],r['Category Path'])==(original['lineId'],original['description'],original['unit'],' > '.join(original['categoryPath']))
 all_folder_rows=[r for p in (DEST/'03-Categories').rglob('Items.csv') for r in read_csv(p)]
 assert len(all_folder_rows)==len(byid) and {r['Catalog ID'] for r in all_folder_rows}==set(byid)
 for row in all_folder_rows:
  original=byid[row['Catalog ID']]
  assert row['Unit']==original['unit'] and row['Legacy Line ID']==original['lineId']
 expected=set(byid)|{v['catalogId'] for r in catalog for v in r['variants']}
 index=read_csv(DEST/'01-Catalog/Catalog-Folder-Index.csv')
 assert len(index)==len(expected) and {r['Catalog ID'] for r in index}==expected
 for r in index:
  target=(DEST/r['File']).resolve();assert target.is_relative_to(DEST.resolve()) and target.is_file()
 pdfs=['01-Catalog/Neovi-All-Related-Items-Side-by-Side.pdf','01-Catalog/Neovi-Site-BOM-Formula-Guide.pdf','02-Projects/Franklin/Franklin-All-Items-Calculations.pdf','02-Projects/Santa-Rita/Santa-Rita-All-Items-Calculations.pdf']
 pages={}
 for filename in pdfs:
  with fitz.open(DEST/filename) as pdf:
   text='\n'.join(p.get_text() for p in pdf);pages[filename]=len(pdf)
   for r in catalog:
    for key in ('catalogId','lineId'):
     assert re.search(r'(?<![A-Z0-9-])'+re.escape(r[key])+r'(?![A-Z0-9-])',text),(filename,r[key])
   assert 'Round Round' not in text, filename
 roots={r['categoryPath'][0] for r in catalog}
 assert len(list((DEST/'03-Categories').glob('*/Related-Items.pdf')))==len(roots)
 for name in ['Franklin','Santa-Rita']:
  rows=read_csv(DEST/'02-Projects'/name/f'{name}-All-Items-Calculations.csv')
  assert len(rows)==len(byid) and {r['Catalog ID'] for r in rows}==set(byid)
  for r in rows:assert r['Unit']==byid[r['Catalog ID']]['unit']
 report={'status':'PASS','activeItems':len(catalog),'variantItems':len(expected)-len(catalog),'categoryRoots':len(roots),'categoryFolders':len(list((DEST/'03-Categories').rglob('Items.csv'))),'pdfPages':pages,'checks':'Every catalog/legacy ID, checklist/folder/project CSV row, unit, folder link and main PDF presence checked. Layout visually reviewed separately.','pending':'Washer multiplier: 10 per bolt/nut pair versus 10 per individual component.'}
 (DEST/'04-Audits/Delivery-Verification.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
if __name__=='__main__':verify()
