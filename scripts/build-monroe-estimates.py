"""Build a complete, traceable Monroe model quantity and planning report."""
import json
import math
from collections import Counter
from pathlib import Path

from model_takeoff_rules import parameter, select_unique
from planning_estimates import planning_drivers
from project_model_mapper import map_model

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'outputs/NeoviBOM/_Internal/Model-Data'
DEST = ROOT / 'outputs/NeoviBOM/05-Monroe'

# Each benchmark uses the denominator that actually controls its takeoff. Area
# rates are extra comparisons where a square-foot proxy is useful.
FASTENER_BENCHMARKS = {
    'PAN-006': ('floorPlates', 'floor plate', None),
    'PAN-009': ('wallLength', 'wall FT', None),
    'PAN-010': ('wallLength', 'wall FT', None),
    'PAN-030': ('wallLength', 'wall FT', None),
    'PAN-016': ('trussCount', 'truss', 'roofProxyArea'),
    'PAN-040': ('roofProxyArea', 'roof SQFT', 'roofProxyArea'),
    'PAN-021': ('roofProxyArea', 'roof SQFT', 'roofProxyArea'),
    'PAN-022': ('roofProxyArea', 'roof SQFT', 'roofProxyArea'),
    'FIN-084': ('doors', 'door', None),
    'FIN-088': ('windows', 'window', None),
    'FIN-166': ('garageArea', 'garage SQFT', 'garageArea'),
    'FIN-103': ('floorArea', 'livable SQFT', 'floorArea'),
    'FIN-108': ('trussFinishBoardArea', 'truss finish board SQFT', 'trussFinishBoardArea'),
    'FIN-111': ('exteriorLength', 'exterior-wall FT', None),
    'FIN-114': ('exteriorLength', 'exterior-wall FT', None),
}

AREA_LABELS = {'floorArea': 'livable SQFT', 'firstStoryArea': 'first-story SQFT',
               'secondStoryArea': 'second-story SQFT', 'roofProxyArea': 'roof SQFT',
               'garageArea': 'garage SQFT', 'dryFloorArea': 'dry-room SQFT',
               'wetRoomArea': 'wet-room SQFT',
               'exteriorWallGrossFaceArea': 'gross exterior-wall SQFT',
               'exteriorWallNetFaceAreaProxy': 'net exterior-wall SQFT proxy',
               'garageWallGrossFaceArea': 'gross garage-wall SQFT',
               'trussFinishBoardArea': 'truss finish board SQFT',
               'interiorWallGrossFaceArea': 'gross interior-wall SQFT'}


def driver(value, references, description):
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'Invalid driver: {description}')
    return {'value': value, 'references': references, 'description': description}


