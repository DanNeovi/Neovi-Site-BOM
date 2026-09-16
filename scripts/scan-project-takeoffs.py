import ijson,json,collections
from pathlib import Path
cats={'Structural Framing','Structural Connections','Bolts','Structural Columns','Generic Models','Plumbing Fixtures','Plumbing Equipment','Electrical Equipment','Mechanical Equipment','Casework','Gutters','Sprinklers','Pipes','Pipe Fittings','Structural Foundations','Doors','Windows','Floors','Walls','Roofs','Ceilings','Rooms','Electrical Fixtures','Lighting Fixtures','Electrical Circuits','Conduits','Conduit Fittings','Cable Trays','Ducts','Duct Fittings','Duct Accessories','Mechanical Equipment','Fascias','Soffits','Railings','Specialty Equipment','Furniture','Assemblies'}
for slug in ['franklin','santa-rita']:
 meta=json.load(open('outputs/NeoviBOM/_Internal/Model-Data/'+slug+'-evidence.json'))
 rows=[]
 with open(meta['source'],'rb') as f:
  for e in ijson.items(f,'elements.item',use_float=True):
   if e.get('category') not in cats or e.get('viewSpecific') or e.get('phaseDemolished') or e.get('designOption'): continue
   rows.append({k:v for k,v in e.items() if k not in ['geometry','boundingBox','mesh']})
 Path('outputs/NeoviBOM/_Internal/Model-Data/'+slug+'-takeoff-elements.json').write_text(json.dumps(rows))
 groups=collections.Counter((e.get('sourceKey'),e.get('phaseCreated'),e.get('category'),e.get('family',''),e.get('type')) for e in rows)
 Path('outputs/NeoviBOM/_Internal/Model-Data/'+slug+'-type-census.txt').write_text('\n'.join(str(k)+' : '+str(v) for k,v in groups.items()))
 stat=Path(meta['source']).stat()
 Path('outputs/NeoviBOM/_Internal/Model-Data/'+slug+'-scan-manifest.json').write_text(json.dumps({'schema':'mapping-scan-2','source':meta['source'],'sourceBytes':stat.st_size,'sourceMtimeNs':stat.st_mtime_ns,'categories':sorted(cats),'retainedElements':len(rows)}))
 print(slug,len(rows))
