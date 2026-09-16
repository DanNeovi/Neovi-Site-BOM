import json,math
from pathlib import Path
from model_takeoff_rules import add_extended_rules, add_hardware_rules, add_circuit_rules, select_unique
from opening_takeoffs import add_opening_rules
from planning_estimates import planning_drivers, estimate_rules
from project_model_mapper import map_model
root=Path('outputs/NeoviBOM/_Internal/Model-Data')
for slug in ['franklin','santa-rita']:
 metadata=json.loads((root/(slug+'-evidence.json')).read_text())
 if metadata['metadata'].get('coordinates.lengthUnit') != 'ft': raise ValueError('Unsupported export units')
 rows=select_unique(json.loads((root/(slug+'-takeoff-elements.json')).read_text()))
 out,opening_report=map_model(rows)
 (root/(slug+'-opening-takeoffs.json')).write_text(json.dumps(opening_report,indent=2))
 standards=json.loads(Path('config/confirmed-site-standards.json').read_text())
 catalog=json.loads((root/'catalog-lines.json').read_text())
 for line in catalog:
  if line['lineId'] in standards:
   lid=line['lineId']
   assert line['sourceMode']=='FIXED'
   out[lid]=dict(value=line['fixedQty'],references=['config/site-bom.template.json#'+lid],elements=[],formula='confirmed fixed project quantity',description=standards[lid],verified=True,status='CONFIRMED_STANDARD')
 (root/(slug+'-mapped-takeoffs.json')).write_text(json.dumps(out,indent=2))
 drivers=planning_drivers(rows,out,opening_report)
 estimates=estimate_rules(drivers,json.loads(Path('config/planning-allowances.json').read_text())['rules'])
 (root/(slug+'-planning-estimates.json')).write_text(json.dumps({'drivers':drivers,'estimates':estimates},indent=2))
 print(slug,{k:v['value'] for k,v in out.items()})