def monroe_drivers(rows, mapped, openings, story_areas):
    result = planning_drivers(rows, mapped, openings)
    unique = select_unique(rows)
    host = [e for e in unique if e.get('sourceKey') == 'host']
    livable = [e for e in host if e.get('category') == 'Floors' and
               e.get('type') == 'Area Takeoff - Standard - Livable']
    for name, level in [('firstStoryArea', 'FIRST FLOOR'), ('secondStoryArea', 'SECOND FLOOR')]:
        floors = [e for e in livable if e.get('level') == level]
        audit = story_areas[level]
        if (not floors or any(parameter(e, 'Area', 'area') is None for e in floors) or
                {e['key'] for e in floors} != {e['key'] for e in audit['elements']} or
                not math.isclose(sum(parameter(e, 'Area', 'area') for e in floors),
                                 audit['rawElementAreaSumSqft'], abs_tol=0.01)):
            raise ValueError('Missing or ambiguous Monroe ' + name)
        refs = [e['key'] for e in floors]
        if level == 'FIRST FLOOR':
            refs.append(audit['garageRoomKey'])
            result['firstStoryGrossArea'] = driver(audit['areaSqft'], [e['key'] for e in floors],
                'XY union of overlapping first-story livable floor meshes before garage-room exclusion')
        description = (f"{level} floor XY union {audit['areaSqft']:.3f} SQFT"
                       if level == 'SECOND FLOOR' else
                       f"{level} floor XY union {audit['areaSqft']:.3f} SQFT minus "
                       f"{audit['garageOverlapSqft']:.3f} SQFT garage overlap")
        result[name] = driver(audit['netLivableAreaSqft'], refs, description)
    result['floorArea'] = driver(result['firstStoryArea']['value'] + result['secondStoryArea']['value'],
        result['firstStoryArea']['references'] + result['secondStoryArea']['references'],
        'first-story net livable XY union + second-story livable XY union')
    host_index = {e['key']: e for e in host}
    for source, plural in [('doors', 'Doors'), ('windows', 'Windows')]:
        if not all(key in host_index for key in result[source]['references']):
            raise ValueError('Opening references missing from Monroe host model: ' + source)
        for name, level in [('firstStory', 'FIRST FLOOR'), ('secondStory', 'SECOND FLOOR')]:
            keys = [key for key in result[source]['references'] if host_index[key].get('level') == level]
            result[name + plural] = driver(len(keys), keys,
                f'COUNT(modeled {source} hosted on {level}); exact story allocation for frame screws')
        if result['firstStory' + plural]['value'] + result['secondStory' + plural]['value'] != result[source]['value']:
            raise ValueError('Modeled ' + source + ' cannot all be assigned to a story')
    wall_details = openings.get('supplemental', {}).get('WALL-TRIM', {}).get('wallDetails', [])
    wall_index = {e['key']: e for e in host if e.get('category') == 'Walls'}
    if not wall_details or any(detail['key'] not in wall_index or detail['length'] is None
                               for detail in wall_details):
        raise ValueError('Modeled story wall lengths unavailable')
    for name, level in [('firstStoryWallLength', 'FIRST FLOOR'),
                        ('secondStoryWallLength', 'SECOND FLOOR')]:
        details = [detail for detail in wall_details if wall_index[detail['key']].get('level') == level]
        if not details:
            raise ValueError('No modeled wall runs on ' + level)
        result[name] = driver(sum(detail['length'] for detail in details),
            [detail['key'] for detail in details],
            f"SUM(host stud-wall Length FT on {level}; each physical wall counted once)")
    if not math.isclose(result['firstStoryWallLength']['value'] +
                        result['secondStoryWallLength']['value'], result['wallLength']['value'], abs_tol=0.001):
        raise ValueError('Story wall lengths do not reconcile with project wall length')
    wall_groups = {
        'interiorWallLength': [w for w in wall_details if w['classification'] == 'Interior'],
        'exteriorWallLength': [w for w in wall_details if w['classification'] == 'Exterior'],
        'garageWallLength': [w for w in wall_details if 'garage' in w['type'].lower()],
        'nonGarageExteriorWallLength': [w for w in wall_details if w['classification'] == 'Exterior'
                                        and 'garage' not in w['type'].lower()],
    }
    if (not all(wall_groups.values()) or
            any(w['classification'] != 'Exterior' for w in wall_groups['garageWallLength'])):
        raise ValueError('Garage/interior/exterior stud-wall classification changed')
    for name, details in wall_groups.items():
        result[name] = driver(sum(w['length'] for w in details), [w['key'] for w in details],
            f"SUM(typed Length FT of {len(details)} {name} host stud-wall runs; each physical wall once)")
        if name in ('interiorWallLength', 'exteriorWallLength'):
            for prefix, level in [('firstStory', 'FIRST FLOOR'), ('secondStory', 'SECOND FLOOR')]:
                selected = [w for w in details if wall_index[w['key']].get('level') == level]
                if not selected:
                    raise ValueError('Missing ' + name + ' on ' + level)
                result[prefix + name[0].upper() + name[1:]] = driver(
                    sum(w['length'] for w in selected), [w['key'] for w in selected],
                    f'SUM({name} on {level}; typed host stud-wall Length FT)')
        area_name = name.replace('Length', 'GrossFaceArea')
        heights = [(wall_index[w['key']]['bounds']['max']['z'] -
                    wall_index[w['key']]['bounds']['min']['z']) for w in details]
        if any(not math.isfinite(h) or h <= 0 or h > 30 for h in heights):
            raise ValueError('Wall gross-height proxy requires review: ' + name)
        result[area_name] = driver(sum(w['length'] * h for w, h in zip(details, heights)),
            [w['key'] for w in details],
            f'SUM(each {name} FT x its model bounding-box height FT); one gross face, openings not deducted')
        net_name = name.replace('Length', 'NetFaceAreaProxy')
        typed = [parameter(wall_index[w['key']], 'Area', 'area') for w in details]
        if any(a is not None and (a <= 0 or a > w['length'] * h + 0.1)
               for w, h, a in zip(details, heights, typed)):
            raise ValueError('Typed wall Area outside gross face: ' + name)
        missing = sum(a is None for a in typed)
        result[net_name] = driver(sum(a if a is not None else w['length'] * h
                                      for w, h, a in zip(details, heights, typed)),
            [w['key'] for w in details],
            f'SUM({len(details) - missing} typed wall Area SQFT plus {missing} gross Length x height fallback); '
            'one-face net-area proxy, typed openings deducted')
    if (not math.isclose(result['interiorWallLength']['value'] + result['exteriorWallLength']['value'],
                         result['wallLength']['value'], abs_tol=0.001) or
            not math.isclose(result['exteriorWallLength']['value'], result['garageWallLength']['value'] +
                             result['nonGarageExteriorWallLength']['value'], abs_tol=0.001)):
        raise ValueError('Wall type lengths do not reconcile')
    result['trussFinishBoardArea'] = driver(result['exteriorWallLength']['value'] * 2,
        result['exteriorWallLength']['references'],
        'Exterior host stud-wall run FT x assumed 2-FT-high truss-finish concrete-board band; proxy, not modeled board')
    rooms = [e for e in host if e.get('category') == 'Rooms' and
             e.get('level') in ('FIRST FLOOR', 'SECOND FLOOR')]
    if not rooms or any(parameter(e, 'Area', 'area') is None or parameter(e, 'Name') is None for e in rooms):
        raise ValueError('Incomplete Monroe room areas')
    garage = [e for e in rooms if parameter(e, 'Name') == 'GARAGE']
    if len(garage) != 1 or garage[0]['key'] != story_areas['FIRST FLOOR']['garageRoomKey']:
        raise ValueError('Garage room changed since geometry scan')
    result['garageArea'] = driver(parameter(garage[0], 'Area', 'area'), [garage[0]['key']],
                                  'modeled GARAGE room Area SQFT; horizontal ceiling proxy')
    garage_perimeter = parameter(garage[0], 'Perimeter', 'length')
    if garage_perimeter is None or garage_perimeter < result['garageWallLength']['value']:
        raise ValueError('Modeled GARAGE room perimeter requires review')
    result['garageRoomPerimeter'] = driver(garage_perimeter, [garage[0]['key']],
        'modeled GARAGE room Perimeter FT; includes boundaries without selected stud-wall runs')
    wet_names = ('BATH', 'POWDER', 'WC', 'LAUNDRY')
    wet = [e for e in rooms if parameter(e, 'Name').upper().startswith(wet_names)]
    dry = [e for e in rooms if e not in wet and e not in garage]
    result['wetRoomArea'] = driver(sum(parameter(e, 'Area', 'area') for e in wet),
                                  [e['key'] for e in wet], 'SUM(bath, powder, WC and laundry room Area SQFT)')
    result['dryFloorArea'] = driver(sum(parameter(e, 'Area', 'area') for e in dry),
                                   [e['key'] for e in dry],
                                   'SUM(non-garage, non-wet room Area SQFT); finish floor coverage proxy')
    kitchen = [e for e in host if e.get('category') == 'Plumbing Fixtures' and
               e.get('family') == 'BSB Sink - Single']
    bathrooms = [e for e in host if e.get('category') == 'Plumbing Fixtures' and
                 e.get('family', '').startswith('Neovi_Bathroom-Sink-Cutout')]
    if not kitchen or not bathrooms:
        raise ValueError('Sink proxy source disappeared; review fixture selection')
    result['sinks'] = driver(len(kitchen) + len(bathrooms),
                             [e['key'] for e in kitchen + bathrooms],
                             'COUNT(kitchen sink fixtures + bathroom sink cutouts); planning fixture proxy')
    result['bathroomSinks'] = driver(len(bathrooms), [e['key'] for e in bathrooms],
                                     'COUNT(bathroom sink cutouts); planning fixture proxy')
    result['coldFixtures'] = driver(result['sinks']['value'] + result['toilets']['value'],
                                    result['sinks']['references'] + result['toilets']['references'],
                                    'sink proxy count + modeled toilet count')
    toilet_cutouts = [e for e in host if e.get('category') == 'Plumbing Equipment' and
                      e.get('family') == 'Neovi_PE_Toilet']
    result['toiletCutouts'] = driver(len(toilet_cutouts), [e['key'] for e in toilet_cutouts],
        'COUNT(toilet rough-in cutouts); comparison with modeled toilet fixtures, not an added toilet count')
    windows = [e for e in host if e.get('category') == 'Windows' and
               not any(word in (e.get('family', '') + ' ' + e.get('type', '')).lower()
                       for word in ('skylight', 'suntunnel', 'sun_tunnel', 'sun tunnel'))]
    fixed_windows = [e for e in windows if e.get('family') == 'Neovi_WD_Fixed']
    operable_windows = [e for e in windows if e.get('family', '').startswith('Neovi_WD_Tilt&Turn') or
                        'Hung' in e.get('family', '')]
    if (len(windows) != result['windows']['value'] or
            len(fixed_windows) + len(operable_windows) != len(windows)):
        raise ValueError('Monroe window operation types need review')
    result['operableWindows'] = driver(len(operable_windows),
        [e['key'] for e in operable_windows],
        'COUNT(tilt-and-turn plus hung windows); fixed windows excluded from screen/handle allowance')
    result['fixedWindows'] = driver(len(fixed_windows), [e['key'] for e in fixed_windows],
        'COUNT(Neovi_WD_Fixed); no operable screen or handle assumed')
    smart_controls = [e for e in host if e.get('category') == 'Electrical Fixtures' and
                      e.get('family') == 'Neovi_EF_Smart Touch Panel']
    result['smartControls'] = driver(len(smart_controls), [e['key'] for e in smart_controls],
        'COUNT(modeled Smart Button and Smart Touch Panel positions); low-voltage routing proxy')
    light_families = ('Neovi_EF_LED Strip', 'Neovi_LF_Downlight_Ceiling',
                      'Neovi_LF_Exterior Lighting Fixture', 'PENDANT LINEAR LED LIGHT FIXTURE')
    light_loads = [e for e in host if e.get('family') in light_families]
    fan_loads = [e for e in host if e.get('category') == 'Mechanical Equipment' and
                 e.get('family') in ('Neovi_EF_AeroPure Vent Fan', 'Neovi_ME_Exhaust-Fan-Only')]
    result['lightAndFanPositions'] = driver(len(light_loads) + len(fan_loads),
        [e['key'] for e in light_loads + fan_loads],
        'COUNT(LED strips, downlights, exterior/pendant lights and vent fans); grouped circuit proxy')
    battery = [e for e in host if e.get('category') == 'Electrical Equipment' and
               e.get('family') == 'Tesla-Powerwall2']
    result['batteryUnits'] = driver(len(battery), [e['key'] for e in battery],
        'COUNT(modeled Tesla Powerwall units); one breaker allowance per unit')
    for lid in ('FIN-058', 'FIN-059', 'FIN-060'):
        if lid not in mapped:
            raise ValueError('Outlet mapping missing: ' + lid)
    outlet_elements = [e for e in host if e.get('category') == 'Electrical Fixtures' and
                       e.get('family') in ('Neovi_EF-Outlet_Horizontal',
                                           'Neovi_EF-Garage Outlet_Horizontal',
                                           'Neovi_EF-Exterior Outlet_Horizontal')]
    outlet_keys = {e['key'] for e in outlet_elements}
    mapped_outlet_keys = {key for lid in ('FIN-058', 'FIN-059', 'FIN-060')
                          for key in mapped[lid]['references']}
    if outlet_keys != mapped_outlet_keys:
        raise ValueError('Some modeled outlet types have no cover class: ' +
                         str(sorted(outlet_keys - mapped_outlet_keys)))
    standard_outlets = mapped['FIN-058']['value'] + mapped['FIN-060']['value']
    result['standardOutlets'] = driver(standard_outlets,
        mapped['FIN-058']['references'] + mapped['FIN-060']['references'],
        'ordinary interior + exterior outlet cover equivalents; one stacked location contributes two, high-amperage positions excluded')
    high_amp = mapped['FIN-059']['elements']
    for name, amperage in [('highAmp30', '30 AMP'), ('highAmp50', '50 AMP')]:
        subset = [e for e in high_amp if amperage in e['type'].upper()]
        if not subset:
            raise ValueError('No modeled ' + amperage + ' outlet positions')
        result[name] = driver(sum(e['value'] for e in subset), [e['key'] for e in subset],
            'COUNT(modeled ' + amperage + ' outlet positions)')
    if result['highAmp30']['value'] + result['highAmp50']['value'] != mapped['FIN-059']['value']:
        raise ValueError('High-amperage outlet classes do not reconcile')
    ac_units = [e for e in host if e.get('category') == 'Mechanical Equipment' and
                e.get('family') == 'Neovi_ME_Prouall PWD1-10HD-W']
    ac_covers = [e for e in host if e.get('family') == 'Neovi_GM_PTAC Cover']
    if not ac_units or len(ac_units) != len(ac_covers):
        raise ValueError('Indoor AC positions and covers need reconciliation')
    result['indoorUnits'] = driver(len(ac_units), [e['key'] for e in ac_units],
        'COUNT(Prouall wall-mounted mechanical units); model-specific proxy for indoor AC positions')
    sheathing = [e for e in host if e.get('category') == 'Roofs' and
                 e.get('type') == 'Sheathing_7 1/2" - Vertical']
    if not sheathing or any(parameter(e, 'Area', 'area') is None for e in sheathing):
        raise ValueError('Roof sheathing areas unavailable')
    result['roofProxyArea'] = driver(sum(parameter(e, 'Area', 'area') for e in sheathing),
        [e['key'] for e in sheathing],
        'SUM(host roof sheathing Area SQFT); roof-panel coverage proxy, excluding small generic roof objects')
    result['gutterLength'] = driver(mapped['FIN-115']['value'], mapped['FIN-115']['references'],
        'SUM(typed Length FT of modeled gutter runs); fascia and soffit lengths are not identified')
    clip_evidence = openings['hardwareEvidence'].get('Floor clip fastener positions')
    if not clip_evidence:
        raise ValueError('Floor-clip fastener-position evidence missing')
    result['floorClipFastenerPositions'] = driver(clip_evidence['value'], clip_evidence['references'],
        'SUM(typed leg fastener positions on linked floor clips); fastener type and site/factory scope unknown')
    saddles = [e for e in unique if e.get('sourceKey', '').startswith('host/') and
               e.get('category') == 'Structural Connections' and e.get('family') == 'Base Plate U Saddle' and
               str(parameter(e, 'Host')).upper() == 'LEVEL : PILE CAP']
    if not saddles:
        raise ValueError('No linked pile-cap saddle positions found')
    result['pileProxy'] = driver(len(saddles), [e['key'] for e in saddles],
        'COUNT(linked U saddles hosted on PILE CAP); proxy positions, not confirmed piles')
    result['pileAreaBenchmark'] = driver(math.ceil(result['firstStoryGrossArea']['value'] / 125),
        result['firstStoryGrossArea']['references'],
        'CEILING(first-story gross footprint / 125 SQFT per pile); comparison assumption only')
    trusses = [e for e in unique if e.get('sourceKey', '').startswith('host/') and
               e.get('family') == 'TrussLabel']
    if not trusses:
        raise ValueError('No linked truss labels found')
    result['trussCount'] = driver(len(trusses), [e['key'] for e in trusses],
        'COUNT(linked TrussLabel instances); proxy for truss assemblies')
    for name, line in [('floorPlates', 'PAN-002'), ('holdDowns', 'PAN-013')]:
        if line not in mapped:
            raise ValueError('Expected model mapping missing: ' + line)
        result[name] = driver(mapped[line]['value'], mapped[line]['references'],
                              'selected model elements mapped to ' + line)
    if 'FIN-087' not in mapped:
        raise ValueError('Expected window trim mapping missing')
    result['windowTrimLength'] = driver(mapped['FIN-087']['value'], mapped['FIN-087']['references'],
                                       'model-derived installed window-trim run FT')
    shades = [e for e in host if e.get('family') == 'Neovi_GM_Window Shade - WallBased']
    result['shadeCount'] = driver(len(shades), [e['key'] for e in shades],
        'COUNT(wall-based window-shade assemblies); electrical controls excluded')
    fans = [e for e in host if e.get('category') == 'Mechanical Equipment' and
            e.get('family') in ('Neovi_EF_AeroPure Vent Fan', 'Neovi_ME_Exhaust-Fan-Only')]
    result['fanCount'] = driver(len(fans), [e['key'] for e in fans],
        'COUNT(AeroPure and exhaust-only fan instances); covers may be included')
    led_face = [e for e in host if e.get('family') == 'Neovi_LF_LED Profile_Perimeter_FaceBased']
    led_wall = [e for e in host if e.get('family') == 'Neovi_LF_LED Profile_Perimeter_Wall Based']
    if not led_face or not led_wall or any(parameter(e, 'Neovi_Length', 'length') is None for e in led_face + led_wall):
        raise ValueError('LED profile length missing')
    def midpoint(element, axis):
        bounds = element['bounds']
        return (bounds['min'][axis] + bounds['max'][axis]) / 2
    def long_axis(element):
        bounds = element['bounds']
        return 'x' if bounds['max']['x'] - bounds['min']['x'] > bounds['max']['y'] - bounds['min']['y'] else 'y'
    def same_led_run(wall, face):
        axis = long_axis(wall)
        cross_axis = 'y' if axis == 'x' else 'x'
        return (axis == long_axis(face) and
                abs(midpoint(wall, 'z') - midpoint(face, 'z')) < 0.25 and
                abs(midpoint(wall, cross_axis) - midpoint(face, cross_axis)) < 0.2 and
                abs(midpoint(wall, axis) - midpoint(face, axis)) < 0.3 and
                abs(parameter(wall, 'Neovi_Length', 'length') - parameter(face, 'Neovi_Length', 'length')) < 0.5)
    candidates = []
    for wall in led_wall:
        for face in led_face:
            if same_led_run(wall, face):
                axis = long_axis(wall)
                cross_axis = 'y' if axis == 'x' else 'x'
                score = (abs(midpoint(wall, cross_axis) - midpoint(face, cross_axis)) / 0.2 +
                         abs(midpoint(wall, axis) - midpoint(face, axis)) / 0.3 +
                         abs(midpoint(wall, 'z') - midpoint(face, 'z')) / 0.25 +
                         abs(parameter(wall, 'Neovi_Length', 'length') - parameter(face, 'Neovi_Length', 'length')) / 0.5)
                candidates.append((score, wall, face))
    matched_walls, matched_faces = set(), set()
    for _, wall, face in sorted(candidates, key=lambda row: row[0]):
        if wall['key'] not in matched_walls and face['key'] not in matched_faces:
            matched_walls.add(wall['key'])
            matched_faces.add(face['key'])
    duplicate_keys = matched_walls
    led_unique = led_face + [wall for wall in led_wall if wall['key'] not in duplicate_keys]
    result['ledProfileLength'] = driver(sum(parameter(e, 'Neovi_Length', 'length') for e in led_unique),
        [e['key'] for e in led_unique],
        f"SUM(typed Neovi_Length FT of {len(led_face)} face-based + {len(led_wall) - len(matched_walls)} distinct wall-based runs); {len(matched_walls)} spatial duplicates excluded")
    result['ledProfileRawSum'] = driver(sum(parameter(e, 'Neovi_Length', 'length') for e in led_face + led_wall),
        [e['key'] for e in led_face + led_wall],
        'Raw LED family length before spatial duplicate exclusion; comparison only')
    return result


