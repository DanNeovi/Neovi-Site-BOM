"""Audit every live Monroe SiteBOM line against model math and drawing leads.

This is a review artifact. A mention or AI extraction is never treated as an
approved quantity, and this script does not write the live Google Sheet.
"""

import argparse
import csv
import hashlib
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path('G:/My Drive/SiteBOM/04-Audits/Monroe-Full-Quantity-Audit')
MODEL_AUDIT = Path('G:/My Drive/SiteBOM/05-Monroe/Monroe-Value-Audit.json')
MODEL_ELEMENTS = Path('G:/My Drive/SiteBOM/_Internal/Model-Data/monroe-takeoff-elements.json')
PILE_SCHEDULE = ROOT / 'config/monroe-helical-pile-schedule.json'
CORE_EXTRACTIONS = Path('G:/My Drive/SiteBOM/04-Audits/Monroe-AI/extractions')
PLAN_PDF = Path.home() / 'Downloads/Neovi_206 Monroe State Set 260325.pdf'
STOP = set('and the for with from into under over per each all one two three four site '
           'model material materials assembly complete set type typical new to of on in at by '
           'ea ft sqft gal pcs piece pieces inch inches foot feet'.split())
DIRECT_PLAN = {'FND-006': 'Structural schedule, PDF page 30 / SE page 3: 48 piles; 9 at 3 1/2 in, 22 at 4 1/2 in, 17 at 2 7/8 in.'}
PILE_ROWS = {'3 1/2 in': 9, '4 1/2 in': 22, '2 7/8 in': 17}
PILE_HEADS = {'GTC03723': 9, 'GTC03796': 22, 'GTC03795': 17}
# Counted visually from both panel schedules on E4.1 (March 2026 plan check).
# Two-pole circuit pairs count as one breaker; SPACE and feed-through lugs do not.
BREAKER_BY_TYPE = {'20A standard': 2, '50A GFCI': 3, '30A GFCI': 3,
                   '20A AFCI': 22, '20A GFCI': 20, '20A DFCI': 8,
                   '80A standard': 1}
HOLD_DOWNS_BY_FAMILY = {'CF_SHD15S': 36, 'CF_SHDU9': 21,
                        'CF_SHD10S': 4, 'CF_SHD10B': 4}
SHORT_ANGLES_BY_SIZE = {'L4X4X1/4, 4 in': 31, 'L6X4X3/8, 5 in': 4,
                        'L4X4X3/8, 4 in': 2}
