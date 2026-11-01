"""Index every collected Monroe source and plan review-only Gemini page reads.

The source index is local/Drive evidence, not an approved purchasing takeoff.
Only current AI Core PDFs enter the default extraction plan. Older drawings and
duplicate forwards remain searchable for revision and conflict review.
"""

import argparse
import hashlib
import json
import math
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import fitz


DEFAULT_SOURCE = Path.home() / 'Downloads/Data for SiteBOM'
DEFAULT_OUTPUT = Path('G:/My Drive/SiteBOM/04-Audits/Monroe-AI')
CORE_SCOPES = {
    'Monroe SE sheets.pdf': 'Engineer structural schedules, pile counts and diameters, site foundation connections',
    'Neovi - Monroe_Steel Shop Drawings_REV 1 2025.12.18.pdf': 'Bedframe beams and site-installed pile-to-bedframe connection materials',
    'Neovi - Monroe_Fabrication Shop Drawing Package - Wall Panels 2026-08-26.pdf': 'Site-installed hold-down and L-angle connections, rod diameter and count',
    'Neovi - Monroe_Fabrication 2000 Series - Floor Cassettes 2026-08-19.pdf': 'Site-installed floor cassette connection materials and hardware',
}


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def text_layer_reliable(text):
    if not text.strip():
        return False
    controls = sum(ord(char) < 32 and char not in '\n\r\t' for char in text)
    return controls / max(len(text), 1) < 0.01


def file_identity(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size)