def load_rules():
    general = json.loads((ROOT / 'config/planning-allowances.json').read_text())['rules']
    overrides = json.loads((ROOT / 'config/monroe-planning-overrides.json').read_text())['groups']
    rules = {key: {'terms': [{'driver': rule['driver'], 'rate': rule['rate']}],
                    'basis': rule['assumption'], 'source': 'general planning allowance'}
             for key, rule in general.items()}
    override_lines = set()
    for group in overrides:
        terms = group.get('terms', [{'driver': group.get('driver'), 'rate': group.get('rate')}])
        for line in group['lines']:
            if line in override_lines or (line in rules and not (group.get('replaceGeneral') and line in general)):
                raise ValueError('Duplicate Monroe planning rule: ' + line)
            override_lines.add(line)
            rules[line] = {'terms': terms, 'basis': group['basis'],
                           'source': 'Monroe planning override',
                           'conditionalZero': group.get('conditionalZero', False)}
    return rules


def up(value, step):
    if step <= 0:
        raise ValueError('Quantity increment must be positive')
    return round(math.ceil((value - 1e-10) / step) * step, 8)


def format_number(value):
    return f'{value:,.6f}'.rstrip('0').rstrip('.')


def fastener_metrics(item, drivers):
    lid = item['lineId']
    if lid not in FASTENER_BENCHMARKS:
        return None
    primary, unit, area = FASTENER_BENCHMARKS[lid]
    denominator = drivers[primary]['value']
    livable = drivers['floorArea']['value']
    if denominator <= 0 or livable <= 0 or (area and drivers[area]['value'] <= 0):
        raise ValueError('Fastener benchmark has zero denominator: ' + lid)
    quantity = item['quantity']
    return {
        'quantityExcludesSpares': quantity,
        'primaryDriver': primary,
        'primaryDriverValue': denominator,
        'primaryDriverUnit': unit,
        'averagePerPrimaryDriver': quantity / denominator,
        'areaDriver': area,
        'areaDriverValue': drivers[area]['value'] if area else None,
        'areaDriverUnit': AREA_LABELS[area] if area else None,
        'averagePerApplicableSqft': quantity / drivers[area]['value'] if area else None,
        'averagePerLivableSqft': quantity / livable,
    }


