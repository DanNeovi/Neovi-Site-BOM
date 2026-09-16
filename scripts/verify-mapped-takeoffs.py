import json,math
from pathlib import Path
root=Path('outputs/NeoviBOM/_Internal/Model-Data')
catalog=json.loads((root/'catalog-lines.json').read_text())
for slug in ['franklin','santa-rita']:
 mapped=json.loads((root/(slug+'-mapped-takeoffs.json')).read_text())
 for line,e in mapped.items():
  if e.get('status')=='CONFIRMED_STANDARD':
   catalog=json.loads((root/'catalog-lines.json').read_text())
   assert e['value']==next(r['fixedQty'] for r in catalog if r['lineId']==line)
   assert e['references']==['config/site-bom.template.json#'+line]
   continue
  assert len(e['references'])==len(set(e['references']))
  assert e['references']==[r['key'] for r in e['elements']]
  assert math.isclose(sum(r['value'] for r in e['elements']),e['value'])
  assert all(r['sourceKey']=='host' for r in e['elements']) if line not in ('PAN-002','PAN-013','FND-012','FND-008') else all(r['sourceKey'].startswith('host/') for r in e['elements'])
 assert mapped['PAN-002']['value']==(161 if slug=='franklin' else 242)
 assert mapped['FIN-064']['value']==(22 if slug=='franklin' else 30)
 print(slug,'source references and sums verified')
 audit=json.loads((root/(slug+'-all-item-mapping-audit.json')).read_text())
 assert {r['lineId'] for r in audit}=={r['lineId'] for r in catalog}
 for row in audit:
  assert row['requirement'] and row['search'] and row['status']
  assert row['mappedQuantity']==(mapped[row['lineId']]['value'] if row['lineId'] in mapped else None)

projects=json.load(open(root/'full-project-calculations.json'))['projects']
for project in projects:
 for r in project['rows']:
  estimate=r.get('planningEstimate')
  if estimate is not None:
   assert r['required'] is None, 'Estimate overwrote verified takeoff'
   assert math.isfinite(estimate) and estimate>=0
   assert r['planningFormula'] and r['planningAssumption'] and r['planningSources']
   assert r['planningBaseKit'] >= estimate+r['planningSpare']
   assert r['order'] is None, 'Planning estimate became actual order'
 assert sum(r['required'] is not None or r.get('planningEstimate') is not None for r in project['rows'])>84
 row=next(r for r in project['rows'] if r['lineId']=='PAN-013')
 expected= (34,4) if 'Santa Rita' in project['project'] else (14,2)
 assert (row['required'],row['spare'])==expected
 assert row['order'] is None and row['cost'] is None
 assert len(row['sourceReferences'].split('; '))==expected[0]
 print(project['project'], 'hold-down calculation verified', expected)