def index_sources(source_root, output_root):
    source_root = Path(source_root).resolve()
    if not (source_root / 'AI Core').is_dir():
        raise FileNotFoundError(f'Monroe AI Core is missing: {source_root}')
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    files, pages, hash_cache = [], [], {}
    for path in sorted(source_root.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        relative = path.relative_to(source_root).as_posix()
        stat = path.stat()
        identity = file_identity(path)
        if identity not in hash_cache:
            hash_cache[identity] = digest(path)
        entry = {'path': relative, 'bytes': stat.st_size, 'sha256': hash_cache[identity],
                 'suffix': path.suffix.lower(), 'role': 'current_core' if path.parent.name == 'AI Core'
                 else 'supporting_or_prior_revision' if path.parent.name in ('Email Structural', 'Local Structural')
                 else 'provenance_or_benchmark'}
        if path.suffix.lower() == '.pdf':
            with fitz.open(path) as document:
                entry['pages'] = len(document)
                entry['textLayerUnreliablePages'] = []
                for number, page in enumerate(document, 1):
                    # The structural PDF uses a custom font encoding. A sorted
                    # extraction fills pages with layout spaces and hides that
                    # corruption from the reliability check.
                    content = page.get_text()
                    reliable = text_layer_reliable(content)
                    if not reliable:
                        entry['textLayerUnreliablePages'].append(number)
                    pages.append({'path': relative, 'page': number, 'sourceSha256': entry['sha256'],
                                  'textLayerReliable': reliable, 'textSha256': hashlib.sha256(content.encode()).hexdigest(),
                                  'text': content})
        elif path.suffix.lower() == '.zip':
            with zipfile.ZipFile(path) as archive:
                entry['zipMembers'] = [member.filename for member in archive.infolist() if not member.is_dir()]
        elif path.suffix.lower() in ('.step', '.stp'):
            with path.open('rb') as stream:
                header = stream.read(4096).decode('utf-8', 'replace')
            match = re.search(r"FILE_NAME\s*\(\s*'([^']*)'", header, re.I)
            entry['stepFileName'] = match.group(1) if match else None
        elif path.suffix.lower() == '.json' and stat.st_size > 100_000_000:
            with path.open('rb') as stream:
                header = stream.read(4096).decode('utf-8', 'replace')
            for name in ('schemaVersion', 'exportedAtUtc', 'projectNumber', 'projectName'):
                match = re.search(r'"' + name + r'":"([^"]+)"', header)
                if match:
                    entry[name] = match.group(1)
        files.append(entry)
    duplicates = defaultdict(list)
    for entry in files:
        duplicates[entry['sha256']].append(entry['path'])
    manifest = {'schema': 'monroe-ai-source-index-1', 'project': 'Monroe',
                'generatedAtUtc': datetime.now(timezone.utc).isoformat(),
                'sourceRoot': str(source_root), 'files': files,
                'pdfCount': sum(entry['suffix'] == '.pdf' for entry in files),
                'pdfPageCount': sum(entry.get('pages', 0) for entry in files),
                'duplicateGroups': [paths for paths in duplicates.values() if len(paths) > 1]}
    (output_root / 'source-index.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    with (output_root / 'page-text.jsonl').open('w', encoding='utf-8') as stream:
        for page in pages:
            stream.write(json.dumps(page, ensure_ascii=False) + '\n')
    return manifest


def make_plan(manifest, model, repeats, daily_cap, include_prior=False):
    if repeats < 1 or daily_cap < 1:
        raise ValueError('Repeats and daily cap must be positive')
    chosen = [entry for entry in manifest['files'] if entry['suffix'] == '.pdf' and
              (include_prior or entry['role'] == 'current_core')]
    if not include_prior and {Path(entry['path']).name for entry in chosen} != set(CORE_SCOPES):
        raise ValueError('Current Monroe AI Core PDF set changed; review sources before extraction')
    sources = [{'path': entry['path'], 'sha256': entry['sha256'], 'pages': entry['pages'],
                'scope': CORE_SCOPES.get(Path(entry['path']).name,
                    'Classify quantities and dimensions by site or factory scope; keep revisions separate')}
               for entry in chosen]
    page_count = sum(entry['pages'] for entry in sources)
    return {'schema': 'monroe-ai-page-plan-1', 'project': 'Monroe', 'model': model,
            'repeatsPerPage': repeats, 'localDailyCap': daily_cap,
            'includesPriorRevisions': include_prior, 'pdfCount': len(sources),
            'pagesPerPass': page_count, 'plannedRequests': page_count * repeats,
            'minimumRunDaysAtCap': math.ceil(page_count * repeats / daily_cap),
            'sources': sources, 'status': 'review_only_not_purchasing_data'}


def planned_jobs(plan):
    """Cover each page once before starting the next repeat."""
    for repeat in range(1, plan['repeatsPerPage'] + 1):
        for source in plan['sources']:
            for page in range(1, source['pages'] + 1):
                yield {'path': source['path'], 'sourceSha256': source['sha256'],
                       'page': page, 'repeat': repeat, 'scope': source['scope']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('index', 'plan'))
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--model', default='gemini-3.5-flash-lite')
    parser.add_argument('--repeats', type=int, default=20)
    parser.add_argument('--daily-cap', type=int, default=20,
                        help='Conservative local safety cap, not a claim about Google quota')
    parser.add_argument('--include-prior', action='store_true', help='Include older revisions and duplicates')
    args = parser.parse_args()
    if args.command == 'index':
        result = index_sources(args.source_root, args.output_root)
        print(f"Indexed {len(result['files'])} Monroe files, {result['pdfCount']} PDFs, "
              f"{result['pdfPageCount']} PDF pages; {len(result['duplicateGroups'])} duplicate groups.")
    else:
        manifest = json.loads((args.output_root / 'source-index.json').read_text(encoding='utf-8'))
        result = make_plan(manifest, args.model, args.repeats, args.daily_cap, args.include_prior)
        (args.output_root / 'page-plan.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f"Planned {result['plannedRequests']} review-only requests over "
              f"{result['pagesPerPass']} pages and {result['pdfCount']} PDFs; "
              f"at least {result['minimumRunDaysAtCap']} run days at the local cap of {args.daily_cap}/day.")


if __name__ == '__main__':
    main()