def item_average_metrics(item, drivers, rule=None):
    """Expose an observed average for every defined value; keep sizing basis explicit."""
    if item['basis'] in ('PLANNING_PLACEHOLDER', 'PLANNING_CONDITIONAL_ZERO'):
        return {'quantityExcludesSpares': item['quantity'], 'primaryDriver': None,
                'primaryDriverValue': None, 'primaryDriverUnit': None,
                'averagePerPrimaryDriver': None, 'areaDriver': None,
                'areaDriverValue': None, 'areaDriverUnit': None,
                'averagePerApplicableSqft': None, 'averagePerLivableSqft': None,
                'meaning': 'Undefined item or alternate-system quantity; zero is not an average usage rate'}
    special = fastener_metrics(item, drivers)
    if special:
        special['meaning'] = 'Rounded project quantity divided by the named model driver; planning comparison'
        return special
    terms = rule['terms'] if rule else []
    primary = terms[0]['driver'] if len(terms) == 1 else None
    denominator = drivers[primary]['value'] if primary else None
    if denominator is not None and denominator <= 0:
        raise ValueError('Item average has zero driver: ' + item['lineId'])
    area = primary if primary in AREA_LABELS else None
    return {
        'quantityExcludesSpares': item['quantity'],
        'primaryDriver': primary,
        'primaryDriverValue': denominator,
        'primaryDriverUnit': AREA_LABELS.get(primary, primary),
        'averagePerPrimaryDriver': item['quantity'] / denominator if primary else None,
        'areaDriver': area,
        'areaDriverValue': denominator if area else None,
        'areaDriverUnit': AREA_LABELS.get(area),
        'averagePerApplicableSqft': item['quantity'] / denominator if area else None,
        'averagePerLivableSqft': item['quantity'] / drivers['floorArea']['value'],
        'meaning': ('Project allowance normalized for comparison; do not size purchases by floor area'
                    if primary == 'project' else
                    'Model or fixed quantity normalized for comparison; source formula remains controlling'
                    if not rule else
                    'Rounded project quantity divided by the named model driver; planning comparison'),
    }


