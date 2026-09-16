"""Second audit pass: independently recompute Node results with decimal arithmetic."""
import json
import csv
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

D = lambda value: Decimal(str(value))


def rounded(value, step):
    return (value / D(step)).to_integral_value(rounding=ROUND_CEILING) * D(step)


def check(actual, expected, label):
    assert abs(D(actual) - expected) <= Decimal('0.00000001'), f'{label}: {actual} != {expected}'


def kit(line, value, fields):
    required = (D(line['fixedQty']) if line['sourceMode'] == 'FIXED' else
                D(fields['manualBaseQty']) if line['sourceMode'] == 'MANUAL' else
                value * D(line['multiplier']))
    spare = rounded(required * D(line['sparePercent']), line['quantityIncrement'])
    demand = rounded(max(required + spare + D(fields['manualExtra']), D(line['minimumKitQty'])), line['quantityIncrement'])
    return required, spare, demand


def buying(demand, item, on_hand, committed):
    net = max(D(0), demand + D(item['targetStockQty']) - D(on_hand) - D(committed))
    order = rounded(max(net, D(item['minimumOrderQty'])), item['packSize']) if net > 0 else D(0)
    return net, order


def main():
    folder = Path('outputs/NeoviBOM/_Internal/Model-Data')
    data = json.loads((folder / 'quantity-audit.json').read_text(encoding='utf-8'))
    catalog = {s['line']['lineId']: s['line'] for s in data['scenarios']}
    shipping_path = Path('outputs/NeoviBOM/01-Catalog/Neovi-Site-BOM-Checklist.csv')
    with shipping_path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        assert len(reader.fieldnames) == 23
        shipping = list(reader)
    assert len(shipping) == len(catalog)
    assert {row['Line ID'] for row in shipping} == set(catalog)
    for row in shipping:
        line = catalog[row['Line ID']]
        assert row['Quantity'] == '' and row['Project'] == '' and row['Revision'] == ''
        assert row['Item ID'] == line['itemId'] and row['Unit'] == line['unit']
        assert row['Catalog ID'] == line['catalogId'] and row['Category Path'] == ' > '.join(line['categoryPath'])
        assert row['Work Area'] == f"{line['categorySection']} {line['stage']}"
        assert row['Phase'] == line['phase'] and row['Stage'] == line['deliveryStage']
        assert all(step in row['Quantity Basis'] for step in ('Required =', 'Spare =', 'Kit =', 'Net =', 'Order =', 'Order once'))
        if line['sourceMode'] in ('DIRECT', 'CALCULATED') and not line.get('takeoffFormula'):
            assert f"in {line['inputUnit']}) x {line['multiplier']:g}" in row['Quantity Basis']
    for scenario in data['scenarios']:
        required, spare, demand = kit(scenario['line'], D(scenario['input']), scenario['fields'])
        for field, value in [('requiredQty', required), ('ruleSpareQty', spare), ('kitDemandQty', demand)]:
            check(scenario['result'][field], value, f"{scenario['line']['lineId']} {scenario['name']} {field}")
        demand *= scenario['occurrences']
        net, order = buying(demand, scenario['item'], scenario['purchase']['onHand'], scenario['purchase']['alreadyCommitted'])
        for field, value in [('totalKitDemand', demand), ('netNeed', net), ('orderQty', order), ('extendedCost', order * D('2.5'))]:
            check(scenario['purchase'][field], value, field)

    report = [
        '# NeoviBOM quantity audit — Santa Rita and Franklin', '',
        f"Two passes completed: source/formula review, then independent Python Decimal verification of {len(data['scenarios'])} scenarios across {data['catalogLines']} catalog lines and both project export tests.", '',
        f'The generated 23-column shipping CSV was also checked: {len(catalog)} unique matching Line IDs, permanent Catalog IDs, category paths, units, complete quantity explanations, and intentionally blank project/revision/quantities.', '',
        '## Corrections made', '',
        '- Source-unit explanations now use the actual input unit and distinguish it from the purchased unit.',
        '- Invalid pack sizes no longer default to one in the JavaScript calculator; the explanation identifies the missing pack size.',
        '- Invalid or missing unit costs remain unknown for positive orders; zero orders have zero extended cost, matching the sheet.',
        '- Nonnumeric inventory is flagged for review.',
        '- Rounding no longer drops very small positive demand or a real amount just above a pack boundary.', '',
        '## Export arithmetic tests', '',
        'The roof records below are test candidates, not an approved roof-material takeoff. Selection includes unique host New Construction roof instances with positive instance Area, no demolition or design option, and feet as the export coordinate unit. Linked roofs are excluded to prevent mixing source models. Different roof types/material layers may still overlap; that scope needs review.', '',
        '| Project | Elements scanned | Roof candidates | Source area (SQFT) | Rounded 10% spare | Kit demand (SQFT) | Test order: 100 on hand, 32 SQFT packs |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for project in data['projects']:
        value = sum((D(row['value']) for row in project['candidates']), D(0))
        required, spare, demand = kit(project['line'], value, {'manualBaseQty': 0, 'manualExtra': 0})
        for field, expected in [('requiredQty', required), ('ruleSpareQty', spare), ('kitDemandQty', demand)]:
            check(project['result'][field], expected, f"{project['project']} {field}")
        test_item = {**project['line'], 'targetStockQty': 0, 'minimumOrderQty': 0, 'packSize': 32}
        net, order = buying(demand, test_item, 100, 0)
        check(project['packScenario']['netNeed'], net, 'export net need')
        check(project['packScenario']['orderQty'], order, 'export order')
        check(project['packScenario']['extendedCost'], order * D('2.5'), 'export cost')
        catalog_net, catalog_order = buying(demand, project['line'], 0, 0)
        check(project['purchase']['netNeed'], catalog_net, 'catalog net')
        check(project['purchase']['orderQty'], catalog_order, 'catalog order')
        report.append(f"| {project['project']} | {project['elementCount']:,} | {project['candidateCount']} | {value:,.6f} | {spare:,} | {demand:,} | {order:,} |")
    report += ['', 'The 100 SQFT inventory, 32 SQFT pack, and $2.50/SQFT cost are explicit test assumptions. Actual vendor packs, costs, inventory and roof-material scope remain unapproved.', '', '## Source reconciliation', '']
    for project in data['projects']:
        report += [f"### {project['project']}", '',
                   f"Category **{project['line']['categorySection']} {project['line']['stage']}** | Phase: {project['line']['phase']} | Delivery stage: {project['line']['deliveryStage']} | Trade: {project['line']['category']}", '',
                   f"Source: `{project['source']}` ({project['bytes']:,} bytes), exported {project['exportedAt']}.", '',
                   f"Duplicate element keys: {project['duplicateElementKeys']}. BOM-tagged elements: {project['bomTaggedElements']}. Roof exclusions: {project['roofExclusions']}.", '',
                   '| Element key | Roof type | Level | Area (SQFT) |', '| --- | --- | --- | ---: |']
        for row in project['candidates']:
            report.append(f"| {row['key']} | {row['type'].replace('|', '/')} | {row['level']} | {row['value']:.8f} |")
        report += ['']
    report += ['## Remaining limits', '',
               f"{data['manualLines']} of {data['catalogLines']} catalog lines still require manual takeoffs. Neither export has BOM input tags, so these tests cannot establish connection counts, fastener counts, or a complete project buy list. No missing source quantity was inferred from a generic element count.", '',
               'CSV test inputs round-trip through the repository importer with units and unique source references. The 1375 synthetic scenarios cover zero input, fractional takeoffs and extras, inventory coverage, target stock/commitments/minimums/pack rounding, and shared-item aggregation.', '',
               'The generated Google Sheets script is rebuilt and checked locally. These are not live Google Sheets recalculation or visual-render tests. The operational master remains unchanged.', '']
    destination = folder / 'Santa-Rita-and-Franklin-Quantity-Audit.md'
    destination.write_text('\n'.join(report), encoding='utf-8')
    print(f"PASS: {len(data['scenarios'])} independent decimal scenarios; {len(data['projects'])} project export tests. Report: {destination}")


if __name__ == '__main__':
    main()
