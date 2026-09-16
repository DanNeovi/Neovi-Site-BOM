"""Versioned search criteria and required measurements for every catalog item."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Search expressions discover evidence; they NEVER authorize an automatic takeoff.
# Numeric takeoffs require the stricter evaluated selectors in map-project-takeoffs.py.
DATA = r'''
FND-001|mud.?mat|Count mat layout locations; mat dimensions and access layout required.
FND-002,FND-003,FND-004,FND-005|site.?suppl|Placeholder: replace with an exact purchasable item before mapping.
FND-006|helical,pile|Count identified helical pile instances; distinguish foundations from annotations.
FND-007|pile,extension|Sum extension segments per pile; installed depth and segment lengths required.
FND-008|pile,cap,saddle|Count pile-specific caps; beam saddles are not automatically pile caps.
FND-009|pile,pin|Count pin joints x pins per joint; connection specification required.
FND-010|pile,bracket,saddle|Count pile-specific brackets; establish pile-to-bracket association.
FND-011|helical,pile|Days = ceil(piles / installation rate); schedule and production rate required.
FND-012|hollow,hss|Count foundation-level hollow structural beams in authoritative structural source.
FND-014,FND-015|bolt,nut|Identify bedframe bolt sets; bolt objects may represent patterns, not single bolts.
FND-016|thread,rod|Sum rod cut lengths; diameter and bedframe connection association required.
FND-017|spacer,gap|Count specified spacers at actual gaps; product definition and gap survey required.
FND-018|shim|Sum shims per bearing location; shim thickness schedule required.
FND-019|isolation,plastic|Sum isolated contact areas; material and coverage scope required.
PAN-001|lifting|Confirmed standard: 1 complete four-point lifting set per project; not 4 separate straps.
PAN-002|plate|Count exact flat 4x3 plate types; exclude bent plates and unspecified generic plates.
PAN-003,PAN-004,PAN-005|bolt,rod,saddle|Count floor-to-HSS joints; identify rod/washer/nut assembly and avoid counting bolt patterns as joints.
PAN-006|floorclip,fastener|Sum floor connection fasteners; leg fastener types must identify these screws.
PAN-007|floor,foam|Foam CUFT = SUM(joint length FT x gap width IN x depth IN / 144); joint gaps required.
PAN-008|lifting,hook|Confirmed standard: 2 two-point lifts with custom hooks per project.
PAN-009|wall,clip,fastener|Count eligible wall joints x 4; classify joint details and screw type first.
PAN-010|wood,metal,screw|Sum wood-to-metal joints x specified screws per joint; connection association required.
PAN-011|angle,clip,nut|Count wall-angle joints x nuts per joint; distinguish screws-only angles.
PAN-012|brace,bracing|Count temporary 2x4 braces from site bracing layout; permanent framing is excluded.
PAN-013|holdown,hold.down|Count Simpson hold-downs x one complete washer/nut assembly per catalog.
PAN-014|plate,wall|Count explicitly wall-to-wall plate details; floor plates cannot be reused as this takeoff.
PAN-015|wall,corner,foam|Foam CUFT = SUM(corner height FT x gap width IN x depth IN / 144); gap geometry required.
PAN-016|truss,fastener|Sum screws from truss connection schedule; members and datum nodes are not screws.
PAN-017|truss,angle,clip|Count identified truss angles; distinguish wall/floor clips from truss connections.
PAN-018|truss,stitch|Count named truss stitch pieces; distinguish web members, caps and connectors.
PAN-019|purlin|Sum purlin cut lengths in FT; exclude truss chords and generic framing.
PAN-020|roof,slope|Sum actual slope build-up areas; roof finish layers are not automatically slope material.
PAN-021|roof,purlin,screw|Sum roof panel-to-purlin fasteners from attachment details; spacing/type required.
PAN-022|roof,rivet|Count rivets at specified roof details; spacing and lap locations required.
PAN-023|roof,joint,butyl|Sum taped seam lengths x tape runs per seam; seam topology and tape scope required.
PAN-024|roller|Catalog allowance 1 roller; confirm installation method and crew equipment.
FIN-001|12/2,12-2,mc.cable|Sum routed 12/2 MC cable lengths; circuit length alone does not establish cable type.
FIN-002|mc,fitting|Count specified 3/8 MC terminations; ends and fitting sizes required.
FIN-003|10/3,10-3,mc.cable|Sum routed 10/3 MC cable lengths; gauge and conductor count required.
FIN-004|fitting|Count 1/2 electrical fittings by type; generic pipe fittings are excluded.
FIN-005|8/3,8-3,mc.cable|Sum routed 8/3 MC cable lengths; gauge and conductor count required.
FIN-006|fitting|Count 3/4 electrical fittings by type; termination details required.
FIN-007|breaker.panel|Count main breaker panel assemblies, excluding smart-home boxes.
FIN-008|fire,bell,cable|Sum fire-bell circuit routes for specified 12/2 MC cable.
FIN-009|feed,panel,circuit|Feeder route length x conductor runs; route and conductor specification required.
FIN-010|conduit,feed|Sum feeder conduit routes; distinguish conduit from individual conductor length.
FIN-011|feed,fitting|Count feeder fittings at bends/terminations; sizes and routed system required.
FIN-012|meter,shutoff|Count meter/shutoff combo panels; excludes water meter equipment.
FIN-013|tesla,powerwall|Sum battery wire routes; equipment count does not establish wire length.
FIN-014|conduit|Sum conduit lengths by size/system; exclude feeder and solar runs counted separately.
FIN-015|pex,fire,pipe|Sum fire PEX routes; pipe material and fire-system identity required.
FIN-016|pex,fire,fitting|Count fire PEX fittings by system and type.
FIN-017|pex,ring|Count crimped fire-system ends x rings per end; joint method required.
FIN-018|sprinkler|Count actual sprinkler heads; exclude ceiling symbols and cutouts.
FIN-019,FIN-020|riser|Count fire riser assemblies; define component boundary to avoid duplicate purchase.
FIN-021|fire.alarm,smoke|Count specified fire alarm assemblies; smoke detector count is not a sprinkler alarm takeoff.
FIN-022|bell|Count fire bells; distinguish detectors and control panels.
FIN-023|hot,pex,pipe|Sum hot-water PEX lengths with material and hot-water system identity.
FIN-024|hot,pex,fitting|Count hot-water PEX fittings by system, size and type.
FIN-025|hot,pex,ring|Count hot-water crimped ends; joint method and port counts required.
FIN-026|recirc,pump|Count recirculation pumps; exclude unrelated pumps.
FIN-027|check.valve,one.way|Count check valves from identified hot-water system.
FIN-028|water.heater|Count water heaters, not fixtures named as heater cutouts.
FIN-029|water.heater,flex|Count flex-connected heater ports; selected connection method required.
FIN-030|water.heater,pan|Count heaters requiring separate drain pans; installation detail required.
FIN-031|water.heater,drain|Sum heater drain routes; heater count cannot determine run length.
FIN-032|water.heater,valve|Count heater isolation points by piping detail; number of valves required.
FIN-033|hot,valve|Count hot-water push-on valves; connection method and fixture ports required.
FIN-034|cold,pex,pipe|Sum cold-water PEX lengths with system/material identity.
FIN-035|cold,pex,fitting|Count cold-water fittings by system, size and type.
FIN-036|cold,pex,ring|Count cold-water crimped ends; joint method required.
FIN-037|water,pipe|Sum house main water routes; separate from branch and underground runs.
FIN-038|water,pipe|Sum underground main route; underground scope and route elevations required.
FIN-039|backflow|Count backflow devices from identified water service.
FIN-040|water.meter|Count water meters; electrical meter combo is excluded.
FIN-041|meter.box,water.meter|Count separate water-meter boxes; enclosure/product boundary required.
FIN-042|cold,valve|Count cold-water push-on valves; connection specification required.
FIN-043|test,cap,sewer|Count temporary sewer test caps from test-zone plan.
FIN-044|toilet,elbow|Count actual toilet 90 elbows; wall-hung toilet fixtures do not establish elbow geometry.
FIN-045|toilet,trim|Ambiguous catalog wording: define toilet bottoms/trim product before mapping.
FIN-046|toilet|Count actual toilets x one complete hardware assembly per catalog; exclude plumbing cutouts.
FIN-047|coupling,sink,toilet|Count 3-inch rubber joints by actual pipe connection size/material.
FIN-048|coupling,laundry|Count 2-inch rubber joints by actual pipe connection size/material.
FIN-049|test,balloon,sewer|Count reusable sewer test balloons from test-zone plan.
FIN-050|vent,pipe|Sum 2-inch PVC vent routes; verify diameter, PVC material and vent system.
FIN-051|vent,fitting|Count 2-inch PVC vent fittings; distinguish waste and vent fittings.
FIN-052|mini.split|Count indoor units x one mounting-hardware assembly per catalog.
FIN-053|condensate,drain|Sum actual condensate drain routes, including vertical offsets.
FIN-054|branch.box|Count HVAC branch boxes; electrical junction boxes are excluded.
FIN-055|refrigerant,line.set|Sum specified refrigerant tube runs; distinguish pair length from individual tube length.
FIN-056|branch.box,cable|Sum outdoor-to-branch-box power routes with conductor specification.
FIN-057|breaker.panel|One cover per breaker panel is a derived assembly rule; verify covers are not included.
FIN-058|outlet|One cover per ordinary indoor box; stacked locations count twice; exclude high-amp/exterior.
FIN-059|outlet|One outlet-and-cover assembly per explicitly 30/50 AMP location; keep separate from regular covers.
FIN-060|outlet|One weatherproof cover per regular exterior outlet; exclude high-amp assemblies already covered.
FIN-061|circuit,breaker|Count scheduled breakers by poles/type; circuits do not automatically equal individual breakers.
FIN-062|ironridge,rail|Sum specified solar rails; panel count alone cannot establish rail layout.
FIN-063|ironridge,clip|Count end/mid clamps from racking layout and exact product.
FIN-064|solar.panel|Count solar panel instances; exclude roof surfaces and generic solar accessories.
FIN-065|solar,connector|Count string connectors from wiring topology; module count is insufficient.
FIN-066|solar,conduit|Sum routed solar conduit runs; keep separate from other conduit.
FIN-067|solar,penetration|Count solar roof penetrations with waterproofing assembly scope.
FIN-068|junction,solar|Count roof junction boxes belonging to solar system.
FIN-069|sprinkler|Cover compatibility unresolved for recessed versus concealed heads; head count alone is insufficient.
FIN-070|hot,flex,sink|Count hot flex-connected ports; fixture assembly internals and hose inclusion required.
FIN-071|hot,escutcheon|Count hot-water wall penetrations requiring separate escutcheons.
FIN-072|cold,flex,sink|Count cold flex-connected ports; distinguish hard-piped ports.
FIN-073|cold,escutcheon|Count cold-water penetrations requiring separate escutcheons.
FIN-074|faucet,tap|Count actual sink faucets; sink bowls may contain factory faucet assemblies.
FIN-075|slip,adapter|Count 1-1/2-inch PVC-to-slip transitions; pipe sizes and joints required.
FIN-076|trap,sink|Count actual slip-joint traps; fixture counts do not establish trap type.
FIN-077|slip,bend|Count slip-joint bends from drainage routing.
FIN-078|cleanout|Count cleanouts requiring separate covers.
FIN-079|sink,drain|Count bowl drains excluding factory-included strainers; bowl count and supply scope required.
FIN-080|slip,adapter|Count remaining slip adapters excluding FIN-075 transitions.
FIN-081|vent,cap|Count vent terminal caps; open plumbing vents may not use caps.
FIN-082|door|Count doors hosted by exterior-function walls; exclude garage vehicle doors. One sill pan per opening.
FIN-083|door|SUM(door count by rough-opening size x (2 x height + width)); exterior host walls, head and two jambs, sill pan separate.
FIN-084|door,screw|Sum frame attachment positions from door installation schedule.
FIN-085|door,foam|SUM(opening joint length x gap width x depth); gap width/depth required.
FIN-086|interior.door|Placeholder: define exact interior-door materials before mapping.
FIN-087|window|SUM(2 x (rough width + rough height) x sides); user rule interior wall = 2 sides, exterior wall = 1; exclude skylights.
FIN-088|window,screw|Sum attachment positions per window schedule; spacing and edge conditions required.
FIN-089|window,sealant|Sealant FL OZ = joint length FT x bead area SQIN x 12 / 1.8046875; bead dimensions required.
FIN-090|window,foam|SUM(perimeter FT x gap width IN x depth IN / 144); gap dimensions required.
FIN-091|vanity,cabinet|Count complete vanity cabinets; countertops and sink modules are not equivalent.
FIN-092|vanity,clip|Count vanity attachment points x clips per point; attachment design required.
FIN-093|island|Count complete kitchen islands; grouping of base cabinets required.
FIN-094|closet|Placeholder: define exact closet materials before mapping.
FIN-095|smart,wire|Sum routed smart-home cable lengths by cable specification.
FIN-096|low.voltage,wire|Sum low-voltage power runs, separate from smart-home signal wire.
FIN-097|routing,conduit|Sum dedicated wire-routing lengths; product and overlap scope required.
FIN-098|connector,smart|Count low-voltage terminations by connector type.
FIN-099|ceiling,garage|Sum gypsum ceiling area spatially matched to GARAGE room; exclude stretch ceiling.
FIN-100|garage.door|Placeholder: define garage-door installation materials before mapping.
FIN-101|sand,level|Area x fill depth x bulk density; survey depth and material density required.
FIN-102|self.level,struco|Area x specified thickness / product coverage x bag weight; product yield required.
FIN-103|floor,screw|Count diagnosed floor-creak repair points x screws per repair.
FIN-104|rubber,underlay|Sum actual rubber-underlayment layer area; finish area alone does not prove underlayment.
FIN-105|wood.floor,floorboard|Sum finished floor top-face area; imported solids require validated area, not total surface area.
FIN-106|simpson,angle,clip|Count Simpson angle clips in truss finish scope; generic clip names are insufficient.
FIN-107|cement.board,concrete.board|Sum board area in truss finish scope; floor/deck cement board is excluded.
FIN-108|truss,screw|Sum finish attachment points from board fastening pattern.
FIN-109|truss,foam|Sum truss-area void volumes; joint geometry and foam coverage required.
FIN-110|roof,trim|Sum identified roof edge trim runs with profile/lap schedule.
FIN-111|gutter,fascia,rivet|Count rivets from trim joint details and fastening spacing.
FIN-112|s.5,clamp|Count S-5 clamps from attachment plan; roof panel count is insufficient.
FIN-113|gutter,fascia,clip|Count trim angles at actual attachment locations.
FIN-114|gutter,fascia,screw|Sum gutter/fascia screw positions from attachment spacing.
FIN-115|gutter|Sum instance Length for gutter elements in FT.
FIN-116|fascia|Sum fascia profile run lengths; generic roof perimeter may include non-fascia edges.
FIN-117|soffit,clip|Count soffit attachment positions x clips per position.
FIN-118|soffit|Sum soffit panel coverage area; exclude roofs and interior ceilings.
FIN-119|stretch,strech,ceiling|Sum stretch-ceiling attachment boundary runs; ceiling area does not give perimeter/profile intersections.
FIN-120|led.profile|Sum measured Light Strip Length for modeled LED profiles; exclude symbolic visibility length.
FIN-121|downlight|One ceiling circle per modeled recessed downlight; verify ceiling installation scope.
FIN-122|sprinkler|One ceiling circle per sprinkler head; verify ceiling installation scope.
FIN-123|glue|Count glued rings x adhesive usage per ring; product consumption required.
FIN-124|heat.gun|Catalog allowance 1 heat gun; crew equipment applicability required.
FIN-125|propane|Burn rate LB/hour x operating hours; equipment and work duration required.
'''

def build():
    entries = {}
    for record in DATA.strip().splitlines():
        ids, search, requirement = record.split('|')
        for line_id in ids.split(','):
            if line_id in entries: raise ValueError(f'Duplicate {line_id}')
            entries[line_id] = {'search': search.split(','), 'requirement': requirement}
    catalog = json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())
    additions=json.loads((ROOT/'config/additions-2026-09-15.json').read_text())
    for item in additions:
        words=re.findall(r'[A-Za-z]{3,}',item['description'])
        entries[item['lineId']]={'search':['.?'.join(words[:3]).lower()],
            'requirement':f"Count or measure {item['description']} in {item['unit']}; confirm exact product, pack size and project requirement. "+item['notes']}
    structural=['Structural Foundations','Structural Framing','Structural Columns','Structural Connections','Bolts','Generic Models','Assemblies']
    plumbing=['Plumbing Fixtures','Plumbing Equipment','Pipes','Pipe Fittings','Generic Models']
    electrical=['Electrical Fixtures','Electrical Equipment','Electrical Circuits','Conduits','Conduit Fittings','Cable Trays','Generic Models']
    for line in catalog:
        lid=line['lineId']; number=int(lid.split('-')[1])
        if lid not in entries:
            entries[lid]={'search':[re.escape(word.lower()) for word in re.findall(r'[A-Za-z]{4,}',line['description'])], 'requirement':line['itemNotes']}
        if line.get('takeoffFormula') or lid in ('FND-009','FND-011','FND-014','FND-015','FND-017','FND-018','FND-019','PAN-011'):
            entries[lid]['requirement']=(line.get('takeoffFormula','')+'; '+line['itemNotes']).strip('; ')
        searches={
            'FND-019':['vapor.?barrier','vapour.?barrier','crawl.?space','moisture.?barrier'],
            'FND-021':['total.?station','survey'],
            'FND-024':['milwaukee','batter'], 'FND-027':['milwaukee','charger'],
            'FND-041':['lifting.?strap','lifting.?sling'],
            'FND-043':['digger','excavator'], 'FND-045':['pipe.?level'],
            'FND-047':['annular','magnetic.?drill.*bit','mag.?drill.*bit'],
            'PAN-007':['froth','foam','floor.*joint'],
            'PAN-010':['temporary.?brac','bracing.*screw','4.?inch.*screw'],
            'PAN-011':['4.?x.?4.*angle','wall.?angle','threaded.?rod'],
            'PAN-038':['threaded.*clamp','wall.*clamp'],
        }
        if lid in searches:entries[lid]['search']=searches[lid]
        if lid.startswith('FND'): categories=structural
        elif lid.startswith('PAN'):
            categories=structural+(['Roofs'] if number>=19 else ['Walls','Floors'])
        elif number<=14 or 57<=number<=68 or 95<=number<=98: categories=electrical
        elif 15<=number<=22 or number==69: categories=plumbing+['Sprinklers']
        elif 23<=number<=51 or 70<=number<=81: categories=plumbing
        elif 52<=number<=56: categories=['Mechanical Equipment','Ducts','Duct Accessories','Pipes','Pipe Fittings','Electrical Equipment','Generic Models']
        elif 82<=number<=90 or number==100: categories=['Doors','Windows','Generic Models']
        elif 91<=number<=94: categories=['Casework','Furniture','Generic Models','Plumbing Fixtures']
        elif number==99: categories=['Ceilings','Rooms']
        elif 101<=number<=105: categories=['Floors','Generic Models']
        elif 106<=number<=109: categories=structural+['Floors','Walls','Ceilings']
        elif 110<=number<=118: categories=['Roofs','Gutters','Fascias','Soffits','Generic Models','Structural Connections']
        else: categories=['Ceilings','Lighting Fixtures','Sprinklers','Generic Models']
        addition=next((a for a in additions if a['lineId']==lid),None)
        if addition:
            categories={
                'Sitework':['Generic Models','Specialty Equipment'],
                'Structural':structural+['Specialty Equipment'],
                'Building Envelope':['Roofs','Gutters','Fascias','Soffits','Generic Models','Specialty Equipment'],
                'Electrical':electrical+['Specialty Equipment'],
                'Fire Protection':plumbing+['Sprinklers','Specialty Equipment'],
                'Plumbing':plumbing+['Specialty Equipment'],
                'Mechanical':['Mechanical Equipment','Duct Accessories','Generic Models','Specialty Equipment'],
                'Doors & Windows':['Doors','Windows','Generic Models','Specialty Equipment'],
                'Interior Finishes':['Casework','Furniture','Floors','Walls','Ceilings','Generic Models','Specialty Equipment'],
            }[addition['category']]
        entries[lid]['categories']=categories
    entries={line['lineId']:entries[line['lineId']] for line in catalog}
    assert all(r['search'] and r['requirement'] for r in entries.values()), 'Every catalog line must have an explicit search and takeoff requirement'
    (ROOT/'config/model-item-mapping-register.json').write_text(json.dumps(entries,indent=2))
    print(f'Mapping register: {len(entries)} explicit item definitions')

if __name__ == '__main__': build()
