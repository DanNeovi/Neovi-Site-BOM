"""A7.1 window operations keyed by scheduled Mark, independent of family names."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / 'config/monroe-window-schedule.json'
SOURCE_PDF = Path.home() / 'Downloads/Neovi_206 Monroe State Set 260325.pdf'


def load_window_schedule(path=SCHEDULE, source_pdf=SOURCE_PDF):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if (data.get('project'), data.get('documentType'), data.get('approvalStatus')) != (
            'Monroe', 'window_operation_schedule', 'not_approved_for_purchase'):
        raise ValueError('Wrong project, schedule type, or review status')
    rows = data.get('rows')
    if not isinstance(rows, list) or not rows:
        raise ValueError('No window schedule rows')
    marks = set()
    count = Counter()
    for row in rows:
        mark, type_mark, operation = row['mark'], row['typeMark'], row['operation']
        if (not re.fullmatch(r'\d{3}', mark) or mark in marks or
                not re.fullmatch(r'[A-Z]\d+', type_mark) or
                operation not in ('FIXED', 'TILT & TURN')):
            raise ValueError(f'Invalid or duplicate window schedule row: {row}')
        marks.add(mark)
        count[operation] += 1
    if (len(rows), count['FIXED'], count['TILT & TURN']) != (24, 5, 19):
        raise ValueError('A7.1 window operation totals changed')
    digest = data.get('sourceSha256', '').lower()
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Missing source PDF SHA-256')
    if source_pdf and Path(source_pdf).is_file():
        with open(source_pdf, 'rb') as source:
            actual = hashlib.file_digest(source, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('A7.1 source PDF changed after schedule transcription')
    return data


def classify_window_operations(windows, schedule):
    """Match every modeled opening by Mark and Type Mark to the reviewed A7.1 rows."""
    by_mark = {row['mark']: row for row in schedule['rows']}
    found = {}
    for element in windows:
        values = {p['name']: p.get('displayValue') for p in element.get('parameters', [])
                  if p.get('name') in ('Mark', 'Type Mark') and p.get('hasValue')}
        mark, type_mark = values.get('Mark'), values.get('Type Mark')
        if mark in found or mark not in by_mark:
            raise ValueError(f'Duplicate or unscheduled window mark: {mark}')
        scheduled = by_mark[mark]
        if type_mark != scheduled['typeMark']:
            raise ValueError(f'Window Type Mark differs from A7.1: {mark}')
        family = element.get('family', '')
        operation = scheduled['operation']
        if ((family == 'Neovi_WD_Fixed' and operation != 'FIXED') or
                (family.startswith('Neovi_WD_Tilt&Turn') and operation != 'TILT & TURN')):
            raise ValueError(f'Window family and A7.1 operation disagree: {mark}')
        found[mark] = element
    if set(found) != set(by_mark):
        raise ValueError('A7.1 window marks do not match the current model')
    fixed = [found[row['mark']] for row in schedule['rows'] if row['operation'] == 'FIXED']
    operable = [found[row['mark']] for row in schedule['rows'] if row['operation'] == 'TILT & TURN']
    return fixed, operable
