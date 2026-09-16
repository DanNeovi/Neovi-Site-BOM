"""Stream large Everything exports into a compact, auditable BOM evidence report."""
import collections
import json
import sys
from pathlib import Path

import ijson


def inspect(source):
    categories = collections.Counter()
    tagged = []
    samples = {}
    count = 0
    roof_areas = []
    roof_exclusions = collections.Counter()
    seen = set()
    duplicate_keys = 0
    with source.open('rb') as stream:
        metadata = {}
        for prefix, event, value in ijson.parse(stream, use_float=True):
            if prefix == 'elements' and event == 'start_array':
                break
            if event in ('string', 'number', 'boolean', 'null'):
                metadata[prefix] = value
    with source.open('rb') as stream:
        for element in ijson.items(stream, 'elements.item', use_float=True):
            count += 1
            category = element.get('category', '')
            categories[category] += 1
            parameters = element.get('parameters', [])
            key = element.get('key')
            duplicate = key in seen
            if duplicate:
                duplicate_keys += 1
            seen.add(key)
            bom = [p for p in parameters if p.get('name', '').startswith('BOM ')]
            evidence = {k: element.get(k) for k in ('key', 'sourceKey', 'name', 'category', 'type', 'level', 'phaseCreated', 'phaseDemolished', 'designOption', 'viewSpecific')}
            evidence['parameters'] = [p for p in parameters if p.get('name') in ('Area', 'Length', 'Count', 'Type Name', 'Function') or p in bom]
            if bom:
                tagged.append(evidence)
            if category in ('Roofs', 'Doors', 'Windows', 'Ceilings', 'Structural Connections') and len(samples.setdefault(category, [])) < 3:
                samples[category].append(evidence)
            if category == 'Roofs':
                areas = [p for p in parameters if p.get('name') == 'Area'
                         and p.get('scope') == 'instance' and p.get('hasValue')
                         and p.get('storageType') == 'Double'
                         and str(p.get('dataType', '')).startswith('autodesk.spec.aec:area-')]
                reason = ('duplicate key' if duplicate else 'missing key' if not key
                          else 'linked source' if element.get('sourceKey') != 'host'
                          else 'view specific' if element.get('viewSpecific')
                          else 'demolished' if element.get('phaseDemolished')
                          else 'design option' if element.get('designOption')
                          else 'not New Construction' if element.get('phaseCreated') != 'New Construction'
                          else 'missing or ambiguous instance area' if len(areas) != 1
                          else 'unsupported coordinate units' if metadata.get('coordinates.lengthUnit') != 'ft'
                          else '')
                value = areas[0].get('doubleValue') if len(areas) == 1 else None
                if not reason and (not isinstance(value, (int, float)) or value <= 0):
                    reason = 'nonpositive or invalid area'
                if reason:
                    roof_exclusions[reason] += 1
                else:
                    roof_areas.append({**{k: evidence[k] for k in evidence if k != 'parameters'},
                                       'value': value, 'unit': 'SQFT', 'parameterId': areas[0].get('parameterId'),
                                       'displayValue': areas[0].get('displayValue')})
    return {'source': str(source), 'bytes': source.stat().st_size, 'elementCount': count,
            'metadata': metadata, 'duplicateElementKeys': duplicate_keys,
            'categories': dict(categories), 'bomTaggedElements': tagged, 'samples': samples,
            'roofAreaTestCandidates': roof_areas, 'roofExclusions': dict(roof_exclusions),
            'testScope': 'All unique host New Construction roof instances with positive Area, no demolition or design option. Arithmetic test only: roof types and material layers have not been approved as a purchasing takeoff.'}


if __name__ == '__main__':
    source, destination = map(Path, sys.argv[1:3])
    report = inspect(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'source': source.name, 'elements': report['elementCount'], 'bomTagged': len(report['bomTaggedElements']), 'report': str(destination)}))