def estimate(line, rule, drivers):
    parts, refs = [], []
    raw = 0
    for term in rule['terms']:
        name, rate = term['driver'], term['rate']
        if name not in drivers or not isinstance(rate, (int, float)) or rate < 0 or not math.isfinite(rate):
            raise ValueError(f"Invalid planning rule for {line['lineId']}: {term}")
        value = drivers[name]['value']
        raw += value * rate
        parts.append(f"{format_number(value)} {name} x {format_number(rate)} {line['unit']}/{name}")
        refs += drivers[name]['references']
    quantity = up(raw, line['quantityIncrement'])
    return quantity, f"ceil_to_{format_number(line['quantityIncrement'])}({' + '.join(parts)}) = {format_number(quantity)} {line['unit']}", sorted(set(refs))


def story_allocation(rule, drivers, quantity, increment):
    names = [term['driver'] for term in rule['terms']]
    if names == ['floorArea']:
        rate = rule['terms'][0]['rate']
        raw = [drivers[name]['value'] * rate for name in ('firstStoryArea', 'secondStoryArea')]
    elif names == ['wallLength']:
        rate = rule['terms'][0]['rate']
        raw = [drivers[name]['value'] * rate for name in ('firstStoryWallLength', 'secondStoryWallLength')]
    elif names in (['firstStoryWallLength', 'secondStoryWallLength'],
                   ['firstStoryArea', 'secondStoryArea']):
        raw = [drivers[term['driver']]['value'] * term['rate'] for term in rule['terms']]
    else:
        return None
    if quantity <= increment and all(value > 0 for value in raw):
        return None  # A single whole unit cannot meaningfully be assigned to both stories.
    whole = [math.floor(value / increment + 1e-10) for value in raw]
    remaining = round(quantity / increment) - sum(whole)
    if remaining not in (0, 1, 2):
        raise ValueError('Story allocation does not reconcile')
    fractions = [value / increment - whole[i] for i, value in enumerate(raw)]
    for index in sorted(range(2), key=lambda i: fractions[i], reverse=True)[:remaining]:
        whole[index] += 1
    result = {level: {'raw': value, 'quantity': round(whole[i] * increment, 8)}
              for i, (level, value) in enumerate(zip(('FIRST FLOOR', 'SECOND FLOOR'), raw))}
    if not math.isclose(sum(row['quantity'] for row in result.values()), quantity, abs_tol=1e-8):
        raise ValueError('Allocated story quantities do not sum to project quantity')
    return result