HIGH_PRIORITY = {
    'SHEET-016': 'Legacy 50 six-inch piles conflict with the three scheduled shaft diameters; do not order from this row.',
    'SHEET-017': 'Legacy 25 four-inch piles conflict with the three scheduled shaft diameters; do not order from this row.',
    'SHEET-018': '75 caps are unsupported. If exactly one cap/head per scheduled pile, plan basis is 48: GTC03723 x9, GTC03796 x22, GTC03795 x17; confirm whether a separate cap is required.',
    'SHEET-019': '200 nuts are user-listed; the current 2-per-pile planning rule yields 96. Count exact nuts per approved pile-head and bedframe connection detail.',
    'SHEET-020': '200 bolts are user-listed; the current 2-per-pile planning rule yields 96. Count exact bolts per approved connection detail and avoid counting shared joints twice.',
    'SHEET-030': 'Six listed 8x6 beams at 8 ft are not equivalent to 29 model-selected foundation HSS members. Reconcile member size and length schedule by beam key before ordering.',
    'FND-007': '12 extensions are a 25% allowance on 48 piles. Use required installed depth minus stock shaft length, by pile ID and actual available extension lengths.',
    'FND-010': '48 brackets use one per pile. Compare cap/head codes and steel details before deciding whether bracket is separate from the scheduled head.',
    'FND-014': '96 nuts use 2 per pile. Count by connection type and approved fastener detail, then multiply by occurrences.',
    'FND-015': '96 bolts use 2 per pile. Count by connection type and approved fastener detail, then multiply by occurrences.',
    'FND-016': '58 FT threaded rod uses 2 FT per 29 HSS beams. Reconcile with 21-inch cuts per evidenced hold-down or L-angle, grouped by diameter.',
    'FND-058': '960 washers use 20 per pile; this is not supported by the pile schedule. Count washers per actual bolted connection.',
    'PAN-002': '236 plate positions are model-selected, but the base kit becomes 250. Separate installation count, stock pack/minimum and spare stock.',
    'PAN-003': '58 floor connecting rods use 2 per 29 HSS beams. Count actual connection locations and rod diameter, with site/factory scope.',
    'PAN-006': '1,888 screws use 8 per 236 plates; 3,858 model fastener positions need type and installation-scope reconciliation.',
    'PAN-013': '65 modeled hold-downs are a type-agnostic count. Schedule by Simpson model, bolt diameter and unique installed location.',
    'PAN-029': '130 bolts use 2 per 65 hold-downs; count each hold-down type and specified bolt pattern.',
    'PAN-036': '300 SQFT site cement board is 10% of an exterior wall proxy. Use panel-by-panel site repair/finish scope; reconcile FIN-107.',
    'PAN-016': '400 truss screws use 8 per 50 truss labels. Use truss bearing details and distinguish factory screws from field connections.',
    'PAN-017': '100 truss angles use 2 per truss label. Count actual bearing conditions and angle type.',
    'PAN-018': '100 truss stitch pieces use 2 per truss label. Count actual approved connection locations.',
    'PAN-019': '1,408 FT purlins derive from roof area / assumed 2-FT spacing. Use actual purlin layout and cut lengths.',
    'PAN-021': '4,223 roof screws use a 1.5/SQFT rate. Count fasteners by support line, panel span and edge/field fastening pattern.',
    'PAN-022': '845 rivets use a 0.3/SQFT rate. Count seams and per-seam fastener spacing.',
    'PAN-023': '939 FT butyl tape uses area / 3. Measure actual seams, laps and openings, then add waste by roll.',
    'FIN-061': '57 breakers are a grouped-load budget. E4.1 visually schedules 59 branch breaker devices (35 main + 24 sub; two-pole pair = one device), excluding SPACE/feed-through lugs. Reconcile plan version and equipment scope.',
    'FIN-074': 'Four faucets follow four model sink modules, while P4.1 depicts seven lav/sink locations (four bathrooms, two kitchen, one garage). Reconcile model completeness and faucet type before ordering.',
    'FIN-079': 'Four drains follow four model sink modules, while P4.1 depicts seven lav/sink locations. Confirm which fixtures include drains and whether all seven are in site scope.',
    'FIN-107': 'Two-foot cement-board band uses wall length; compare actual elevation/finish zones and PAN-036 to prevent duplicate board.',
}


def words(value):
    return {word[:-1] if word.endswith('s') and len(word) > 4 else word
            for word in re.findall(r'[a-z0-9]+', str(value or '').lower())
            if len(word) >= 3 and word not in STOP}


def text_is_reliable(text):
    return bool(text.strip()) and sum(ord(char) < 32 and char not in '\n\r\t' for char in text) / len(text) < .01


def plan_pages(path):
    records = []
    with fitz.open(path) as pdf:
        for page_no, page in enumerate(pdf, 1):
            text = page.get_text()
            reliable = text_is_reliable(text)
            tail = text[-1700:]
            codes = re.findall(r'\b[ASEMP]\d+(?:\.\d+)?\b', tail)
            records.append({'page': page_no, 'sheet': codes[-1] if codes else None,
                            'textLayerReliable': reliable, 'text': text,
                            'tokens': words(text) if reliable else set()})
    return records


def page_leads(description, pages):
    query = words(re.sub(r'^Legacy list:\s*', '', description, flags=re.I))
    if len(query) < 2:
        return []
    scored = []
    for page in pages:
        if not page['textLayerReliable']:
            continue
        matched = query & page['tokens']
        if len(matched) < 2 or len(matched) / len(query) < .65:
            continue
        scored.append((len(matched) / len(query), page['page'],
                       {'page': page['page'], 'sheet': page['sheet'],
                        'matchedTerms': sorted(matched), 'kind': 'text_mention_not_quantity_proof'}))
    return [entry for _, _, entry in sorted(scored, key=lambda row: (-row[0], row[1]))[:3]]


