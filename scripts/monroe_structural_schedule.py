"""Validated structural-schedule facts used by the Monroe planning report."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / 'config/monroe-helical-pile-schedule.json'
SOURCE_PDF = Path.home() / 'Downloads/Data for SiteBOM/AI Core/Monroe SE sheets.pdf'


def load_pile_schedule(path=SCHEDULE, source_pdf=SOURCE_PDF):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = data['rows']
    if data.get('project') != 'Monroe' or data.get('documentType') != 'helical_pile_schedule':
        raise ValueError('Wrong project or structural schedule type')
    if data.get('approvalStatus') != 'not_approved_for_purchase':
        raise ValueError('Schedule review status changed; review this integration')
    if not isinstance(rows, list) or not rows:
        raise ValueError('No pile schedule rows')
    ids = set()
    counts = Counter()
    for row in rows:
        pile_id, count, diameter = row['pileId'], row['count'], row['diameterIn']
        if (not re.fullmatch(r'HP-[0-9]+[a-z]', pile_id) or pile_id in ids or
                type(count) is not int or count <= 0 or
                not re.fullmatch(r'[0-9]+(?: [0-9]+/[0-9]+)?"', diameter)):
            raise ValueError(f'Invalid or duplicate pile row: {row}')
        ids.add(pile_id)
        counts[diameter] += count
    if sum(counts.values()) != data['totalPiles']:
        raise ValueError('Pile schedule row total disagrees with stated total')
    listed = {row['diameterIn']: row['count'] for row in data['byDiameter']}
    if len(listed) != len(data['byDiameter']) or dict(counts) != listed:
        raise ValueError('Pile diameter subtotal disagrees with schedule rows')
    digest = data.get('sourceSha256', '').lower()
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Missing source PDF SHA-256')
    if source_pdf and Path(source_pdf).is_file():
        with open(source_pdf, 'rb') as source:
            actual = hashlib.file_digest(source, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('Structural PDF no longer matches the extracted schedule')
    return data


def rod_lengths_by_diameter(connections, inches_per_connection=21):
    """Return proposed rod lengths for evidenced hold-down/angle connections.

    This does not infer a diameter or an angle count from generic model labels.
    """
    if type(inches_per_connection) is not int or inches_per_connection <= 0:
        raise ValueError('Invalid rod cut length')
    counts = Counter()
    seen = set()
    for row in connections:
        key, kind, diameter = row['sourceId'], row['kind'], row['diameterIn']
        if not key or key in seen or kind not in ('hold_down', 'l_angle') or not diameter:
            raise ValueError(f'Invalid or duplicate rod connection: {row}')
        seen.add(key)
        counts[diameter] += 1
    return {diameter: {'pieces': count, 'cutLengthIn': inches_per_connection,
                       'totalIn': count * inches_per_connection,
                       'totalFt': count * inches_per_connection / 12}
            for diameter, count in sorted(counts.items())}
