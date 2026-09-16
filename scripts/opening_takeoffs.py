"""Wall-side and opening rules requested by the user; all dimensions are feet."""
from model_takeoff_rules import parameter,select_unique,measured

def dimension(e,name):
    for scope in ('instance','type'):
        v=parameter(e,name,'length',scope)
        if v is not None and v>0:return v
    return None

def opening_size(e):
    # Use rough opening, not a door leaf or zero-width display parameter.
    return dimension(e,'Rough Width'),dimension(e,'Rough Height')

def add_opening_rules(rows,out):
    host=[e for e in select_unique(rows) if e['sourceKey']=='host']
    index={e.get('uniqueId'):e for e in host if e.get('uniqueId')}
    def wall_function(e):
        wall=index.get(e.get('hostUniqueId'),{})
        return parameter(wall,'Function',scope='type') if wall.get('category')=='Walls' else None
    doors=[e for e in host if e['category']=='Doors' and 'garage' not in e.get('family','').lower()]
    exterior=[e for e in doors if wall_function(e)==1]
    def jamb_head(e):
        w,h=opening_size(e)
        return None if w is None or h is None else 2*h+w
    # Host wall resolves mislabeled door-family Function fields.
    if doors and all(wall_function(e) in (0,1) for e in doors):
        measured(out,'FIN-082',exterior,lambda e:1,'COUNT(doors hosted by Exterior walls) x 1 sill pan',
                 'Host wall Function defines exterior; garage vehicle doors excluded','DERIVED_ALLOWANCE')
        measured(out,'FIN-083',exterior,jamb_head,'SUM(exterior door count by size x (2H + W))',
                 'One head and two jambs per exterior opening; threshold handled separately by sill pan; no lap/waste allowance','USER_GEOMETRY_RULE')
    windows=[e for e in host if e['category']=='Windows' and not any(x in (e.get('family','')+' '+e.get('type','')).lower() for x in ('skylight','suntunnel','sun_tunnel','sun tunnel'))]
    def window_trim(e):
        w,h=opening_size(e);f=wall_function(e)
        return None if w is None or h is None or f not in (0,1) else 2*(w+h)*(2 if f==0 else 1)
    measured(out,'FIN-087',windows,window_trim,'SUM(2(W+H) x sides); interior=2, exterior=1',
             'User trim rule: four-sided opening trim, two faces on interior walls and one on exterior walls; skylights excluded','USER_GEOMETRY_RULE')
    # Supplemental wall runs have no existing catalog item; do not mislabel them
    # as window trim or overwrite a placeholder with an unrelated product.
    walls=[e for e in host if e['category']=='Walls' and e.get('family')=='Basic Wall' and 'Stud_' in e.get('type','')]
    def trim_run(e):
        length=dimension(e,'Length');f=parameter(e,'Function',scope='type')
        return None if length is None or f not in (0,1) else length*(2 if f==0 else 1)
    extra={}
    measured(extra,'WALL-TRIM',walls,trim_run,'2 x SUM(interior wall Length) + SUM(exterior wall Length)',
             'Gross trim run per user side rule; primary host stud walls only, excluding linked duplicates and additional cladding pieces; openings not deducted','USER_GEOMETRY_RULE')
    if 'WALL-TRIM' in extra:
        entry=extra['WALL-TRIM'];entry['unit']='FT'
        entry['interiorLength']=sum(dimension(e,'Length') for e in walls if parameter(e,'Function',scope='type')==0)
        entry['exteriorLength']=sum(dimension(e,'Length') for e in walls if parameter(e,'Function',scope='type')==1)
        entry['wallDetails']=[dict(key=e['key'],type=e['type'],length=dimension(e,'Length'),sides=2 if parameter(e,'Function',scope='type')==0 else 1,
                                  classification='Interior' if parameter(e,'Function',scope='type')==0 else 'Exterior',trimLength=trim_run(e)) for e in walls]
    opening_details=[]
    for e in doors+windows:
        w,h=opening_size(e);f=wall_function(e)
        opening_details.append(dict(key=e['key'],category=e['category'],type=e['type'],hostWall=e.get('hostUniqueId'),wallFunction=f,width=w,height=h,
                                    sides=2 if f==0 else 1 if f==1 else None,
                                    headAndJambLength=jamb_head(e),perimeter=2*(w+h) if w is not None and h is not None else None))
    for entry in out.values():
        if entry.get('status')=='USER_GEOMETRY_RULE':
            entry['openingDimensions']=[d for d in opening_details if d['key'] in entry['references']]
    return dict(supplemental=extra,openings=opening_details,
                exteriorDoorCount=len(exterior),exteriorDoorJointLength=out.get('FIN-083',{}).get('value'),
                windowPerimeter=sum(d['perimeter'] for d in opening_details if d['category']=='Windows') if windows and all(d['perimeter'] is not None for d in opening_details if d['category']=='Windows') else None)
