"""Deterministic model selectors. Names discover candidates; typed parameters measure them."""
import math
import re

def display_parameter(element,name,scope='instance'):
    values=[p.get('displayValue') for p in element.get('parameters',[]) if p.get('name')==name and p.get('scope')==scope and p.get('hasValue')]
    return values[0] if len(values)==1 else None

def parameter(element, name, spec=None, scope='instance'):
    values = [p for p in element.get('parameters', []) if p.get('name') == name and p.get('hasValue') and p.get('scope') == scope]
    if len(values) != 1: return None
    p = values[0]
    if spec and not str(p.get('dataType','')).startswith('autodesk.spec.aec:' + spec + '-'):
        return None
    v = p.get('doubleValue',p.get('integerValue',p.get('stringValue')))
    if spec and (not isinstance(v,(int,float)) or not math.isfinite(v)): return None
    return v

def eligible(e):
    phase_ok = e.get('phaseCreated') == 'New Construction'
    if e.get('category') == 'Rooms' and not e.get('phaseCreated'):
        phase_ok = any(p.get('name') == 'Phase' and p.get('displayValue') == 'New Construction' and p.get('hasValue') for p in e.get('parameters',[]))
    if e.get('category')=='Electrical Circuits' and not e.get('phaseCreated') and e.get('revitClass')=='Autodesk.Revit.DB.Electrical.ElectricalSystem':
        phase_ok=display_parameter(e,'Circuit State')=='Circuit' and bool(display_parameter(e,'Panel')) and bool(display_parameter(e,'Circuit Number'))
    return bool(e.get('key')) and phase_ok and not any(e.get(k) for k in ('phaseDemolished','viewSpecific','designOption'))

def select_unique(elements):
    found = {}
    for e in elements:
        if not eligible(e): continue
        if e['key'] in found and e != found[e['key']]: raise ValueError('Conflicting duplicate element key: '+e['key'])
        found[e['key']] = e
    return list(found.values())

def measured(out, line, elements, measure, formula, description, status='MODEL_MEASURED'):
    elements = select_unique(elements)
    if not elements: return
    refs=[]
    for e in elements:
        value = measure(e)
        # Never silently drop a missing measurement and call a partial sum a total.
        if value is None or not math.isfinite(value) or value < 0: return
        refs.append(dict(key=e['key'], family=e.get('family',''), type=e.get('type',''), sourceKey=e['sourceKey'], value=value))
    out[line] = dict(value=sum(r['value'] for r in refs), references=[r['key'] for r in refs], elements=refs,
                     formula=formula, description=description, verified=True, status=status)

def outlet_class(e):
    if e.get('category') != 'Electrical Fixtures' or e.get('family') not in ('Neovi_EF-Outlet_Horizontal','Neovi_EF-Garage Outlet_Horizontal','Neovi_EF-Exterior Outlet_Horizontal'): return None
    text=(e.get('family','')+' '+e.get('type','')).lower()
    if re.search(r'(30|50)\s*amp',text): return 'FIN-059'
    if 'exterior' in text: return 'FIN-060'
    if any(t in text for t in ('regular_outlet','quad_outlet','bidet_outlet','sub zero_outlet')): return 'FIN-058'
    return None

def add_hardware_rules(rows, out):
    """Preserve measured hardware even when its catalog installation scope is unknown."""
    linked = [e for e in select_unique(rows) if e.get('sourceKey','').startswith('host/')]
    if len({e['sourceKey'] for e in linked}) != 1: return {}
    saddles = [e for e in linked if e.get('family') == 'Base Plate U Saddle']
    # A saddle name alone is insufficient: require the explicit pile-cap host.
    if saddles and all(parameter(e,'Host') == 'Level : Pile Cap' for e in saddles):
        measured(out,'FND-008',saddles,lambda e:1,
                 'COUNT(Base Plate U Saddle hosted at Level : Pile Cap)',
                 'Saddle pile-cap plates at the explicit Pile Cap level; excludes any inferred pile or extension count',
                 'MODEL_SCOPE_RULE')
    extra={}
    for location in ('Site','Shop'):
        bolts=[e for e in linked if e.get('category')=='Bolts' and
               [p.get('displayValue') for p in e.get('parameters',[]) if p.get('name')=='Location'
                and p.get('scope')=='instance' and p.get('hasValue')]==[location]]
        measured(extra,location+' bolts',bolts,lambda e:parameter(e,'Number'),
                 'SUM(bolt pattern Number where Location = '+location+')',
                 'Actual bolt-pattern quantity; catalog connection assignment remains unresolved')
    clips=[e for e in linked if e.get('family')=='BimSf-FloorClip']
    def fasteners(e):
        a=parameter(e,'Leg 1 Number of Fasteners',scope='type')
        b=parameter(e,'Leg 2 Number of Fasteners',scope='type')
        return a+b if a is not None and b is not None else None
    measured(extra,'Floor clip fastener positions',clips,fasteners,
             'SUM(Leg 1 Number of Fasteners + Leg 2 Number of Fasteners)',
             'Positions inside floor clips; blank fastener types and factory/site scope prevent assignment to floor screws')
    return extra

