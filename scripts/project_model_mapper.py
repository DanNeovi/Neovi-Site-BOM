"""Shared source-to-item mappings for any Everything model export."""
import math
from model_takeoff_rules import add_extended_rules, add_hardware_rules, add_circuit_rules, select_unique
from opening_takeoffs import add_opening_rules

def map_model(rows):
 rows=select_unique(rows)
 rules={
 'PAN-002':('Structural Connections',('BIMSF-Plate','BIMSF-Plate1'),{'16 GA. 4"x3" Plate','16 GA. 3"x4" Plate'}),
 'PAN-013':('Structural Connections',('Holdown-Simpson_Strong_Tie-HDU-3D','Holdown-Simpson_Strong_Tie-SHDU-3D','CF_SHDU9_3d_Cad_MULT_Prod1','CF_SHD15S_3d_Cad_MULT_Prod','CF_SHD10S_3d_Cad_MULT_Prod','CF_SHD10B_3D_CAD_MULT_Prod'),None),
 'FIN-052':('Mechanical Equipment','Neovi_ME_Ceiling-recessed_Mini-Split',None),
 'FIN-046':('Plumbing Fixtures','Neovi_PF_Toilets',None),
 'FIN-007':('Electrical Equipment','Neovi_EF_Breaker Panel Assembly and VoidM',None),
 'FIN-012':('Electrical Equipment','Neovi_EE_Meter & ShutOff Panel',None),
 'FIN-028':('Plumbing Fixtures','BSB Water Heater',None),
 'FIN-064':('Generic Models','Risen Solar Pack Solar Panel',None),
 'FIN-018':('Sprinklers','Neov_FS_Recessed Sprinkler Head',None),
 'FIN-115':('Gutters','Gutter',None),
 }
 out={}
 for line,(cat,family,types) in rules.items():
  families = family if isinstance(family,tuple) else (family,)
  found={e['key']:e for e in rows if e['category']==cat and e.get('family') in families and (types is None or e.get('type') in types) and e.get('phaseCreated')=='New Construction' and not e.get('phaseDemolished') and not e.get('viewSpecific') and not e.get('designOption') and (line in ('PAN-002','PAN-013') or e.get('sourceKey')=='host')}
  if not found: continue
  refs=[]
  for e in found.values():
   value=1
   if line=='FIN-115':
    ps=[p for p in e['parameters'] if p.get('name')=='Length' and p.get('scope')=='instance' and p.get('hasValue') and str(p.get('dataType','')).startswith('autodesk.spec.aec:length-')]
    if len(ps)!=1: raise ValueError('Ambiguous gutter length')
    value=ps[0]['doubleValue']
    assert math.isfinite(value) and value>=0
   refs.append(dict(key=e['key'],family=e['family'],type=e['type'],value=value,sourceKey=e['sourceKey']))
  formula = 'COUNT(hold-downs) x 1 hardware assembly per hold-down (catalog rule)' if line=='PAN-013' else 'COUNT(indoor units) x 1 mounting assembly (catalog rule)' if line=='FIN-052' else 'COUNT(toilets) x 1 hardware assembly (catalog rule)' if line=='FIN-046' else 'SUM(instance Length in FT)' if line=='FIN-115' else 'COUNT(unique matching model instances)'
  out[line]=dict(value=sum(r['value'] for r in refs),references=[r['key'] for r in refs],elements=refs,formula=formula,description='Simpson/CF hold-downs' if line=='PAN-013' else ', '.join(families),verified=True)
 add_extended_rules(rows,out)
 add_circuit_rules(rows,out)
 opening_report=add_opening_rules(rows,out)
 opening_report['hardwareEvidence']=add_hardware_rules(rows,out)
 # Active catalog retirement is applied consistently for every model export.
 import json
 from pathlib import Path
 retired=json.loads((Path(__file__).resolve().parents[1]/'config/catalog-revision-2026-09-15.json').read_text())['retired']
 for lid in retired:out.pop(lid,None)
 # PAN-010 now describes temporary-bracing screws, not permanent wall joints.
 out.pop('PAN-010',None)
 return out,opening_report