def extraction_candidates(folders):
    rows = []
    for folder in folders:
        if not folder.exists():
            continue
        for path in folder.glob('*.json'):
            doc = json.loads(path.read_text(encoding='utf-8'))
            if doc.get('project') != 'Monroe' or doc.get('reviewStatus') != 'candidate_only':
                continue
            for finding in doc['result']['findings']:
                rows.append({'source': doc['source'], 'page': doc['page'],
                             'sheet': doc['result'].get('sheet'), 'item': finding['item'],
                             'quantity': finding.get('quantity'), 'unit': finding.get('unit'),
                             'size': finding.get('size'), 'scope': finding.get('installationScope'),
                             'evidence': finding.get('evidence'), 'tokens': words(finding['item'])})
    return rows


def candidate_leads(description, candidates):
    query = words(re.sub(r'^Legacy list:\s*', '', description, flags=re.I))
    if len(query) < 2:
        return []
    scored = []
    for candidate in candidates:
        matched = query & candidate['tokens']
        if len(matched) < 2 or len(matched) / len(query) < .65:
            continue
        score = len(matched) / len(query)
        scored.append((score, candidate))
    result, seen = [], set()
    for score, candidate in sorted(scored, key=lambda row: -row[0]):
        key = (candidate['source'], candidate['page'], candidate['item'])
        if key in seen:
            continue
        seen.add(key)
        result.append({key: value for key, value in candidate.items() if key != 'tokens'})
        if len(result) == 3:
            break
    return result


def verify_source_counts():
    pile_rows = json.loads(PILE_SCHEDULE.read_text(encoding='utf-8'))['rows']
    by_diameter = Counter()
    for row in pile_rows:
        by_diameter[row['diameterIn'].replace('"', ' in')] += row['count']
    if dict(by_diameter) != PILE_ROWS:
        raise ValueError(f'Pile schedule rows no longer match source audit: {by_diameter}')

    elements = json.loads(MODEL_ELEMENTS.read_text(encoding='utf-8'))
    hold_downs, short_angles = Counter(), Counter()
    family_map = {'CF_SHD15S_3d_Cad_MULT_Prod': 'CF_SHD15S',
                  'CF_SHDU9_3d_Cad_MULT_Prod1': 'CF_SHDU9',
                  'CF_SHD10S_3d_Cad_MULT_Prod': 'CF_SHD10S',
                  'CF_SHD10B_3D_CAD_MULT_Prod': 'CF_SHD10B'}
    for element in elements:
        family = element.get('family', '')
        if element.get('category') == 'Structural Connections' and family in family_map:
            hold_downs[family_map[family]] += 1
        if element.get('category') != 'Structural Framing' or 'angle' not in (
                family + ' ' + element.get('type', '') + ' ' + element.get('name', '')).lower():
            continue
        cut = next((p.get('displayValue') or '' for p in element.get('parameters', [])
                    if p.get('name') == 'Cut Length'), '')
        match = re.match(r'^\s*(\d+(?:\.\d+)?)\s*(?:"|in|inch)', cut, re.I)
        if match and float(match.group(1)) <= 12:
            short_angles[f"{element['type']}, {match.group(1)} in"] += 1
    if dict(hold_downs) != HOLD_DOWNS_BY_FAMILY or dict(short_angles) != SHORT_ANGLES_BY_SIZE:
        raise ValueError(f'Model hardware counts changed: {hold_downs}, {short_angles}')