def add_extended_rules(rows, out):
    host = [e for e in select_unique(rows) if e.get('sourceKey') == 'host']
    for line in ('FIN-058','FIN-059','FIN-060'):
        measured(out,line,[e for e in host if outlet_class(e)==line],lambda e: 2 if 'Stacked' in e.get('type','') else 1,
                 'SUM(outlet locations; stacked=2) x 1 cover/assembly', 'Outlet-box-derived allowance; one cover per box, high-amp assemblies separate', 'DERIVED_ALLOWANCE')
    measured(out,'FIN-057',[e for e in host if e.get('family')=='Neovi_EF_Breaker Panel Assembly and VoidM'],lambda e:1,
             'COUNT(breaker panels) x 1 cover', 'Panel-cover allowance; confirm not included with panel', 'DERIVED_ALLOWANCE')
    doors=[e for e in host if e.get('category')=='Doors' and 'garage' not in e.get('family','').lower()]
    ambiguous_doors=[e for e in doors if parameter(e,'Function',scope='type') not in (0,1)
                     or ('_Ex ' in e.get('family','') and parameter(e,'Function',scope='type')!=1)]
    if not ambiguous_doors:
        measured(out,'FIN-082',[e for e in doors if parameter(e,'Function',scope='type')==1],lambda e:1,
                 'COUNT(exterior non-garage door openings) x 1 sill pan','Sill-pan allowance; confirm threshold waterproofing detail','DERIVED_ALLOWANCE')
    measured(out,'FIN-120',[e for e in host if e.get('family') in ('Neovi_GM_LED Profile_Perimeter_FaceBased','Neovi_GM_LED Profile_Midst_FaceBased')],
             lambda e: parameter(e,'VEEV_Length' if e.get('family')=='Neovi_GM_LED Profile_Midst_FaceBased' else 'Light Strip Length','length'),'SUM(profile length FT: Light Strip Length / VEEV_Length)', 'LED profiles; excludes PlanVisibilityLength')
    measured(out,'FIN-121',[e for e in host if e.get('family')=='Neovi_LF_Downlight_Ceiling'],lambda e:1,
             'COUNT(recessed downlights) x 1 circle','Ceiling-circle allowance; confirm installation scope','DERIVED_ALLOWANCE')
    measured(out,'FIN-122',[e for e in host if e.get('category')=='Sprinklers' and 'Sprinkler Head' in e.get('family','')],lambda e:1,
             'COUNT(sprinkler heads) x 1 circle','Ceiling-circle allowance; confirm installation scope','DERIVED_ALLOWANCE')
    measured(out,'FIN-119',[e for e in host if e.get('category')=='Ceilings' and re.search(r'str[ea]t?ch|strech',e.get('type',''),re.I)],
             lambda e:parameter(e,'Perimeter','length'), 'SUM(stretch ceiling Perimeter FT) x 1 boundary profile run',
             'Profile allowance along each ceiling boundary; LED replacement sections and shared profiles need layout review','DERIVED_ALLOWANCE')
    # A room/ceiling join is accepted only for a unique exact XY footprint match,
    # matching level, gypsum type and consistent area. No bounding-box area is used.
    garages=[e for e in host if e.get('category')=='Rooms' and parameter(e,'Name')=='GARAGE']
    ceilings=[]
    for room in garages:
        candidates=[]
        for e in host:
            if e.get('category')!='Ceilings' or 'gyp' not in e.get('type','').lower() or e.get('level')!=room.get('level'): continue
            if not e.get('bounds') or not room.get('bounds'): continue
            if not all(abs(e['bounds'][end][axis]-room['bounds'][end][axis]) < 0.001 for end in ('min','max') for axis in ('x','y')): continue
            area=parameter(e,'Area','area'); room_area=parameter(room,'Area','area')
            if area is not None and room_area is not None and abs(area-room_area)<max(1,room_area*0.01): candidates.append(e)
        if len(candidates)!=1: ceilings=[]; break
        ceilings.extend(candidates)
    measured(out,'FIN-099',ceilings,lambda e:parameter(e,'Area','area'),'SUM(gypsum ceiling Area over matched GARAGE room)',
             'Gypsum ceiling: unique same-level XY room footprint and area match')
    if 'FIN-099' in out: out['FIN-099']['supportingRoomKeys']=[e['key'] for e in garages]
    # Foundation takeoff uses the structural link as the authority. Host copies
    # are retained in the audit but never added to linked structural quantities.
    beams=[e for e in select_unique(rows) if e.get('sourceKey','').startswith('host/') and e.get('category')=='Structural Framing'
           and re.search(r'hollow|\bhss',e.get('family','')+' '+e.get('type',''),re.I)
           and (parameter(e,'Elevation at Top','length') is not None and parameter(e,'Elevation at Top','length')<=0.001)
           and (parameter(e,'Reference Level Elevation','length') is not None and parameter(e,'Reference Level Elevation','length')<=0.001)]
    if len({e['sourceKey'] for e in beams})==1:
        measured(out,'FND-012',beams,lambda e:1,'COUNT(linked hollow beams with top/reference elevation <= 0 FT)',
                 'Foundation-level hollow beams; structural link authority, upper steel and host copies excluded','MODEL_SCOPE_RULE')

