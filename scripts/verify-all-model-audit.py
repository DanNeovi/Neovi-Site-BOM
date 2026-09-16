"""Independent completeness and arithmetic checks across every scanned model/item/unit."""
import csv,json,math
from pathlib import Path
root=Path('outputs/NeoviBOM/04-Audits/All-Models');catalog=json.load(open('outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json'));ids={l['lineId']:l for l in catalog}
reports=[json.loads(p.read_text()) for p in root.glob('*.audit.json')]
sources=list(Path('C:/Users/danie/Downloads').glob('*.neovi-model.json'))
assert {r['source'] for r in reports}=={str(p) for p in sources}
checks=0
for r in reports:
 assert len(r['items'])==len(ids) and {i['line'] for i in r['items']}==set(ids)
 assert r['metadata']['coordinates.lengthUnit']=='ft'
 assert r['duplicateKeys']==0
 assert r['bytes']==Path(r['source']).stat().st_size
 for item in r['items']:
  assert item['unit']==ids[item['line']]['unit']
  assert 0<=item['unitCompatibleCandidates']<=item['candidates']
  assert sum(g['count'] for g in item['groups'].values())==item['candidates']
  e=r['mapped'].get(item['line'])
  assert item['mappedQuantity']==(e['value'] if e else None)
  if e:
   assert e['references']==[x['key'] for x in e['elements']]
   assert len(e['references'])==len(set(e['references']))
   assert all(x['key'].startswith(x['sourceKey']+':') for x in e['elements'])
   assert math.isclose(e['value'],sum(x['value'] for x in e['elements']),abs_tol=1e-8)
   assert math.isfinite(e['value']) and e['value']>=0
   if e.get('circuitDetails'):
    detail=e['circuitDetails']
    expected=len(detail) if item['unit']=='EA' else sum(c['lengthFt']*c['runs'] for c in detail)
    assert math.isclose(e['value'],expected,abs_tol=1e-8)
  checks+=1
rows=list(csv.DictReader((root/'All-Models-Every-Item-Unit.csv').open(encoding='utf-8-sig')))
assert len(rows)==checks==len(sources)*len(catalog)
assert len({(r['Source'],r['Line']) for r in rows})==checks
(root/'verification.json').write_text(json.dumps({'result':'PASS','models':len(reports),'itemUnitChecks':checks,'elementsScanned':sum(r['elementsScanned'] for r in reports),'mappedRows':sum(len(r['mapped']) for r in reports)},indent=2))
print('PASS',len(reports),'models;',checks,'item/unit checks; source keys, units, counts and arithmetic checked')