def better_math(item, audit):
    line_id = item['lineId']
    if line_id in HIGH_PRIORITY:
        return HIGH_PRIORITY[line_id]
    description = item['description'].lower()
    if 'rod' in description and ('hold' in description or 'angle' in description):
        return 'For each verified diameter, rod cut inches = 21 x unique installed hold-down/L-angle count; feet = inches / 12. Keep sizes separate.'
    if not item.get('monroeEstimate'):
        return ('Use a vendor quote, crew inventory or field measurement; the available drawings do not specify a project quantity.'
                if item['lineId'].startswith('SHEET') else 'Define a quantity basis before estimating.')
    drivers = audit.get('drivers', []) if audit else []
    kind = audit.get('auditKind') if audit else item['monroeEstimate'].get('basis')
    if kind == 'MODELED_OR_DERIVED' or kind in ('MODEL_MEASURED', 'MODEL_SCOPE_RULE'):
        return 'Count unique model element keys by exact type and location; reconcile plan tags and factory/site scope before a purchase total.'
    if 'pileScheduleCount' in drivers:
        return 'Use the 12 pile-schedule rows by shaft diameter and head code; apply connection-specific per-pile rates only after detail review.'
    if 'roofProxyArea' in drivers:
        return 'Use the roof panel/purlin layout and seam lengths, not roof area alone; calculate edge/field fasteners separately.'
    if 'wallLength' in ''.join(drivers) or 'exteriorLength' in drivers:
        return 'Measure unique installed wall runs and openings; apply the actual detail spacing and endpoint count rather than one blanket rate.'
    if 'floorArea' in ''.join(drivers) or 'Area' in ''.join(drivers):
        return 'Use the room/finish or assembly schedule for exact coverage; subtract openings/alternate finishes and apply product pack waste separately.'
    if drivers == ['project'] or kind in ('PROJECT_ASSUMPTION', 'CONFIRMED_STANDARD', 'CATALOG_ALLOWANCE'):
        return 'Project/crew allowance: validate with equipment inventory, installer method or supplier quote; plans do not define the count.'
    if drivers:
        return 'Recount the keyed model driver by type and apply the approved per-instance connection/fixture detail, then round to purchase packs.'
    return 'Verify source scope and units; do not treat a planning rate as a measured plan quantity.'


def classify(item, audit, direct):
    estimate = item.get('monroeEstimate')
    if item['lineId'] in HIGH_PRIORITY:
        return 'priority_reconcile'
    if direct:
        return 'drawing_schedule_count'
    if estimate is None:
        return 'listed_or_unknown_without_estimate'
    if audit and audit['auditKind'] == 'MODELED_OR_DERIVED':
        return 'model_count_check_plan_scope'
    if estimate['basis'] in ('PLANNING_PLACEHOLDER', 'PLANNING_CONDITIONAL_ZERO'):
        return 'undefined_or_conditional'
    if estimate['basis'] == 'CONFIRMED_STANDARD':
        return 'crew_standard_not_plan_quantity'
    return 'planning_math_valid_scope_unverified'