def add_circuit_rules(rows,out):
    circuits=[e for e in select_unique(rows) if e.get('sourceKey')=='host' and e.get('category')=='Electrical Circuits'
              and display_parameter(e,'Circuit State')=='Circuit' and display_parameter(e,'System Type')=='Power']
    # Panel/circuit identifiers must be unique; repeated slot numbers in different panels are legitimate.
    ids=[(display_parameter(e,'Panel'),display_parameter(e,'Circuit Number')) for e in circuits]
    if len(ids)!=len(set(ids)):return
    def length(e):
        run=parameter(e,'# of Runs');value=parameter(e,'Length','length')
        return value*run if value is not None and isinstance(run,(int,float)) and run>=1 and run==int(run) else None
    for lid,size in [('FIN-001','12/2'),('FIN-003','10/3'),('FIN-005','8/3')]:
        selected=[e for e in circuits if display_parameter(e,'Cable Size')==size]
        measured(out,lid,selected,length,'SUM(circuit Length FT x # of Runs; Cable Size = '+size+')',
                 'Model circuit-route quantity for '+size+'; MC construction is NOT specified by Residential cable type. Confirm cable specification and routing before purchase', 'MODEL_ROUTE_QUANTITY')
    battery=[e for e in circuits if re.search(r'powerwall|tesla',display_parameter(e,'Load Name') or '',re.I)]
    measured(out,'FIN-013',battery,length,'SUM(Powerwall circuit Length FT x # of Runs)',
             'Model battery circuit route; cable size recorded in circuit evidence; routing/slack and product specification pending','MODEL_ROUTE_QUANTITY')
    measured(out,'FIN-061',[e for e in circuits if display_parameter(e,'Connection Type')=='Breaker'],lambda e:1,
             'COUNT(unique assigned power circuits with Connection Type = Breaker)',
             'One breaker assembly per assigned breaker-connected circuit, not one per pole; spare/SPD rows excluded. Confirm panel schedule and included breakers','DERIVED_ALLOWANCE')
    for lid in ('FIN-001','FIN-003','FIN-005','FIN-013','FIN-061'):
        if lid in out:
            keys=set(out[lid]['references'])
            out[lid]['circuitDetails']=[dict(key=e['key'],panel=display_parameter(e,'Panel'),circuit=display_parameter(e,'Circuit Number'),load=display_parameter(e,'Load Name'),cableSize=display_parameter(e,'Cable Size'),cableType=display_parameter(e,'Cable Type'),lengthFt=parameter(e,'Length','length'),runs=parameter(e,'# of Runs'),poles=parameter(e,'Number of Poles'),rating=display_parameter(e,'Rating')) for e in circuits if e['key'] in keys]
