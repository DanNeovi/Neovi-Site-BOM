"""Independently check every Monroe catalog quantity and describe evidence limits."""
import importlib.util
import json
import math
import re
import sys
from collections import Counter
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from project_model_mapper import map_model

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'outputs/NeoviBOM/_Internal/Model-Data'
DEST = ROOT / 'outputs/NeoviBOM/05-Monroe'

spec = importlib.util.spec_from_file_location('monroe_builder', ROOT / 'scripts/build-monroe-estimates.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def dec(value):
    return Decimal(str(value))


def ceil_increment(value, increment):
    step = dec(increment)
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


def template_lines(value):
    if isinstance(value, dict):
        if re.fullmatch(r'(FND|PAN|FIN)-\d+', str(value.get('id', ''))):
            yield value
        for child in value.values():
            yield from template_lines(child)
    elif isinstance(value, list):
        for child in value:
            yield from template_lines(child)


REVIEW = {
    'FND-006': '50 linked pile-cap saddles are a position proxy; the independent footprint benchmark is 18. Confirm the engineered pile schedule.',
    'FND-007': 'One extension at 25% of assumed pile positions is a depth allowance; no geotechnical pile length is modeled.',
    'FND-010': 'Bracket quantity follows the 50 saddle-position proxy; confirm pile-to-bracket detail.',
    'FND-014': 'Two nuts per assumed pile follow the catalog rule; verify the bearing connection.',
    'FND-015': 'Two bolts per assumed pile follow the catalog rule; verify the bearing connection.',
    'FND-058': 'Twenty washers per assumed pile is the current interpretation; the catalog explicitly leaves 10 versus 20 unresolved.',
    'PAN-002': '236 plates are selected in the model, but the catalog base kit becomes 250; its 100-versus-250 minimum note is unresolved.',
    'PAN-006': 'The 8-screw/plate allowance does not assign 3,858 typed floor-clip fastener positions because fastener type and site/factory scope are missing.',
    'PAN-016': 'Eight screws per linked truss label means two bearings times four screws. The engineer must confirm the connection schedule.',
    'PAN-036': 'Ten percent of the exterior wall net-area proxy is an assumed site CB scope. One wall lacks typed Area and uses gross area; model wall layers may already contain board. Reconcile FIN-107 and factory installation.',
    'PAN-017': 'Two angles per linked truss label are assumed; no approved connection schedule is modeled.',
    'PAN-018': 'Two stitch pieces per linked truss label are assumed; no approved connection schedule is modeled.',
    'PAN-019': 'Purlin length uses roof sheathing area divided by assumed 2-FT spacing; actual layout and waste are unknown.',
    'PAN-020': 'Catalog section and input key both specify roof slope area. Roof sheathing is a full-coverage proxy; verify actual slope coverage and site/factory scope.',
    'PAN-021': 'Roof-panel screws use 1.5 per SQFT of roof sheathing; verify panel span and fastening pattern.',
    'PAN-022': 'Roof-panel rivets use 0.3 per SQFT of roof sheathing; seam details are not modeled.',
    'PAN-023': 'Butyl tape uses one FT per three roof SQFT; seam layout and roll allowance remain unknown.',
    'PAN-040': 'Truss-stage fasteners use 10% roof-board coverage and ten screws per covered SQFT; verify board scope and distinguish roof-panel screws.',
    'FIN-107': 'Two-foot-high concrete-board band uses exterior stud-wall length; reconcile PAN-036 wall CB and actual finish detail.',
    'FIN-108': 'Eight screws per SQFT are tied to FIN-107 assumed board coverage; confirm fastening schedule and whether this is separate from PAN-040 roof-board screws.',
    'FIN-019': 'Fire riser may be the same purchase as the fire-riser assembly (FIN-020).',
    'FIN-020': 'Fire-riser assembly may include the separately listed fire riser (FIN-019).',
    'FIN-037': 'House-main and underground-main 50-FT allowances may refer to connected or overlapping route segments.',
    'FIN-038': 'Underground-main and house-main 50-FT allowances may refer to connected or overlapping route segments.',
    'FIN-046': 'Four toilet fixtures are modeled, but five separate toilet rough-in cutouts need location reconciliation.',
    'FIN-054': 'Zero applies only to the modeled all-in-one AC scenario; split-system selection changes this row.',
    'FIN-055': 'Zero applies only to the modeled all-in-one AC scenario; split-system selection changes this row.',
    'FIN-056': 'Zero applies only to the modeled all-in-one AC scenario; split-system selection changes this row.',
    'FIN-058': '130 ordinary/quad outlet elements yield 131 cover equivalents because one stacked element has two boxes.',
    'FIN-061': '57 breakers are a grouped-load budget, not a circuit schedule; check panel capacity and included breakers.',
    'FIN-095': 'Twenty FT per smart control is a route allowance; FIN-095 through FIN-097 may overlap unless products are distinguished.',
    'FIN-096': 'Twenty FT per smart control is a route allowance; FIN-095 through FIN-097 may overlap unless products are distinguished.',
    'FIN-097': 'Twenty FT per smart control is a route allowance; FIN-095 through FIN-097 may overlap unless products are distinguished.',
    'FIN-098': 'Two connectors per modeled smart control are assumed; verify the actual connector product.',
    'FIN-101': 'Sand/leveling material and self-leveling compound may be alternate methods; choose the floor assembly.',
    'FIN-102': 'Self-leveling compound and sand/leveling material may be alternate methods; choose the floor assembly.',
    'FIN-104': 'Dry-room area is a finish proxy; confirm floor schedule, waste and whether wet rooms use other underlayment.',
    'FIN-105': 'Dry-room area is a finish proxy; confirm floor schedule, waste and whether wet rooms use another finish.',
    'FIN-119': 'Summed ceiling perimeters may include shared boundaries or LED replacement sections.',
    'FIN-120': '39 spatially overlapping LED profile representations were excluded; confirm any remaining parallel runs.',
    'FIN-159': 'Only 20 operable windows are counted; four fixed windows are excluded. Confirm screen inclusion in the window package.',
    'FIN-160': 'Only 20 operable windows are counted; four fixed windows are excluded. Confirm handle inclusion in the window package.',
}

for lid in ('FIN-015', 'FIN-016', 'FIN-017', 'FIN-018', 'FIN-021', 'FIN-022', 'FIN-069', 'FIN-122'):
    REVIEW[lid] = 'No sprinkler-head instances are modeled; fire-protection counts and routes await the fire system design.'
for lid in ('FIN-110', 'FIN-111', 'FIN-113', 'FIN-114', 'FIN-116', 'FIN-117', 'FIN-118'):
    REVIEW[lid] = 'Roof-edge/fascia/soffit rate uses 400.64 FT exterior-wall proxy; only 237.01 FT of gutter is measured.'


def main():
    report = json.loads((DEST / 'Monroe-Item-Formulas.json').read_text(encoding='utf-8'))
    rows = json.loads((DATA / 'monroe-takeoff-elements.json').read_text())
    manifest = json.loads((DATA / 'monroe-scan-manifest.json').read_text())
    catalog = json.loads((DATA / 'catalog-lines.json').read_text())
    template = list(template_lines(json.loads((ROOT / 'config/site-bom.template.json').read_text())))
    confirmed = json.loads((ROOT / 'config/confirmed-site-standards.json').read_text())
    rules = builder.load_rules()
    mapped, openings = map_model(rows)
    drivers = builder.monroe_drivers(rows, mapped, openings, manifest['storyAreas'])
    source = Path(manifest['source'])
    stat = source.stat()
    if (stat.st_size, stat.st_mtime_ns) != (manifest['sourceBytes'], manifest['sourceMtimeNs']):
        raise ValueError('Monroe model changed; rerun scan-monroe-model.py')
    if (report['sourceBytes'], report['sourceMtimeNs']) != (stat.st_size, stat.st_mtime_ns):
        raise ValueError('Monroe quantity report does not match source model')
    template_by_id = {item['id']: item for item in template}
    catalog_by_id = {item['lineId']: item for item in catalog}
    report_by_id = {item['lineId']: item for item in report['items']}
    if not (len(template_by_id) == len(catalog_by_id) == len(report_by_id) and
            set(template_by_id) == set(catalog_by_id) == set(report_by_id)):
        raise ValueError('Template, catalog and Monroe report do not contain the same unique lines')
    element_keys = {element['key'] for element in rows}
    for name, value in drivers.items():
        actual = report['drivers'][name]
        if not math.isclose(value['value'], actual['value'], rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError('Stale Monroe driver: ' + name)
        if set(value['references']) != set(actual['references']):
            raise ValueError('Changed Monroe driver references: ' + name)
    audits = []
    for line in catalog:
        lid = line['lineId']
        item = report_by_id[lid]
        template_item = template_by_id[lid]
        if item['description'] != line['description'] or item['unit'] != line['unit'] or item['catalogId'] != line['catalogId']:
            raise ValueError('Catalog mismatch: ' + lid)
        if template_item['description'] != line['description'] or template_item['catalogId'] != line['catalogId']:
            raise ValueError('Template/catalog mismatch: ' + lid)
        if (item['quantityIncrement'], item['sparePercent'], item['minimumKitQty']) != (
                line['quantityIncrement'], line['sparePercent'], line['minimumKitQty']):
            raise ValueError('Quantity rule mismatch: ' + lid)
        if not item['formula'] or not item['assumption'] or not item['references']:
            raise ValueError('Missing per-item formula, assumption or evidence: ' + lid)
        missing_refs = [ref for ref in item['references'] if ref.startswith('host') and ref not in element_keys]
        if missing_refs:
            raise ValueError(f'{lid} has references absent from the model cache: {missing_refs[:3]}')
        if lid in mapped:
            evidence = mapped[lid]
            if not math.isclose(item['quantity'], evidence['value'], rel_tol=1e-9, abs_tol=1e-8) or set(item['references']) != set(evidence['references']):
                raise ValueError('Model quantity/reference mismatch: ' + lid)
            kind = 'MODELED_OR_DERIVED'
            driver_names = []
            check = 'Model selector and source references reproduced'
        elif lid in confirmed:
            if item['quantity'] != line['fixedQty'] or item['basis'] != 'CONFIRMED_STANDARD':
                raise ValueError('Confirmed standard mismatch: ' + lid)
            kind = 'CONFIRMED_STANDARD'
            driver_names = []
            check = 'Saved fixed standard matches catalog'
        elif line['sourceMode'] == 'FIXED':
            if item['quantity'] != line['fixedQty'] or item['basis'] != 'CATALOG_FIXED_ALLOWANCE':
                raise ValueError('Catalog fixed allowance mismatch: ' + lid)
            kind = 'CATALOG_ALLOWANCE'
            driver_names = []
            check = 'Catalog fixed quantity reproduced; project scope unconfirmed'
        else:
            rule = rules[lid]
            driver_names = [term['driver'] for term in rule['terms']]
            raw = sum((dec(drivers[term['driver']]['value']) * dec(term['rate'])
                       for term in rule['terms']), Decimal(0))
            expected = ceil_increment(raw, line['quantityIncrement'])
            if dec(item['quantity']) != expected:
                raise ValueError(f'Planning arithmetic mismatch for {lid}: {item["quantity"]} vs {expected}')
            if item['basis'] == 'PLANNING_PLACEHOLDER':
                kind = 'UNDEFINED_PLACEHOLDER'
                check = 'Zero placeholder reproduced; item must be defined'
            elif item['basis'] == 'PLANNING_CONDITIONAL_ZERO':
                kind = 'SYSTEM_CONDITIONAL'
                check = 'Conditional zero reproduced; alternate system requires new quantity'
            else:
                kind = ('PROJECT_ASSUMPTION' if driver_names == ['project'] else
                        'MIXED_MODEL_AND_PROJECT_ASSUMPTION' if 'project' in driver_names else
                        'MODEL_SCALED_ASSUMPTION')
                check = 'Rate arithmetic reproduced; coverage/specification unverified'
        spare = ceil_increment(dec(item['quantity']) * dec(line['sparePercent']), line['quantityIncrement'])
        kit = ceil_increment(max(dec(item['quantity']) + spare, dec(line['minimumKitQty'])), line['quantityIncrement'])
        if dec(item['spareQuantity']) != spare or dec(item['baseKitQuantity']) != kit:
            raise ValueError('Spare/base-kit arithmetic mismatch: ' + lid)
        if 'storyAllocation' in item:
            if not math.isclose(sum(part['quantity'] for part in item['storyAllocation'].values()),
                                item['quantity'], abs_tol=1e-8):
                raise ValueError('Story allocation mismatch: ' + lid)
        fastener = (item['unit'] == 'EA' and item['categoryPath'][0] != 'Tools' and
                    re.search(r'\b(screws?|nails?|rivets?)\b', item['description'], re.I))
        metrics = item.get('averageMetrics')
        if not metrics or bool(fastener) != (lid in builder.FASTENER_BENCHMARKS):
            raise ValueError('Item average or fastener benchmark coverage mismatch: ' + lid)
        if metrics['quantityExcludesSpares'] != item['quantity']:
            raise ValueError('Item average quantity mismatch: ' + lid)
        if item['basis'] in ('PLANNING_PLACEHOLDER', 'PLANNING_CONDITIONAL_ZERO'):
            if metrics['averagePerLivableSqft'] is not None:
                raise ValueError('Undefined/conditional zero published as usage rate: ' + lid)
        else:
            primary = metrics['primaryDriver']
            area = metrics['areaDriver']
            if not math.isclose(metrics['averagePerLivableSqft'],
                                item['quantity'] / drivers['floorArea']['value'], rel_tol=1e-12):
                raise ValueError('Livable-area average arithmetic mismatch: ' + lid)
            if primary and (metrics['primaryDriverValue'] != drivers[primary]['value'] or
                            not math.isclose(metrics['averagePerPrimaryDriver'],
                                             item['quantity'] / drivers[primary]['value'], rel_tol=1e-12)):
                raise ValueError('Primary-driver average arithmetic mismatch: ' + lid)
            if area and (metrics['areaDriverValue'] != drivers[area]['value'] or
                         not math.isclose(metrics['averagePerApplicableSqft'],
                                          item['quantity'] / drivers[area]['value'], rel_tol=1e-12)):
                raise ValueError('Applicable-area average arithmetic mismatch: ' + lid)
        audits.append({
            'lineId': lid, 'description': item['description'], 'unit': item['unit'],
            'quantity': item['quantity'], 'spareQuantity': item['spareQuantity'],
            'baseKitQuantity': item['baseKitQuantity'], 'basis': item['basis'],
            'auditKind': kind, 'arithmeticCheck': check, 'drivers': driver_names,
            'modelReferenceCount': sum(ref in element_keys for ref in item['references']),
            'formula': item['formula'], 'assumption': item['assumption'],
            'averageMetrics': metrics,
            'reviewNote': REVIEW.get(lid, ''),
        })
    counts = dict(Counter(row['auditKind'] for row in audits))
    d = report['drivers']
    if (d['outlets']['value'] != 149 or d['operableWindows']['value'] != 20 or
            d['fixedWindows']['value'] != 4 or d['trussCount']['value'] != 50 or
            d['floorClipFastenerPositions']['value'] != 3858):
        raise ValueError('Critical source family reconciliation changed')
    findings = [
        {'priority': 1, 'topic': 'Foundation position count',
         'lineIds': ['FND-006', 'FND-007', 'FND-010', 'FND-014', 'FND-015', 'FND-058'],
         'evidence': f"{d['pileProxy']['value']:.0f} linked U saddles drive 50 piles/brackets, 13 extensions and 1,000 washers. "
                     f"The separate one-per-125-SQFT footprint comparison is {d['pileAreaBenchmark']['value']:.0f} positions; "
                     'at that count the same rules yield 18 piles/brackets, 5 extensions and 360 washers.',
         'decision': 'Use the engineered pile and connection schedule to choose the count; neither proxy establishes pile locations.'},
        {'priority': 1, 'topic': 'Board coverage and fastener scope',
         'lineIds': ['PAN-036', 'PAN-040', 'FIN-107', 'FIN-108'],
         'evidence': 'The independent assumptions yield 300 SQFT site wall CB, 2,816 truss-stage board screws, '
                     '802 SQFT truss-finish board and 6,411 finish screws. PAN-040 assumes 10% roof-board '
                     'coverage at 10 screws per covered SQFT, yet no separate truss-stage roof-board material line exists. '
                     'FIN-108 assumes eight screws per SQFT of the FIN-107 band.',
         'decision': 'Mark actual board faces and factory/site responsibilities on the assembly drawings, then assign each screw line to one board scope.'},
        {'priority': 1, 'topic': 'Unmodeled fire-protection layout',
         'lineIds': ['FIN-015', 'FIN-016', 'FIN-017', 'FIN-018', 'FIN-019', 'FIN-020', 'FIN-069', 'FIN-122'],
         'evidence': 'No eligible sprinkler-head instance is modeled; the budget still contains 24 heads, '
                     '418 FT fire PEX and 24 covers/circles. Fire riser and fire-riser assembly are each one item.',
         'decision': 'Replace area-density allowances with the fire design and check whether the assembly includes the riser.'},
        {'priority': 1, 'topic': 'Roof slope coverage',
         'lineIds': ['PAN-020'],
         'evidence': f"The catalog names roof_slope_material_area, while the estimate applies slope material to all "
                     f"{d['roofProxyArea']['value']:,.2f} SQFT of selected roof sheathing (rounded to 2,816 SQFT).",
         'decision': 'Measure the actual roof area needing site slope build-up and confirm whether panels arrive with slope already formed.'},
        {'priority': 1, 'topic': 'Foundation rental and installation motor',
         'lineIds': ['FND-011', 'FND-043', 'FND-060'],
         'evidence': 'The user sets a two-week (14-calendar-day) John Deere rental and one digger motor. '
                     'The separate large digger is cataloged as owned equipment, not a second rental.',
         'decision': 'Confirm rental billing and whether the motor or drive attachment comes with the rented machine or owned digger before adding equipment costs.'},
        {'priority': 2, 'topic': 'Floor connection hardware',
         'lineIds': ['PAN-002', 'PAN-003', 'PAN-004', 'PAN-005', 'PAN-006'],
         'evidence': f"{d['floorPlates']['value']:.0f} selected plates drive 1,888 planning screws, but linked floor clips "
                     f"also expose {d['floorClipFastenerPositions']['value']:,.0f} typed fastener positions of unspecified type. "
                     'The 236-plate takeoff becomes a 250-plate base kit under the current minimum.',
         'decision': 'Match clip positions and plate connections to their installation drawings; resolve the 100-versus-250 plate minimum.'},
        {'priority': 2, 'topic': 'Electrical circuits and routes',
         'lineIds': ['FIN-001', 'FIN-002', 'FIN-061', 'FIN-095', 'FIN-096', 'FIN-097'],
         'evidence': '57 breakers are estimated from grouped device loads without modeled circuits. '
                     'Smart-home wire, low-voltage power wire and routing material each carry 520 FT '
                     'from the same 26 control positions; these may describe different products on a shared route.',
         'decision': 'Use the electrical schedule to size circuits and distinguish cable from containment before adding the three 520-FT lines.'},
        {'priority': 2, 'topic': 'Roof edge versus gutter extent',
         'lineIds': ['FIN-110', 'FIN-111', 'FIN-113', 'FIN-114', 'FIN-115', 'FIN-116', 'FIN-117', 'FIN-118'],
         'evidence': f"Gutters measure {d['gutterLength']['value']:,.2f} FT; fascia/soffit and fastener allowances use "
                     f"{d['exteriorWallLength']['value']:,.2f} FT exterior-wall run, "
                     f"{d['exteriorWallLength']['value'] - d['gutterLength']['value']:,.2f} FT longer.",
         'decision': 'Measure separate roof-edge, fascia and soffit runs; the gutter length need not equal any of them.'},
        {'priority': 2, 'topic': 'One exterior wall has no typed area',
         'lineIds': ['PAN-036'],
         'evidence': 'The net wall-face proxy uses 38 typed exterior wall areas and one 157.50-SQFT gross fallback. '
                     'If that wall had zero net area, the current 300-SQFT, 10%-coverage allowance would be 284 SQFT.',
         'decision': 'Obtain or reconstruct the missing wall opening area before treating the board quantity as measured.'},
        {'priority': 2, 'topic': 'Possible alternate or included products',
         'lineIds': ['FIN-101', 'FIN-102', 'FIN-019', 'FIN-020', 'FIN-158', 'FIN-159', 'FIN-160'],
         'evidence': 'Sand/leveling material and self-leveling compound are 658 LB each; '
                     'riser/assembly are one each; fan covers, window screens and handles may be supplied with equipment.',
         'decision': 'Choose the floor method and check package inclusions before adding these lines together.'},
        {'priority': 2, 'topic': 'Water and fixture route discrepancies',
         'lineIds': ['FIN-037', 'FIN-038', 'FIN-040', 'FIN-046'],
         'evidence': 'House-main and underground-main allowances are 50 FT each without modeled route segments. '
                     'Four toilet fixtures have five rough-in cutouts. The modeled electrical meter is not evidence for a water meter.',
         'decision': 'Trace main-water segments and the fifth cutout on the plumbing/site plan.'},
        {'priority': 3, 'topic': 'Reusable tool inventory',
         'lineIds': ['FND-059', 'FND-021', 'FND-055', 'FND-056', 'FND-057', 'FND-061', 'FIN-183', 'FIN-184'],
         'evidence': 'Total station and laser total station are one each; three magnetic-drill pedestal variants '
                     'and ten orange-handle magnets are budgeted, along with manual/electric suction lifters.',
         'decision': 'Check whether each is a distinct tool, accessory or alternative already owned by the crew.'},
        {'priority': 3, 'topic': 'Undefined catalog products',
         'lineIds': ['FIN-086', 'FIN-094', 'FIN-100', 'FIN-150'],
         'evidence': 'Four finishing rows have explicit zero placeholders because their material or tool has not been defined. Foundation placeholders FND-003 and FND-005 were retired.',
         'decision': 'Specify these items before interpreting zero as no purchase.'},
    ]
    result = {'source': str(source), 'sourceBytes': stat.st_size,
              'elementsScanned': manifest['elementsScanned'], 'catalogRowsAudited': len(audits),
              'auditKinds': counts, 'modelDrivers': d, 'priorityFindings': findings, 'items': audits}
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'Monroe-Value-Audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    markdown = [
        '# Monroe Site BOM | Every-value audit', '',
        f"Source model: `{source}`; {manifest['elementsScanned']:,} elements scanned. "
        f"All **{len(audits)}** catalog rows passed source-reference and quantity-arithmetic checks.", '',
        'A passing arithmetic check means the saved number follows its stated formula. It does not confirm the product, '
        'installation scope, engineered connection design or procurement quantity.', '',
        '## Evidence coverage', '',
        '| Audit kind | Rows | Meaning |', '|---|---:|---|',
    ]
    meanings = {
        'MODELED_OR_DERIVED': 'Selected model instances or measured geometry; derived accessories still need scope review.',
        'CONFIRMED_STANDARD': 'Saved user-confirmed project quantity, independent of the model.',
        'CATALOG_ALLOWANCE': 'Existing fixed catalog quantity, not a measured project takeoff.',
        'MODEL_SCALED_ASSUMPTION': 'Model driver multiplied by an assumed rate or coverage.',
        'MIXED_MODEL_AND_PROJECT_ASSUMPTION': 'Model drivers plus at least one project-only assumption.',
        'PROJECT_ASSUMPTION': 'No model quantity driver; a project-level allowance.',
        'SYSTEM_CONDITIONAL': 'Zero only for the current modeled system scenario.',
        'UNDEFINED_PLACEHOLDER': 'Catalog item has not been defined; zero is not a measured absence.',
    }
    for kind, meaning in meanings.items():
        markdown.append(f"| {kind} | {counts.get(kind, 0)} | {meaning} |")
    markdown += ['', '## Decisions with the largest scope or quantity impact', '',
                 'Priority 1 needs a design or assembly decision before the estimate can be used to order that group. '
                 'Priority 2 needs a schedule, route or package check. Priority 3 is a catalog/inventory cleanup. '
                 'These findings do not change a quantity without supporting evidence.', '',
                 '| Priority | Topic and rows | Model evidence / quantity effect | Required decision |',
                 '|---:|---|---|---|']
    for finding in findings:
        clean = lambda value: value.replace('|', '\\|').replace('\n', ' ')
        markdown.append(f"| {finding['priority']} | {clean(finding['topic'])} "
                        f"({', '.join(finding['lineIds'])}) | {clean(finding['evidence'])} | "
                        f"{clean(finding['decision'])} |")
    markdown += ['', '## Source reconciliations that matter', '',
        f"- Livable area: {d['firstStoryArea']['value']:,.2f} SQFT first story + "
        f"{d['secondStoryArea']['value']:,.2f} SQFT second story = {d['floorArea']['value']:,.2f} SQFT. "
        'First-story overlapping floor meshes and garage overlap are removed before area rates.',
        f"- Stud walls: {d['interiorWallLength']['value']:,.2f} FT interior + "
        f"{d['exteriorWallLength']['value']:,.2f} FT exterior = {d['wallLength']['value']:,.2f} FT total. "
        f"The exterior run includes {d['garageWallLength']['value']:,.2f} FT garage-labeled walls; "
        f"{d['garageRoomPerimeter']['value']:,.2f} FT is the separate GARAGE room perimeter.",
        f"- Board areas: PAN-036 assumes 10% of {d['exteriorWallNetFaceAreaProxy']['value']:,.2f} SQFT "
        'net exterior one-face wall area proxy for site CB (one missing typed wall Area uses gross fallback). '
        'PAN-040 assumes 10% of roof sheathing area and ten screws '
        'per covered SQFT for truss-stage board; FIN-107 uses a separate 2-FT exterior-wall strip and FIN-108 uses eight screws per SQFT of that strip. The board scopes need reconciliation.',
        f"- Outlets: {d['outlets']['value']:,.0f} cover equivalents from modeled ordinary, quad, stacked, exterior and high-amp boxes. "
        'One stacked element contributes two covers. Every eligible outlet family has a cover class.',
        f"- Trusses: {d['trussCount']['value']:,.0f} linked labels x two assumed bearings x four screws = "
        f"{report_by_id['PAN-016']['quantity']:,.0f} truss screws. This is "
        f"{report_by_id['PAN-016']['averageMetrics']['averagePerApplicableSqft']:.6f} screws per "
        f"roof SQFT after dividing by {d['roofProxyArea']['value']:,.2f} SQFT modeled roof sheathing. "
        'Roof-panel screws remain a separate roof-area estimate.',
        f"- Windows: {d['operableWindows']['value']:,.0f} operable and {d['fixedWindows']['value']:,.0f} fixed; "
        'screens and handles use operable windows only.',
        f"- Floor clips: {d['floorClipFastenerPositions']['value']:,.0f} typed fastener positions have no identifiable "
        'screw type or site/factory scope. PAN-006 does not silently absorb them.',
        f"- Toilets: {d['toilets']['value']:,.0f} fixtures versus {d['toiletCutouts']['value']:,.0f} rough-in cutouts; "
        'the extra cutout requires location reconciliation.',
        f"- Gutter: {d['gutterLength']['value']:,.2f} FT measured; "
        f"{d['exteriorLength']['value']:,.2f} FT exterior-wall run is only a fascia/soffit fastener proxy.",
        '- Fire protection: no sprinkler-head instances in the eligible model; sprinkler-related amounts are allowances.',
        '', '## Every catalog value', '',
        'The formula, assumption and quantity per livable SQFT are repeated here so each value can be reviewed without '
        'opening the quantity report. Per-SQFT is a comparison for project-only tools and allowances, not their sizing rule. '
        'Source element keys and the full driver calculation are in the JSON reports.', '',
        '| ID | Item | Quantity | Per livable SQFT | Audit kind | Check | Formula and review |',
        '|---|---|---:|---:|---|---|---|',
    ]
    for row in audits:
        detail = row['formula'] + '; ' + row['assumption']
        if row['reviewNote']:
            detail += ' **Review:** ' + row['reviewNote']
        clean = lambda value: value.replace('|', '\\|').replace('\n', ' ')
        average = (f"{row['averageMetrics']['averagePerLivableSqft']:.6f} {row['unit']}/SQFT"
                   if row['averageMetrics']['averagePerLivableSqft'] is not None else 'N/A')
        markdown.append(f"| {row['lineId']} | {clean(row['description'])} | "
                        f"{row['quantity']:,.6f}".rstrip('0').rstrip('.') +
                        f" {row['unit']} | {average} | {row['auditKind']} | {row['arithmeticCheck']} | {clean(detail)} |")
    (DEST / 'Monroe-Value-Audit.md').write_text('\n'.join(markdown) + '\n', encoding='utf-8')
    print(f"Audited {len(audits)} Monroe values: {counts}")


if __name__ == '__main__':
    main()
