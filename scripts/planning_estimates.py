"""Editable budget rates applied to traceable model drivers, separate from takeoffs."""
import json,math
from pathlib import Path
from model_takeoff_rules import measured,select_unique,parameter

def planning_drivers(rows,mapped,opening):
 host=[e for e in select_unique(rows) if e.get('sourceKey')=='host'];d={}
 def count(name,selector):measured(d,name,[e for e in host if selector(e)],lambda e:1,'COUNT(unique model instances)',name)
 measured(d,'floorArea',[e for e in host if e.get('category')=='Floors' and e.get('type','').startswith('Area Takeoff - Standard - Livable')],lambda e:parameter(e,'Area','area'),'SUM(livable takeoff floor Area SQFT)','Livable takeoff floor area; not finish-material measurement')
 count('sinks',lambda e:e.get('family')=='Neovi_GM_Sink Module')
 count('bathroomSinks',lambda e:e.get('family')=='Neovi_GM_Sink Module' and 'Bathroom' in e.get('type',''))
 count('doors',lambda e:e.get('category')=='Doors' and 'garage' not in e.get('family','').lower())
 count('windows',lambda e:e.get('category')=='Windows' and not any(x in (e.get('family','')+' '+e.get('type','')).lower() for x in ['skylight','suntunnel']))
 for name,lid in [('toilets','FIN-046'),('waterHeaters','FIN-028'),('indoorUnits','FIN-052'),('solarPanels','FIN-064'),('hssBeams','FND-012'),('exteriorDoors','FIN-082')]:
  if lid in mapped:d[name]=mapped[lid]
 for name,parts in [('outlets',['FIN-058','FIN-059','FIN-060'])]:
  if all(p in mapped for p in parts):d[name]={'value':sum(mapped[p]['value'] for p in parts),'references':sum([mapped[p]['references'] for p in parts],[])}
 if all(p in d for p in ['sinks','toilets']):d['coldFixtures']={'value':d['sinks']['value']+d['toilets']['value'],'references':d['sinks']['references']+d['toilets']['references']}
 wall=opening['supplemental'].get('WALL-TRIM')
 if wall:
  for name,value in [('wallTrim',wall['value']),('wallLength',wall['interiorLength']+wall['exteriorLength']),('exteriorLength',wall['exteriorLength'])]:
   d[name]={'value':value,'references':wall['references']}
 for name,key in [('doorJoint','exteriorDoorJointLength'),('windowPerimeter','windowPerimeter')]:
  if opening.get(key) is not None:d[name]={'value':opening[key],'references':[e['key'] for e in opening['openings'] if e['category']==('Doors' if name=='doorJoint' else 'Windows')]}
 d['project']={'value':1,'references':['Planning assumption: one project']}
 return d

def estimate_rules(drivers,rules):
 out={}
 for lid,r in rules.items():
  d=drivers.get(r['driver']);rate=r['rate']
  if not isinstance(rate,(int,float)) or not math.isfinite(rate) or rate<0:raise ValueError('Invalid planning rate '+lid)
  if not d:continue
  out[lid]={'value':d['value']*rate,'driver':r['driver'],'driverValue':d['value'],'rate':rate,'assumption':r['assumption'],'references':d['references'],'formula':f"{d['value']:.6g} {r['driver']} x {rate:.6g}",'status':'PLANNING_ESTIMATE'}
 return out
