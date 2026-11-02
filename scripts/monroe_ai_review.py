"""Build a provenance-preserving review report; never publish AI candidates."""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from monroe_ai_sources import DEFAULT_OUTPUT


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / 'config/monroe-helical-pile-schedule.json'


def pile_check(document, schedule):
    expected = {row['pileId'].lower(): row for row in schedule['rows']}
    actual = {}
    duplicates = []
    for finding in document['result']['findings']:
        match = re.search(r'HP-\d+[a-z]', finding['item'], re.I)
        if match:
            pile_id = match.group().lower()
            if pile_id in actual:
                duplicates.append(pile_id)
            actual[pile_id] = finding
    if not actual:
        return None
    mismatches = []
    for pile_id, row in expected.items():
        got = actual.get(pile_id)
        if got is None:
            mismatches.append({'pileId': row['pileId'], 'issue': 'missing row'})
        elif got['quantity'] != row['count']:
            mismatches.append({'pileId': row['pileId'], 'issue': 'count mismatch',
                               'expected': row['count'], 'aiRead': got['quantity']})
        if got is not None:
            expected_size = re.search(r'\d+(?:\s+\d+/\d+)?', row['diameterIn'])
            actual_size = re.search(r'\d+(?:\s+\d+/\d+)?', str(got.get('size') or ''))
            if actual_size is None or actual_size.group() != expected_size.group():
                mismatches.append({'pileId': row['pileId'], 'issue': 'diameter mismatch',
                                   'expected': row['diameterIn'], 'aiRead': got.get('size')})
    for pile_id in actual.keys() - expected.keys():
        mismatches.append({'pileId': pile_id, 'issue': 'unexpected row'})
    for pile_id in duplicates:
        mismatches.append({'pileId': pile_id, 'issue': 'duplicate row'})
    return {'page': document['page'], 'repeat': document['repeat'],
            'aiTotal': sum(finding['quantity'] or 0 for finding in actual.values()),
            'referenceTotal': schedule['totalPiles'], 'mismatches': mismatches,
            'status': 'matches_reference_rows' if not mismatches else 'review_discrepancy'}


def build_report(output_root=DEFAULT_OUTPUT):
    output_root = Path(output_root)
    plan = json.loads((output_root / 'page-plan.json').read_text(encoding='utf-8'))
    schedule = json.loads(SCHEDULE.read_text(encoding='utf-8'))
    source = {item['path']: item for item in plan['sources']}
    rows, documents, pile_checks = [], [], []
    token_totals = Counter()
    page_runs = defaultdict(list)
    for path in sorted((output_root / 'extractions').glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        if (document.get('project') != 'Monroe' or document.get('reviewStatus') != 'candidate_only' or
                document.get('model') != plan['model'] or document.get('source') not in source or
                document.get('sourceSha256') != source[document['source']]['sha256']):
            raise ValueError(f'Extraction is outside the current source plan: {path}')
        documents.append(document)
        usage = document.get('usageMetadata') or {}
        for source_key, target_key in (('promptTokenCount', 'promptTokens'),
                                       ('candidatesTokenCount', 'outputTokens'),
                                       ('totalTokenCount', 'totalTokens')):
            count = usage.get(source_key)
            if isinstance(count, int) and count >= 0:
                token_totals[target_key] += count
        for detail in usage.get('promptTokensDetails', []):
            count = detail.get('tokenCount')
            if isinstance(count, int) and count >= 0:
                if detail.get('modality') == 'IMAGE':
                    token_totals['imageInputTokens'] += count
                elif detail.get('modality') == 'TEXT':
                    token_totals['textInputTokens'] += count
        page_runs[(document['source'], document['page'])].append(document)
        if document['source'].endswith('/Monroe SE sheets.pdf') and document['page'] == schedule['sourcePage']:
            check = pile_check(document, schedule)
            if check:
                pile_checks.append(check)
        for finding in document['result']['findings']:
            rows.append({'project': 'Monroe', 'source': document['source'],
                         'sourceSha256': document['sourceSha256'], 'page': document['page'],
                         'promptVersion': document.get('promptVersion', 1),
                         'sheet': document['result'].get('sheet'), 'revision': document['result'].get('revision'),
                         'repeat': document['repeat'], 'model': document['model'],
                         'item': finding['item'], 'category': finding['category'],
                         'quantity': finding['quantity'], 'unit': finding.get('unit'),
                         'size': finding.get('size'), 'installationScope': finding['installationScope'],
                         'evidence': finding['evidence'], 'notes': finding.get('notes'),
                         'reviewStatus': 'candidate_only'})
    disagreements = []
    for (name, page), runs in page_runs.items():
        fingerprints = [sorted(((str(f['item']).strip().casefold(), f.get('quantity'),
                                 str(f.get('size')).strip().casefold()) for f in run['result']['findings']),
                               key=lambda value: (value[0], str(value[1]), value[2]))
                        for run in runs]
        if len(runs) > 1 and any(fingerprint != fingerprints[0] for fingerprint in fingerprints[1:]):
            disagreements.append({'source': name, 'page': page,
                                  'repeats': [run['repeat'] for run in runs],
                                  'promptVersions': [run.get('promptVersion', 1) for run in runs],
                                  'findingCounts': [len(run['result']['findings']) for run in runs]})
    coverage = {name: {'pages': item['pages'], 'readAtLeastOnce': sum(
        (name, page) in page_runs for page in range(1, item['pages'] + 1))}
        for name, item in source.items()}
    report = {'schema': 'monroe-ai-review-1', 'project': 'Monroe',
              'status': 'candidate_only_no_live_bom_write',
              'sourceFiles': len(source), 'plannedPagesPerPass': plan['pagesPerPass'],
              'pagesReadAtLeastOnce': len(page_runs), 'completedRequests': len(documents),
              'plannedRequests': plan['plannedRequests'], 'candidateFindings': len(rows),
              'routinePassRequests': plan['pagesPerPass'],
              'routinePassRemaining': max(0, plan['pagesPerPass'] - len(page_runs)),
              'sourceCoverage': coverage,
              'tokenUsage': dict(token_totals),
              'promptVersions': dict(Counter(str(doc.get('promptVersion', 1)) for doc in documents)),
              'findingsWithQuantity': sum(row['quantity'] is not None for row in rows),
              'findingsWithoutQuantity': sum(row['quantity'] is None for row in rows),
              'installationScopeCounts': dict(Counter(row['installationScope'] for row in rows)),
              'pileScheduleChecks': sorted(pile_checks, key=lambda check: check['repeat']),
              'pagePassDisagreements': disagreements,
              'reviewInstructions': 'Verify source page, revision, scope, and quantities before any BOM change. Do not sum repeated views or AI passes.'}
    (output_root / 'review-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (output_root / 'candidate-findings.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=('project', 'source', 'sourceSha256', 'page', 'promptVersion', 'sheet',
            'revision', 'repeat', 'model', 'item', 'category', 'quantity', 'unit', 'size',
            'installationScope', 'evidence', 'notes', 'reviewStatus'))
        writer.writeheader()
        writer.writerows(rows)
    return report


if __name__ == '__main__':
    print(json.dumps(build_report(), indent=2))