def markdown(report):
    d = report['drivers']
    by_id = {item['lineId']: item for item in report['items']}
    lines = [
        '# Monroe Site BOM | Model quantities and planning formulas', '',
        f"Source: `{report['source']}`", '',
        f"Catalog rows: **{len(report['items'])}**. Model-linked or fixed catalog quantities: **{report['summary']['modelOrFixed']}**. "
        f"Planning estimate: **{report['summary']['planning']}**. Conditional zero: **{report['summary']['conditionalZero']}**. "
        f"Undefined placeholders: **{report['summary']['placeholderZero']}**.", '',
        '## Measurement and estimating drivers', '',
        '| Driver | Value | How calculated |', '|---|---:|---|',
    ]
    for name in ['firstStoryGrossArea', 'firstStoryArea', 'secondStoryArea', 'floorArea',
                 'firstStoryWallLength', 'secondStoryWallLength',
                 'firstStoryInteriorWallLength', 'secondStoryInteriorWallLength',
                 'firstStoryExteriorWallLength', 'secondStoryExteriorWallLength',
                 'interiorWallLength', 'exteriorWallLength', 'garageWallLength',
                 'nonGarageExteriorWallLength', 'interiorWallGrossFaceArea',
                 'exteriorWallGrossFaceArea', 'garageWallGrossFaceArea',
                 'nonGarageExteriorWallGrossFaceArea',
                 'interiorWallNetFaceAreaProxy', 'exteriorWallNetFaceAreaProxy',
                 'garageWallNetFaceAreaProxy', 'nonGarageExteriorWallNetFaceAreaProxy',
                 'trussFinishBoardArea',
                 'garageArea', 'garageRoomPerimeter', 'wetRoomArea', 'dryFloorArea',
                 'roofProxyArea', 'gutterLength',
                 'floorClipFastenerPositions',
                 'pileProxy', 'pileAreaBenchmark', 'trussCount', 'floorPlates', 'holdDowns',
                 'wallLength', 'exteriorLength', 'windows', 'firstStoryWindows', 'secondStoryWindows',
                 'doors', 'firstStoryDoors', 'secondStoryDoors', 'exteriorDoors',
                 'sinks', 'bathroomSinks', 'toilets', 'toiletCutouts', 'indoorUnits', 'fanCount', 'shadeCount',
                 'operableWindows', 'fixedWindows', 'smartControls',
                 'ledProfileLength', 'ledProfileRawSum', 'windowTrimLength',
                 'outlets', 'standardOutlets', 'highAmp30', 'highAmp50',
                 'lightAndFanPositions', 'batteryUnits',
                 'solarPanels', 'hssBeams']:
        value = d.get(name)
        if value:
            lines.append(f"| {name} | {format_number(value['value'])} | {value.get('description', 'Model-derived planning driver; see source element keys in JSON')} |")
    first_audit = report['storyAreaAudit']['FIRST FLOOR']
    lines += ['',
              f"The two first-story takeoff meshes overlap by {format_number(first_audit['overlapSqft'])} SQFT. "
              f"Their XY union is {format_number(first_audit['areaSqft'])} SQFT; "
              f"{format_number(first_audit['garageOverlapSqft'])} SQFT also overlaps the modeled garage room. "
              f"The first-story livable driver is therefore {format_number(d['firstStoryArea']['value'])} SQFT. "
              'The second-story mesh is independent. Using the raw sum would count overlapping floor area twice.', '',
              'The roof sheathing area is measured from typed roof elements but serves as a planning proxy for panel coverage. '
              'Linked U saddles provide pile-position proxies; the retired pile-cap family does not confirm the helical pile schedule. '
              'Sink and AC drivers also rely on specified model families. Independent estimates for components in one assembly '
              'can overlap; reconcile them before buying.', '',
              '## Wall runs and board planning', '',
              'Wall lengths use host stud walls with a typed Length, counted once. Garage-labeled stud walls are a subset of '
              'the model\'s exterior Function class. Gross face area is each wall length multiplied by model height. '
              'The net-area proxy uses typed wall Area after openings where present, then gross area for the one missing '
              'value. Both are one-face areas; site and factory installation scope is still unverified.', '',
              '| Wall group | Modeled run FT | FT per livable SQFT | Gross one-face SQFT | Net one-face proxy SQFT |',
              '|---|---:|---:|---:|---:|',
              f"| Interior | {format_number(d['interiorWallLength']['value'])} | "
              f"{d['interiorWallLength']['value'] / d['floorArea']['value']:.4f} | "
              f"{format_number(d['interiorWallGrossFaceArea']['value'])} | "
              f"{format_number(d['interiorWallNetFaceAreaProxy']['value'])} |",
              f"| Exterior, including garage | {format_number(d['exteriorWallLength']['value'])} | "
              f"{d['exteriorWallLength']['value'] / d['floorArea']['value']:.4f} | "
              f"{format_number(d['exteriorWallGrossFaceArea']['value'])} | "
              f"{format_number(d['exteriorWallNetFaceAreaProxy']['value'])} |",
              f"| Garage stud walls, exterior subset | {format_number(d['garageWallLength']['value'])} | "
              f"{d['garageWallLength']['value'] / d['floorArea']['value']:.4f} | "
              f"{format_number(d['garageWallGrossFaceArea']['value'])} | "
              f"{format_number(d['garageWallNetFaceAreaProxy']['value'])} |",
              f"| Other exterior stud walls | {format_number(d['nonGarageExteriorWallLength']['value'])} | "
              f"{d['nonGarageExteriorWallLength']['value'] / d['floorArea']['value']:.4f} | "
              f"{format_number(d['nonGarageExteriorWallGrossFaceArea']['value'])} | "
              f"{format_number(d['nonGarageExteriorWallNetFaceAreaProxy']['value'])} |", '',
              f"The GARAGE room itself is {format_number(d['garageArea']['value'])} SQFT with "
              f"{format_number(d['garageRoomPerimeter']['value'])} FT perimeter. "
              f"Its selected stud walls cover {format_number(d['garageWallLength']['value'])} FT; "
              f"that is {d['garageWallLength']['value'] / d['garageArea']['value']:.4f} garage-wall FT per garage SQFT. "
              'The difference includes the garage door and any other unselected boundaries, so it is not treated as a measured door width.', '',
              f"First-story interior/exterior runs are {format_number(d['firstStoryInteriorWallLength']['value'])} / "
              f"{format_number(d['firstStoryExteriorWallLength']['value'])} FT; second-story runs are "
              f"{format_number(d['secondStoryInteriorWallLength']['value'])} / "
              f"{format_number(d['secondStoryExteriorWallLength']['value'])} FT. "
              'Each story\'s FT-per-SQFT rate uses its net livable floor area.', '',
              '| Story | Interior wall FT | Interior FT / story SQFT | Exterior wall FT | Exterior FT / story SQFT |',
              '|---|---:|---:|---:|---:|',
              f"| First | {format_number(d['firstStoryInteriorWallLength']['value'])} | "
              f"{d['firstStoryInteriorWallLength']['value'] / d['firstStoryArea']['value']:.4f} | "
              f"{format_number(d['firstStoryExteriorWallLength']['value'])} | "
              f"{d['firstStoryExteriorWallLength']['value'] / d['firstStoryArea']['value']:.4f} |",
              f"| Second | {format_number(d['secondStoryInteriorWallLength']['value'])} | "
              f"{d['secondStoryInteriorWallLength']['value'] / d['secondStoryArea']['value']:.4f} | "
              f"{format_number(d['secondStoryExteriorWallLength']['value'])} | "
              f"{d['secondStoryExteriorWallLength']['value'] / d['secondStoryArea']['value']:.4f} |", '',
              f"PAN-036 site wall CB = ceil({format_number(d['exteriorWallNetFaceAreaProxy']['value'])} net exterior-wall "
              f"SQFT x 10% assumed site coverage) = {format_number(by_id['PAN-036']['quantity'])} SQFT, or "
              f"{by_id['PAN-036']['averageMetrics']['averagePerLivableSqft']:.3f} SQFT per livable SQFT. "
              'FIN-107 concrete board uses a separate assumed 2-FT-high '
              f"strip: ceil({format_number(d['exteriorWallLength']['value'])} exterior-wall FT x 2 FT) = "
              f"{format_number(by_id['FIN-107']['quantity'])} SQFT. FIN-108 finish screws use the same "
              f"unrounded {format_number(d['trussFinishBoardArea']['value'])} SQFT band x 8 assumed screws/SQFT "
              f"= {format_number(by_id['FIN-108']['quantity'])} screws. "
              'These scopes may overlap and need a board schedule. PAN-040 is a truss-stage roof-board screw allowance.', '',
              '## Decisions that change the estimate most', '',
              f"- Foundation: {format_number(d['pileProxy']['value'])} linked U saddles are used as pile-position proxies. "
              f"An independent area-density benchmark is {format_number(d['pileAreaBenchmark']['value'])}. "
              'Confirm the pile and bracket schedule before using either for procurement; bedframe hardware follows the catalog pile-based rule.',
              f"- Floor connections: {format_number(d['floorPlates']['value'])} model plates are selected. "
              'The catalog currently rounds their base kit to a minimum of 250, while its rule note says 100 versus 250 needs confirmation. '
              f"The linked floor clips also contain {format_number(d['floorClipFastenerPositions']['value'])} typed fastener positions "
              'whose screw type and site/factory scope are unspecified; they are not silently added to PAN-006.',
              f"- Roof: {format_number(d['roofProxyArea']['value'])} SQFT of typed sheathing is the panel-area proxy. "
              f"Truss screws use {format_number(d['trussCount']['value'])} linked truss labels x 8 assumed bearing screws, "
              'separate from roof-panel screws. Truss-stage board screws assume 10% site board coverage of roof area '
              'and ten screws per covered SQFT. Confirm the roof-panel assembly, purlin layout, slopes and fastening schedules.',
              f"- LED profiles: the raw family sum is {format_number(d['ledProfileRawSum']['value'])} FT and the "
              f"spatially reconciled estimate is {format_number(d['ledProfileLength']['value'])} FT. "
              'Confirm profile types and any remaining separate parallel runs.',
              f"- HVAC: {format_number(d['indoorUnits']['value'])} wall-mounted all-in-one units are modeled. "
              'Branch box, refrigerant lines and outdoor-unit power are conditional zero in this scenario; their rows state the split-system fallback.',
              f"- Electrical: {format_number(d['outlets']['value'])} modeled outlet-cover equivalents include quad and stacked boxes. "
              'The six high-amperage positions split into three 30-AMP and three 50-AMP outlets. '
              'The breaker count groups modeled outlets, lighting/fans, AC, water heater, battery and solar as a planning circuit proxy; '
              'no circuit schedule is modeled. Cable and fitting lengths are budget routes, and the 50-AMP connector product is undefined.',
              f"- Openings and plumbing: {format_number(d['operableWindows']['value'])} operable and "
              f"{format_number(d['fixedWindows']['value'])} fixed windows are modeled; only operable windows drive screen/handle allowances. "
              f"{format_number(d['toiletCutouts']['value'])} toilet rough-in cutouts versus "
              f"{format_number(d['toilets']['value'])} toilet fixtures require location reconciliation.",
              f"- Gutter and fire protection: {format_number(d['gutterLength']['value'])} FT of gutter is modeled; "
              f"the {format_number(d['exteriorLength']['value'])} FT exterior-wall run is only a fascia/soffit and fastener proxy. "
              'No sprinkler-head instances are modeled, so sprinkler quantities are planning allowances pending a fire-protection design.',
              '- Assemblies and tools: the fire riser and fire-riser assembly may be one purchase; sand/leveling and self-leveling compound may be alternate methods. Reusable tools need an inventory check.', '',
              '## Screw and fastener benchmarks', '',
              'Each average below is the rounded project quantity divided by the named model driver. '
              'The applicable area rate uses roof sheathing, garage room or livable floor area when that area fits the item. '
              f"The final column divides by {format_number(d['floorArea']['value'])} livable SQFT for a common comparison. "
              'These are planning averages, not counted fasteners or an engineered fastening schedule. '
              'Quantities exclude spares; the exact takeoff formula and assumption are in the item table below.', '',
              '| ID and item | Project quantity | Average per calculation driver | Applicable area rate | Per livable SQFT |',
              '|---|---:|---:|---:|---:|']
    for row in report['items']:
        metrics = row.get('averageMetrics')
        if row['lineId'] in FASTENER_BENCHMARKS:
            label = row['description'].replace('|', '\\|')
            area_rate = (f"{metrics['averagePerApplicableSqft']:.3f} / {metrics['areaDriverUnit']}"
                         if metrics['areaDriver'] else 'N/A')
            lines.append(f"| {row['lineId']} {label} | "
                         f"{format_number(row['quantity'])} | "
                         f"{metrics['averagePerPrimaryDriver']:.3f} / {metrics['primaryDriverUnit']} | "
                         f"{area_rate} | {metrics['averagePerLivableSqft']:.3f} |")
    board = next(item for item in report['items'] if item['lineId'] == 'PAN-040')
    wall = next(item for item in report['items'] if item['lineId'] == 'PAN-009')
    truss = next(item for item in report['items'] if item['lineId'] == 'PAN-016')
    lines += ['',
              f"PAN-016 truss screws = ceil({format_number(d['trussCount']['value'])} linked trusses x "
              '2 assumed bearing connections/truss x 4 screws/connection) = '
              f"{format_number(truss['quantity'])}. The implied roof-area average is "
              f"{format_number(truss['quantity'])} / {format_number(d['roofProxyArea']['value'])} "
              f"= {truss['averageMetrics']['averagePerApplicableSqft']:.6f} screws per roof SQFT. "
              'For an early project with only roof area, ceil(roof SQFT x this rate) is a proxy; '
              'when truss count is available, the connection formula controls. Confirm actual bearings and the engineered screw schedule.', '',
              f"PAN-040 truss-stage board screws = ceil({format_number(d['roofProxyArea']['value'])} modeled roof SQFT "
              f"x 10% assumed site board coverage x 10 screws per covered SQFT) = "
              f"{format_number(board['quantity'])} screws. This roof-board allowance is separate from "
              'PAN-036 wall CB and PAN-021 roof-panel screws.', '',
              f"PAN-009 wall screws = ceil(({format_number(d['firstStoryWallLength']['value'])} first-story wall FT "
              f"+ {format_number(d['secondStoryWallLength']['value'])} second-story wall FT) x 4 screws/FT) "
              f"= {format_number(wall['quantity'])} screws, or {wall['averageMetrics']['averagePerLivableSqft']:.3f} per livable SQFT "
              'when normalized for comparison.', '',
              '## Story allocation where the model supports it', '',
              'Wall-run and floor-area planning rates are applied to each story driver. Door and window screws use '
              'each opening\'s modeled floor. Whole-unit rounding is distributed by the largest fractional remainder '
              'so the two stories add to the rounded project quantity. Area-based cable and fire-protection splits '
              'are budget allocations, not routed lengths or approved layouts.', '',
              '| ID and item | Unit | First story | Second story | Project | First-story / SQFT | Second-story / SQFT |',
              '|---|---|---:|---:|---:|---:|---:|']
    for item in report['items']:
        if 'storyAllocation' not in item:
            continue
        lid = item['lineId']
        first = item['storyAllocation']['FIRST FLOOR']['quantity']
        second = item['storyAllocation']['SECOND FLOOR']['quantity']
        label = item['description'].replace('|', '\\|')
        lines.append(f"| {lid} {label} | {item['unit']} | "
                     f"{format_number(first)} | {format_number(second)} | {format_number(item['quantity'])} | "
                     f"{first / d['firstStoryArea']['value']:.6f} | "
                     f"{second / d['secondStoryArea']['value']:.6f} |")
    lines += ['',
              '## Every catalog item', '',
              'Model quantities retain measured precision. Planning quantities and base kits use the catalog quantity increment. Spare and base kit are shown for review, '
              'but inventory, pack ordering and cost cannot be calculated from the model. Every defined item also has a '
              'quantity-per-livable-SQFT comparison; use the named driver and full formula for sizing. A project-only tool '
              'allowance divided by floor area is just a comparison, not a reusable purchasing rate.', '',
              '| Section | ID and item | Basis | Quantity | Spare / base kit | Average per primary driver | Per livable SQFT | Calculation and assumption |',
              '|---|---|---|---:|---:|---|---:|---|']
    for row in report['items']:
        item = row['description'].replace('|', '\\|') + (' (optional)' if row['optional'] else '')
        detail = (row['formula'] + '; ' + row['assumption']).replace('|', '\\|')
        metrics = row['averageMetrics']
        primary = (f"{format_number(metrics['averagePerPrimaryDriver'])} {row['unit']} / {metrics['primaryDriverUnit']}"
                   if metrics['primaryDriver'] and metrics['primaryDriver'] != 'project' else
                   'project allowance' if metrics['primaryDriver'] == 'project' else 'N/A')
        normalized = (f"{metrics['averagePerLivableSqft']:.6f} {row['unit']}/SQFT"
                      if metrics['averagePerLivableSqft'] is not None else 'N/A')
        lines.append(f"| {row['categorySection']} | {row['lineId']} {item} | {row['basis']} | "
                     f"{format_number(row['quantity'])} {row['unit']} | "
                     f"{format_number(row['spareQuantity'])} / {format_number(row['baseKitQuantity'])} {row['unit']} | "
                     f"{primary} | {normalized} | {detail} |")
    lines += ['', '## Quantity conventions', '',
              '- **Model quantity:** selected model elements or typed dimensions. Derived model allowances still require scope review.',
              '- **Confirmed standard:** a saved user-approved fixed project quantity.',
              '- **Catalog fixed allowance:** an existing fixed catalog number that still needs project approval.',
              '- **Planning estimate:** an editable rate applied to a model driver or explicit project assumption.',
              '- **Conditional zero:** a defined item is held at zero in the current model scenario; its alternate-system allowance is stated in the row.',
              '- **Planning placeholder:** zero only because the catalog item is undefined; it is not a measured zero.',
              '- Spare = round up(quantity × catalog spare percent, quantity increment). '
              'Base kit = round up(max(quantity + spare, minimum kit), quantity increment). '
              'Do not add pack rounding until item demand, inventory, extra quantities and product pack sizes are confirmed.', '',
              'Edit `config/planning-allowances.json` or `config/monroe-planning-overrides.json`, '
              'then rerun `python scripts/build-monroe-estimates.py` to change planning rates.', '']
    return '\n'.join(lines)