def write_report(output_root, summary, results):
    status = summary['auditStatusCounts']
    priority = [row for row in results if row['priority'] == 'high']
    lines = [
        '# Monroe SiteBOM quantity audit', '',
        f"Live Google Sheet revision **{summary['liveRevision']}**, updated {summary['liveUpdatedAt']}. "
        'This is a read-only review. It does not change purchase quantities.', '',
        '## Coverage and limits', '',
        f"- {summary['liveItems']} of {summary['liveItems']} live items have individual rows in `per-item-audit.csv` "
        '(listed quantity, planning quantity, formula, basis, model count, review note, drawing leads and proposed better math).',
        f"- {summary['modelAuditRowsReconciled']} live items match the existing independent model-calculator audit. "
        'This verifies the recorded arithmetic, not the design rate, installation scope or purchase amount.',
        f"- {summary['listedCount']} lines have user-listed quantities; {summary['planningCount']} have planning estimates; "
        f"{summary['siteQuantityCount']} have entered site quantities.",
        f"- {status.get('priority_reconcile', 0)} priority conflicts or weak formulas; "
        f"{status.get('model_count_check_plan_scope', 0)} model-count items needing plan/scope review; "
        f"{status.get('undefined_or_conditional', 0)} conditional or placeholder quantities; "
        f"{status.get('listed_or_unknown_without_estimate', 0)} listed or unknown items without calculated estimates.",
        '- The 52-page March 25, 2026 State Set has 36 usable PDF text layers. Structural pages 28-43 duplicate the '
        '16-page SE PDF; those were read from the SE copy. Gemini candidate findings are search leads only. '
        'No drawing match in the CSV means quantity has not been proven from the plans.',
        '- The later wall/floor shop PDFs and October Export Everything model may supersede some March plan details. '
        'Resolve revisions with the design team before buying material.', '',
        '## Directly checked drawing and model quantities', '',
        '| Item | Current BOM | Source count | Finding |', '| --- | ---: | ---: | --- |',
        '| Helical piles, legacy 6 in + 4 in (`SHEET-016/017`) | 50 + 25 = 75 | 48 | '
        'Structural schedule p30 / SE p3: 9 at 3½ in, 22 at 4½ in, 17 at 2⅞ in. '
        'The live BOM has no canonical 48-pile line. Replace the legacy size/count rows after approval. |',
        '| Pile caps (`SHEET-018`) | 75 | 48 head locations | '
        'The schedule lists GTC03723 ×9, GTC03796 ×22, GTC03795 ×17. Confirm whether separate caps are part of these heads. |',
        '| Branch breakers (`FIN-061`) | 57 planned | 59 scheduled | '
        'E4.1 p46: 35 main + 24 sub devices; circuit pairs count once, spaces and feed-through lugs excluded. |',
        '| Toilet bowls (`FIN-154`) | 4 planned | 4 schematic WC locations | '
        'P4.1 p51 agrees on count; product and site scope remain to verify. |',
        '| Sink faucets and drains (`FIN-074/079`) | 4 each planned | 7 lav/sink locations | '
        'P4.1 p51 depicts 4 baths, 2 kitchen, 1 garage; reconcile model omissions and fixture packages. |',
        '| Hold-down plus short-angle rod locations | no grouped purchase total | 65 + 37 = 102 candidates | '
        'Export model: 36 SHD15S, 21 SHDU9, 4 SHD10S, 4 SHD10B; '
        '31 + 4 + 2 short angles. At 21 in per confirmed location, 2,142 in = 178.5 ft. '
        'Anchor diameter parameters are blank, and ½-in for short angles is only a software default. |', '',
        '## Better calculation rules', '',
        '1. **Pile order:** group schedule rows by actual shaft diameter and head code. '
        'Keep installed quantity, extension need, caps/heads and spares as separate fields. '
        'Extensions = sum over pile IDs of `ceil(max(0, required depth - supplied shaft length) / extension length)`, '
        'with stock lengths and installer-approved depth inputs.',
        '2. **Rod:** for each verified diameter, `cut pieces = unique installed hold-downs + unique short angles`; '
        '`cut inches = pieces × 21`; `net feet = cut inches / 12`. '
        'Optimize stock bar cuts by diameter and kerf, then add a documented waste allowance. '
        'Do not use the existing 2-ft-per-beam proxy or mix diameters.',
        '3. **Connection hardware:** count bolts, nuts and washers per distinct approved connection detail, '
        'multiply by unique occurrences, and subtract factory-installed or included hardware. '
        'The current 20-washers-per-pile rate has no schedule support.',
        '4. **Electrical and plumbing:** count scheduled panel devices by pole/device type, '
        'and fixture locations by symbol and fixture package. Reconcile drawing revision with the model before replacing a live estimate.',
        '5. **Panels and roof:** calculate fasteners from actual connection points and approved spacing, '
        'purlins from cut lists, tape from seam lengths, and finish material from net elevations. '
        'Track factory and site scope separately; round only when converting net demand to purchase packs.', '',
        '## Priority line review', '',
        '| Live ID | Listed | Planning | Unit | Audit finding / better math |',
        '| --- | ---: | ---: | --- | --- |',
    ]
    for row in priority:
        note = row['betterMath'].replace('|', '/').replace('\n', ' ')
        lines.append(f"| `{row['lineId']}` {row['description'].replace('|', '/')} | "
                     f"{row['listedQuantity'] if row['listedQuantity'] is not None else '—'} | "
                     f"{row['planningQuantity'] if row['planningQuantity'] is not None else '—'} | "
                     f"{row['unit'] or '—'} | {note} |")
    lines.extend(['', '## Sources and reproducibility', '',
                  f"- State Set: `{summary['planSet']['path']}`; SHA-256 `{summary['planSet']['sha256']}`.",
                  '- Structural schedule: `Downloads/Data for SiteBOM/AI Core/Monroe SE sheets.pdf`, page 3.',
                  '- Model element cache: `G:/My Drive/SiteBOM/_Internal/Model-Data/monroe-takeoff-elements.json`.',
                  f"- Live state: `live-state-rev{summary['liveRevision']}.json`, retrieved from the revisioned Google Sheet API.",
                  '- Model arithmetic: `G:/My Drive/SiteBOM/05-Monroe/Monroe-Value-Audit.json`.',
                  '- AI source candidates: `G:/My Drive/SiteBOM/04-Audits/Monroe-AI/` and `plan-set-review/`.',
                  '- Re-run: `python scripts/monroe_full_quantity_audit.py` fetches and audits the current live revision.',
                  '- Before using this for orders, obtain the latest approved plan/shop revision and confirm site versus factory scope.'])
    (output_root / 'audit-summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build(live_path, output_root, plan_pdf):
    output_root.mkdir(parents=True, exist_ok=True)
    verify_source_counts()
    live = json.loads(live_path.read_text(encoding='utf-8'))
    if live.get('schema') != 'neovi.site-bom.live.v1' or live.get('revision') is None:
        raise ValueError('Not a revisioned live Monroe SiteBOM state')
    model = json.loads(MODEL_AUDIT.read_text(encoding='utf-8'))
    model_rows = {item['lineId']: item for item in model['items']}
    pages = plan_pages(plan_pdf)
    candidates = extraction_candidates((CORE_EXTRACTIONS, output_root / 'plan-set-review/extractions'))
    results = []
    for item in live['items']:
        line_id = item['lineId']
        audit = model_rows.get(line_id)
        estimate = item.get('monroeEstimate') or {}
        if audit and estimate.get('quantity') != audit['quantity']:
            raise ValueError(f'Live/model audit quantity mismatch: {line_id}')
        direct = DIRECT_PLAN.get(line_id)
        leads = page_leads(item['description'], pages)
        ai_leads = candidate_leads(item['description'], candidates)
        listed, planned = item.get('listedQuantity'), estimate.get('quantity')
        row = {'lineId': line_id, 'phase': item.get('phase'),
               'workArea': item.get('stage'), 'description': item['description'],
               'specification': item.get('specification'), 'unit': item.get('unit'),
               'listedQuantity': listed, 'planningQuantity': planned,
               'siteQuantity': item.get('siteQuantity'),
               'listedMinusPlanning': listed - planned if isinstance(listed, (int, float)) and
                   isinstance(planned, (int, float)) and item.get('unit') == estimate.get('unit') else None,
               'estimateBasis': estimate.get('basis'), 'formula': estimate.get('formula'),
               'assumption': estimate.get('assumption'), 'modelAuditKind': audit.get('auditKind') if audit else None,
               'arithmeticCheck': audit.get('arithmeticCheck') if audit else
                   'Sheet allowance formula recorded' if estimate else 'No calculation',
               'modelReferenceCount': audit.get('modelReferenceCount') if audit else None,
               'drawingScheduleEvidence': direct or (
                   'E4.1, PDF page 46: 59 scheduled branch breaker devices (35 main + 24 sub), counted as devices, not circuit numbers.'
                   if line_id == 'FIN-061' else
                   'P4.1, PDF page 51: four WC symbols; one in each of bathrooms 1-4.'
                   if line_id == 'FIN-154' else
                   'P4.1, PDF page 51: seven lav/sink symbols; bathrooms 1-4, two kitchen, one garage.'
                   if line_id in ('FIN-074', 'FIN-079') else None),
               'planPageLeads': leads, 'aiCandidateLeads': ai_leads,
               'reviewNote': audit.get('reviewNote') if audit else item.get('estimateReview'),
               'betterMath': better_math(item, audit), 'auditStatus': classify(item, audit, direct),
               'priority': 'high' if line_id in HIGH_PRIORITY else 'medium' if estimate else 'low'}
        results.append(row)
    if len(results) != len(live['items']) or len({row['lineId'] for row in results}) != len(results):
        raise ValueError('The item audit did not cover every unique live line')
    if sum(PILE_ROWS.values()) != 48 or sum(PILE_HEADS.values()) != 48:
        raise ValueError('Pile schedule subtotal changed')
    if sum(BREAKER_BY_TYPE.values()) != 59:
        raise ValueError('Panel schedule device subtotal changed')
    hold_downs, short_angles = sum(HOLD_DOWNS_BY_FAMILY.values()), sum(SHORT_ANGLES_BY_SIZE.values())
    if hold_downs != 65 or short_angles != 37:
        raise ValueError('Model-selected hardware subtotal changed')
    summary = {'schema': 'monroe-full-quantity-audit-1', 'liveRevision': live['revision'],
               'liveUpdatedAt': live.get('updatedAt'), 'liveItems': len(results),
               'listedCount': sum(row['listedQuantity'] is not None for row in results),
               'planningCount': sum(row['planningQuantity'] is not None for row in results),
               'siteQuantityCount': sum(row['siteQuantity'] is not None for row in results),
               'modelAuditRowsReconciled': sum(row['modelAuditKind'] is not None for row in results),
               'auditStatusCounts': dict(Counter(row['auditStatus'] for row in results)),
               'structuralPileSchedule': {'source': 'State Set PDF p30 = SE PDF p3',
                                          'total': 48, 'byDiameter': PILE_ROWS, 'headsByCode': PILE_HEADS,
                                          'canonical48PileRowInLiveBOM': any(row['lineId'] == 'FND-006' for row in results),
                                          'legacyLiveRows': ['SHEET-016', 'SHEET-017', 'SHEET-018']},
               'panelSchedule': {'source': 'State Set PDF p46 / E4.1', 'planDate': '2026-03-25',
                                 'mainBranchDevices': 35, 'subBranchDevices': 24,
                                 'totalBranchDevices': sum(BREAKER_BY_TYPE.values()),
                                 'byType': BREAKER_BY_TYPE,
                                 'currentPlanningCount': next(row['planningQuantity'] for row in results if row['lineId'] == 'FIN-061')},
               'plumbingSchematic': {'source': 'State Set PDF p51 / P4.1',
                                     'toilets': 4, 'sinkLavLocations': 7,
                                     'currentSinkFaucetPlanningCount': next(row['planningQuantity'] for row in results if row['lineId'] == 'FIN-074'),
                                     'note': 'Schematic symbols indicate locations, not fixture product or site purchase scope.'},
               'rodTakeoff': {'source': 'Export Everything model, selected Structural Connections and <=12 in cut angles',
                              'holdDownsByFamily': HOLD_DOWNS_BY_FAMILY, 'shortAnglesBySize': SHORT_ANGLES_BY_SIZE,
                              'candidateLocations': hold_downs + short_angles,
                              'cutLengthInPerLocation': 21,
                              'candidateCutLengthIn': 21 * (hold_downs + short_angles),
                              'candidateCutLengthFt': 21 * (hold_downs + short_angles) / 12,
                              'diameterStatus': 'Hold-down diameter parameters are blank in the model; short-angle 1/2 in is a code default. Do not order by diameter without plan/detail review.',
                              'scopeStatus': 'Model locations are candidates; confirm one field-installed rod per location.'},
               'planSet': {'path': str(plan_pdf), 'sha256': hashlib.sha256(plan_pdf.read_bytes()).hexdigest(),
                           'pages': len(pages), 'textReliablePages': sum(p['textLayerReliable'] for p in pages)},
               'aiCandidateCount': len(candidates),
               'warning': 'Drawing mentions and AI candidates are leads only, not quantity proof. No live BOM write.'}
    (output_root / 'full-audit-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output_root / 'per-item-audit.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    with (output_root / 'per-item-audit.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        keys = ['lineId', 'phase', 'workArea', 'description', 'specification', 'unit',
                'listedQuantity', 'planningQuantity', 'siteQuantity', 'listedMinusPlanning',
                'estimateBasis', 'modelAuditKind', 'arithmeticCheck', 'modelReferenceCount',
                'drawingScheduleEvidence', 'planPageLeads', 'aiCandidateLeads',
                'formula', 'assumption', 'reviewNote', 'betterMath', 'auditStatus', 'priority']
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], (dict, list))
                          else row[key] for key in keys} for row in results)
    write_report(output_root, summary, results)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-state', type=Path,
                        help='Use a saved API snapshot instead of fetching the current live revision')
    parser.add_argument('--output-root', type=Path, default=OUTPUT)
    parser.add_argument('--plan-pdf', type=Path, default=PLAN_PDF)
    args = parser.parse_args()
    live_path = args.live_state
    if live_path is None:
        endpoint = json.loads((ROOT / 'config/live-site-endpoint.json').read_text(encoding='utf-8'))['url']
        with urllib.request.urlopen(endpoint, timeout=30) as response:
            live = json.load(response)
        if live.get('schema') != 'neovi.site-bom.live.v1' or not isinstance(live.get('revision'), int):
            raise ValueError('The live API did not return a revisioned SiteBOM state')
        args.output_root.mkdir(parents=True, exist_ok=True)
        live_path = args.output_root / f"live-state-rev{live['revision']}.json"
        live_path.write_text(json.dumps(live, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(build(live_path, args.output_root, args.plan_pdf), indent=2))


if __name__ == '__main__':
    main()
