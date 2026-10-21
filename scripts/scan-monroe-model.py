"""Retain physical Monroe elements needed for repeatable site BOM estimates."""
import json
from pathlib import Path

import ijson
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from model_takeoff_rules import eligible, parameter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('C:/Users/danie/Downloads/Neovi_206 Monroe Dr_00004_ShopDrawing.neovi-model.json')
OUT = ROOT / 'outputs/NeoviBOM/_Internal/Model-Data'
CATEGORIES = {
    'Structural Framing', 'Structural Connections', 'Bolts', 'Structural Columns',
    'Generic Models', 'Plumbing Fixtures', 'Plumbing Equipment', 'Electrical Equipment',
    'Mechanical Equipment', 'Casework', 'Gutters', 'Sprinklers', 'Pipes', 'Pipe Fittings',
    'Structural Foundations', 'Doors', 'Windows', 'Floors', 'Walls', 'Roofs', 'Ceilings',
    'Rooms', 'Electrical Fixtures', 'Lighting Fixtures', 'Electrical Circuits', 'Conduits',
    'Conduit Fittings', 'Cable Trays', 'Ducts', 'Duct Fittings', 'Duct Accessories',
    'Fascias', 'Soffits', 'Railings', 'Specialty Equipment', 'Furniture', 'Assemblies',
}


def projected_floor_polygon(element):
    """Union the floor mesh triangles in XY, dropping vertical/degenerate faces."""
    triangles = []
    for mesh in element.get('geometry', {}).get('meshes', []):
        positions, indices = mesh['positions'], mesh['indices']
        vertices = [(positions[i], positions[i + 1]) for i in range(0, len(positions), 3)]
        for offset in range(0, len(indices), 3):
            triangle = Polygon([vertices[indices[offset + i]] for i in range(3)])
            if triangle.area > 0.000001:
                if not triangle.is_valid:
                    raise ValueError('Invalid projected floor triangle: ' + element['key'])
                triangles.append(triangle)
    if not triangles:
        raise ValueError('No usable floor geometry: ' + element['key'])
    polygon = unary_union(triangles)
    typed_area = parameter(element, 'Area', 'area')
    if typed_area is None or abs(polygon.area - typed_area) > 0.01:
        raise ValueError(f"Floor mesh/typed area mismatch for {element['key']}: {polygon.area} vs {typed_area}")
    return polygon, typed_area


def story_area_audit(floors, garage_rooms):
    evidence = {}
    for level in ('FIRST FLOOR', 'SECOND FLOOR'):
        selected = [(e, projected_floor_polygon(e)) for e in floors if e.get('level') == level]
        if not selected:
            raise ValueError('Missing livable floor takeoff geometry for ' + level)
        projected_union = unary_union([shape for _, (shape, _) in selected])
        raw_sum = sum(area for _, (_, area) in selected)
        evidence[level] = {
            'areaSqft': projected_union.area,
            'rawElementAreaSumSqft': raw_sum,
            'overlapSqft': raw_sum - projected_union.area,
            'method': 'XY union of host New Construction livable floor takeoff meshes on this level',
            'elements': [{'key': e['key'], 'typedAreaSqft': area} for e, (_, area) in selected],
        }
        if level == 'FIRST FLOOR':
            if len(garage_rooms) != 1:
                raise ValueError('Expected one host garage room for livable-floor overlap audit')
            garage = garage_rooms[0]
            bounds = garage['bounds']
            garage_shape = box(bounds['min']['x'], bounds['min']['y'],
                               bounds['max']['x'], bounds['max']['y'])
            garage_area = parameter(garage, 'Area', 'area')
            if garage_area is None or abs(garage_shape.area - garage_area) > 0.01:
                raise ValueError('Garage room is not a rectangular room footprint')
            overlap = projected_union.intersection(garage_shape).area
            evidence[level]['garageRoomKey'] = garage['key']
            evidence[level]['garageOverlapSqft'] = overlap
            evidence[level]['netLivableAreaSqft'] = projected_union.area - overlap
            evidence[level]['method'] += '; subtract exact XY overlap with modeled garage room'
        else:
            evidence[level]['garageOverlapSqft'] = 0
            evidence[level]['netLivableAreaSqft'] = projected_union.area
    return evidence


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    stat = SOURCE.stat()
    manifest_path = OUT / 'monroe-scan-manifest.json'
    cache_path = OUT / 'monroe-takeoff-elements.json'
    if manifest_path.exists() and cache_path.exists():
        prior = json.loads(manifest_path.read_text())
        if (prior.get('schema') == 'monroe-scan-5' and
                (prior.get('sourceBytes'), prior.get('sourceMtimeNs')) == (stat.st_size, stat.st_mtime_ns)):
            print('Current Monroe scan cache:', cache_path)
            return
    found = {}
    livable_floors = []
    garage_rooms = []
    count = 0
    with SOURCE.open('rb') as stream:
        for element in ijson.items(stream, 'elements.item', use_float=True):
            count += 1
            if element.get('category') not in CATEGORIES or not eligible(element):
                continue
            if (element.get('sourceKey') == 'host' and element.get('category') == 'Floors' and
                    element.get('type') == 'Area Takeoff - Standard - Livable'):
                livable_floors.append(element)
            if (element.get('sourceKey') == 'host' and element.get('category') == 'Rooms' and
                    parameter(element, 'Name') == 'GARAGE'):
                garage_rooms.append(element)
            key = element['key']
            element = {k: v for k, v in element.items() if k not in ('geometry', 'boundingBox', 'mesh')}
            if key in found:
                if found[key] != element:
                    raise ValueError('Conflicting Monroe model element key: ' + key)
                continue
            found[key] = element
            if count % 50000 == 0:
                print(f'Scanned {count} elements; retained {len(found)}', flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    areas = story_area_audit(livable_floors, garage_rooms)
    cache_path.write_text(json.dumps(list(found.values())))
    manifest_path.write_text(json.dumps({
        'schema': 'monroe-scan-5',
        'source': str(SOURCE), 'sourceBytes': stat.st_size, 'sourceMtimeNs': stat.st_mtime_ns,
        'elementsScanned': count, 'retainedElements': len(found), 'categories': sorted(CATEGORIES),
        'storyAreas': areas,
    }, indent=2))
    print(f'Scanned {count} elements; retained {len(found)} in {cache_path}', flush=True)


if __name__ == '__main__':
    main()