def main():
    rows = json.loads((DATA / 'monroe-takeoff-elements.json').read_text())
    manifest = json.loads((DATA / 'monroe-scan-manifest.json').read_text())
    source = Path(manifest['source'])
    stat = source.stat()
    if (stat.st_size, stat.st_mtime_ns) != (manifest['sourceBytes'], manifest['sourceMtimeNs']):
        raise ValueError('Monroe source changed; rerun scan-monroe-model.py')
    mapped, openings = map_model(rows)
    catalog = json.loads((DATA / 'catalog-lines.json').read_text())
    confirmed = json.loads((ROOT / 'config/confirmed-site-standards.json').read_text())
    rules = load_rules()
    if manifest.get('schema') != 'monroe-scan-5':
        raise ValueError('Rescan Monroe source with the current geometry audit')
    drivers = monroe_drivers(rows, mapped, openings, manifest['storyAreas'])
    known = {line['lineId'] for line in catalog}
    if set(rules) - known:
        raise ValueError('Planning rule for unknown catalog line: ' + str(set(rules) - known))
    items = []
    for line in catalog:
        lid = line['lineId']
        item = {
            'lineId': lid, 'catalogId': line['catalogId'], 'description': line['description'],
            'phase': line['phase'], 'categorySection': line['categorySection'],
            'categoryPath': line['categoryPath'], 'unit': line['unit'],
            'optional': line['optional'],
            'catalogTakeoffFormula': line.get('takeoffFormula', ''),
            'quantityIncrement': line['quantityIncrement'], 'sparePercent': line['sparePercent'],
            'minimumKitQty': line['minimumKitQty'], 'modelQuantity': None,
            'planningQuantity': None,
        }
        if lid in mapped:
            evidence = mapped[lid]
            item.update(basis=evidence.get('status', 'MODEL_MEASURED'),
                        quantity=evidence['value'],
                        modelQuantity=evidence['value'],
                        formula=f"{evidence['formula']} = {format_number(evidence['value'])} {line['unit']}",
                        assumption=evidence['description'] + '; verify installation scope and product inclusion',
                        references=evidence['references'])
        elif lid in confirmed:
            item.update(basis='CONFIRMED_STANDARD', quantity=line['fixedQty'],
                        modelQuantity=line['fixedQty'],
                        formula=f"{format_number(line['fixedQty'])} {line['unit']} per project",
                        assumption=confirmed[lid],
                        references=['config/confirmed-site-standards.json#' + lid])
        elif line['sourceMode'] == 'FIXED':
            item.update(basis='CATALOG_FIXED_ALLOWANCE', quantity=line['fixedQty'],
                        planningQuantity=line['fixedQty'],
                        formula=f"{format_number(line['fixedQty'])} {line['unit']} per project",
                        assumption='Existing catalog fixed allowance; project applicability and procurement need review',
                        references=['config/site-bom.template.json#' + lid])
        elif lid in rules:
            quantity, formula, refs = estimate(line, rules[lid], drivers)
            rule = rules[lid]
            basis = ('PLANNING_CONDITIONAL_ZERO' if rule.get('conditionalZero') else
                     'PLANNING_PLACEHOLDER' if quantity == 0 and all(t['rate'] == 0 for t in rule['terms']) else
                     'PLANNING_ESTIMATE')
            item.update(basis=basis, quantity=quantity, planningQuantity=quantity,
                        formula=formula, assumption=rule['basis'], references=refs,
                        planningRuleSource=rule['source'])
            allocation = story_allocation(rule, drivers, quantity, line['quantityIncrement'])
            if allocation:
                item['storyAllocation'] = allocation
            if lid in ('FIN-084', 'FIN-088'):
                plural = 'Doors' if lid == 'FIN-084' else 'Windows'
                if len(rule['terms']) != 1 or rule['terms'][0]['driver'] != plural.lower() or rule['terms'][0]['rate'] != 8:
                    raise ValueError('Opening screw rule changed; revise story allocation: ' + lid)
                item['storyAllocation'] = {
                    level: {'raw': drivers[name + plural]['value'] * 8,
                            'quantity': drivers[name + plural]['value'] * 8}
                    for level, name in [('FIRST FLOOR', 'firstStory'), ('SECOND FLOOR', 'secondStory')]
                }
                if sum(part['quantity'] for part in item['storyAllocation'].values()) != quantity:
                    raise ValueError('Opening screw story quantities do not reconcile: ' + lid)
        else:
            raise ValueError('No model quantity, fixed quantity or planning formula for ' + lid)
        item['spareQuantity'] = up(item['quantity'] * line['sparePercent'], line['quantityIncrement'])
        item['baseKitQuantity'] = up(max(item['quantity'] + item['spareQuantity'], line['minimumKitQty']),
                                     line['quantityIncrement'])
        active_rule = rules.get(lid) if item['basis'].startswith('PLANNING_') else None
        item['averageMetrics'] = item_average_metrics(item, drivers, active_rule)
        items.append(item)
    count = Counter(item['basis'] for item in items)
    planning_statuses = {'PLANNING_ESTIMATE', 'PLANNING_PLACEHOLDER', 'PLANNING_CONDITIONAL_ZERO'}
    summary = {'byBasis': dict(count),
               'modelOrFixed': sum(v for k, v in count.items() if k not in planning_statuses),
               'planning': count['PLANNING_ESTIMATE'],
               'conditionalZero': count['PLANNING_CONDITIONAL_ZERO'],
               'placeholderZero': count['PLANNING_PLACEHOLDER']}
    report = {'source': str(source), 'sourceBytes': stat.st_size,
              'sourceMtimeNs': stat.st_mtime_ns, 'elementsScanned': manifest['elementsScanned'],
              'drivers': drivers, 'storyAreaAudit': manifest['storyAreas'],
              'summary': summary, 'items': items}
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'Monroe-Item-Formulas.json').write_text(json.dumps(report, indent=2))
    (DEST / 'Monroe-Item-Formulas.md').write_text(markdown(report), encoding='utf-8')
    print(f"Monroe: {len(items)} catalog rows; {summary}")


if __name__ == '__main__':
    main()
