"""Stream every local model and audit every catalog selector and unit, without category blind spots."""
import collections,csv,json,math,re,sys,time,hashlib
from pathlib import Path
import ijson
from model_takeoff_rules import eligible
from project_model_mapper import map_model
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/NeoviBOM/04-Audits/All-Models';OUT.mkdir(parents=True,exist_ok=True)
register=json.loads((ROOT/'config/model-item-mapping-register.json').read_text())
catalog=json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())
RULE_HASH=hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in ['config/model-item-mapping-register.json','config/site-bom.template.json','config/catalog-revision-2026-09-15.json','scripts/model_takeoff_rules.py','scripts/opening_takeoffs.py','scripts/project_model_mapper.py','scripts/audit-all-download-models.py'])).hexdigest()
patterns={lid:re.compile(r'\b(?:'+'|'.join(r['search'])+')',re.I) for lid,r in register.items()}
unit_specs={'FT':'length','SQFT':'area','CUFT':'volume','LB':'mass','OZ':'volume'}
def unit_evidence(e,unit):
 if unit=='EA':return True
 spec=unit_specs.get(unit)
 return bool(spec) and any(p.get('scope')=='instance' and p.get('hasValue') and str(p.get('dataType','')).startswith('autodesk.spec.aec:'+spec+'-') and isinstance(p.get('doubleValue'),(int,float)) and math.isfinite(p['doubleValue']) for p in e.get('parameters',[]))
def scan(source):
 dest=OUT/(source.stem+'.audit.json');stat=source.stat()
 if dest.exists() and '--rescan' not in sys.argv:
  old=json.loads(dest.read_text())
  if old.get('bytes')==stat.st_size and old.get('mtimeNs')==stat.st_mtime_ns and old.get('ruleHash')==RULE_HASH:return old
 metadata={}
 with source.open('rb') as f:
  for prefix,event,value in ijson.parse(f,use_float=True):
   if prefix=='elements' and event=='start_array':break
   if event in ('string','number','boolean','null'):metadata[prefix]=value
 results={l['lineId']:{'line':l['lineId'],'item':l['description'],'unit':l['unit'],'phase':l['phase'],'stage':l['deliveryStage'],'section':l['categorySection'],'candidates':0,'excluded':0,'unitCompatibleCandidates':0,'outsidePreviousCategories':0,'groups':{},'sampleKeys':[]} for l in catalog}
 seen=set();duplicates=0;total=0;accepted=0;cache={};categories=collections.Counter();phases=collections.Counter();physical=[]
 with source.open('rb') as f:
  for e in ijson.items(f,'elements.item',use_float=True):
   total+=1;categories[e.get('category','')]+=1;phases[e.get('phaseCreated','')]+=1
   key=e.get('key');dup=key in seen
   if key:seen.add(key)
   if dup:duplicates+=1
   ok=eligible(e) and not dup
   if ok:
    accepted+=1
    physical.append({k:v for k,v in e.items() if k not in ['geometry','boundingBox','mesh']})
   text=' '.join(str(e.get(k,'')) for k in ('category','family','type','name'))
   text+=' '+' '.join(str(p.get('displayValue','')) for p in e.get('parameters',[]) if p.get('hasValue') and p.get('name') in ('Description','BIMSF_Description','Part Description','Part Number','System Name','System Type','Material','Assembly Name','Cable Size','Cable Type','Load Name','IFC Material Name'))
   text=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',text).replace('_',' ')
   if text not in cache:cache[text]=[lid for lid,p in patterns.items() if p.search(text)]
   for lid in cache[text]:
    r=results[lid]
    if not ok:r['excluded']+=1;continue
    r['candidates']+=1;r['unitCompatibleCandidates']+=unit_evidence(e,r['unit'])
    r['outsidePreviousCategories']+=e.get('category') not in register[lid]['categories']
    identity=' | '.join(str(e.get(k,'')) for k in ['category','family','type','sourceKey'])
    if identity not in r['groups']:r['groups'][identity]={'count':0,'parameters':{},'sampleKeys':[]}
    g=r['groups'][identity];g['count']+=1
    if len(g['sampleKeys'])<3:g['sampleKeys'].append(key)
    for p in e.get('parameters',[]):
     if p.get('hasValue') and (p.get('dataType','').startswith('autodesk.spec.aec:') or any(w in p.get('name','').lower() for w in ['fastener','number','assembly','system','material','length','diameter'])):
      token=p.get('scope','')+':'+p['name'];v=str(p.get('displayValue',''))
      if token not in g['parameters']:g['parameters'][token]=[]
      if v not in g['parameters'][token] and len(g['parameters'][token])<6:g['parameters'][token].append(v)
    if len(r['sampleKeys'])<5:r['sampleKeys'].append(key)
 mapped,opening=map_model(physical) if metadata.get('coordinates.lengthUnit')=='ft' else ({},{})
 for r in results.values():
  r['testStatus']='NO_MATCH' if not r['candidates'] else 'MATCH_UNIT_MISSING' if not r['unitCompatibleCandidates'] else 'CANDIDATE_UNIT_PRESENT'
  r['limitation']='Search evidence only. Physical unit compatibility does not establish installation scope or purchasable quantity.'
  evidence=mapped.get(r['line'])
  r['mappedQuantity']=evidence['value'] if evidence else None
  r['mappingStatus']=evidence.get('status','MODEL_MEASURED') if evidence else 'UNRESOLVED'
  if evidence:r['testStatus']='MAPPED_QUANTITY'
 result={'source':str(source),'bytes':stat.st_size,'mtimeNs':stat.st_mtime_ns,'ruleHash':RULE_HASH,'mapped':mapped,'metadata':metadata,'elementsScanned':total,'eligibleInstances':accepted,'duplicateKeys':duplicates,'categories':dict(categories),'phases':dict(phases),'items':list(results.values())}
 dest.write_text(json.dumps(result,indent=2));print(source.name,total,'elements;',len(results),'item/unit checks',flush=True)
 return result
sources=sorted(Path('C:/Users/danie/Downloads').glob('*.neovi-model.json'))
reports=[scan(p) for p in sources]
with (OUT/'All-Models-Every-Item-Unit.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['Model','Source','Section','Stage','Phase','Line','Item','BOM Unit','Test Status','Eligible Candidates','Unit-Compatible Candidates (not takeoff)','Outside Prior Categories','Excluded Candidates','Requirement','Mapped Quantity','Mapping Status'])
 for report in reports:
  assert {r['line'] for r in report['items']}=={r['lineId'] for r in catalog}
  for r in report['items']:w.writerow([report['metadata'].get('project.title'),report['source'],r['section'],r['stage'],r['phase'],r['line'],r['item'],r['unit'],r['testStatus'],r['candidates'],r['unitCompatibleCandidates'],r['outsidePreviousCategories'],r['excluded'],register[r['line']]['requirement'],r['mappedQuantity'] if r['mappedQuantity'] is not None else 'N/A',r['mappingStatus']])
(OUT/'summary.json').write_text(json.dumps({'models':len(reports),'itemUnitChecks':len(catalog)*len(reports),'elementsScanned':sum(r['elementsScanned'] for r in reports),'sources':[{'source':r['source'],'elements':r['elementsScanned'],'coordinateUnit':r['metadata'].get('coordinates.lengthUnit'),'duplicates':r['duplicateKeys']} for r in reports]},indent=2))
print('COMPLETE',len(reports),'models',len(catalog)*len(reports),'item/unit checks',flush=True)
