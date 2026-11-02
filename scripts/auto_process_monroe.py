"""Process new Monroe raw exports and drawing files without publishing purchases.

Runs safely from Windows Task Scheduler. The Revit exporter atomically replaces
its model JSON; this job only recalculates when that published file changes.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(Path(sys.executable).with_name('python.exe')) if Path(sys.executable).name.lower() == 'pythonw.exe' else sys.executable
DRIVE = Path('G:/My Drive/SiteBOM')
STATE = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Neovi/SiteBOM/automation-state.json'
AUTO_MODEL = STATE.parent / 'Raw/Monroe/Neovi_206 Monroe Dr_00004_ShopDrawing.neovi-model.json'
LEGACY_MODEL = Path.home() / 'Downloads/Neovi_206 Monroe Dr_00004_ShopDrawing.neovi-model.json'
DOCUMENTS = Path.home() / 'Downloads/Data for SiteBOM'
CORE_PDFS = (
    'Monroe SE sheets.pdf',
    'Neovi - Monroe_Steel Shop Drawings_REV 1 2025.12.18.pdf',
    'Neovi - Monroe_Fabrication Shop Drawing Package - Wall Panels 2026-08-26.pdf',
    'Neovi - Monroe_Fabrication 2000 Series - Floor Cassettes 2026-08-19.pdf',
)
PIPELINE_FILES = (
    'config/site-bom.template.json', 'config/site-bom-checklist.json',
    'config/planning-allowances.json', 'config/monroe-planning-overrides.json',
    'config/monroe-window-schedule.json', 'config/monroe-helical-pile-schedule.json',
    'scripts/scan-monroe-model.py', 'scripts/model_takeoff_rules.py',
    'scripts/opening_takeoffs.py', 'scripts/build-monroe-estimates.py',
    'scripts/audit-monroe-values.py', 'scripts/export-data.mjs',
    'scripts/build-viewer.mjs',
)


def signature(path):
    stat = path.stat()
    return {'path': str(path.resolve()), 'bytes': stat.st_size, 'mtimeNs': stat.st_mtime_ns}


def source_signature(folder):
    files = sorted(path for path in folder.rglob('*') if path.is_file() and
                   '__pycache__' not in path.parts)
    if not files:
        raise FileNotFoundError(f'No Monroe source files in {folder}')
    return [{'path': str(path.relative_to(folder)), 'bytes': path.stat().st_size,
             'mtimeNs': path.stat().st_mtime_ns} for path in files]


def pipeline_digest():
    digest = hashlib.sha256()
    for relative in PIPELINE_FILES:
        digest.update(relative.encode('utf-8'))
        digest.update((ROOT / relative).read_bytes())
    return digest.hexdigest()


def verify_project(path):
    # The project header precedes the 1.97 GB element array.
    with path.open('rb') as stream:
        header = stream.read(16384).decode('utf-8', 'replace')
    if '"project":' not in header or '"projectName":"206 Monroe Drive"' not in header:
        raise ValueError(f'The selected raw model is not the Monroe export: {path}')


def run(*command, env=None):
    print('Running:', ' '.join(map(str, command)), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def write_state(value):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(STATE)


def process(model=None, force=False, index_drawings=True):
    if not DRIVE.is_dir():
        raise FileNotFoundError(f'Google Drive output is unavailable: {DRIVE}')
    source = Path(model) if model else AUTO_MODEL if AUTO_MODEL.is_file() else LEGACY_MODEL
    if not source.is_file():
        raise FileNotFoundError(f'No Monroe raw model export at {source}')
    verify_project(source)
    previous = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    status = {'schema': 'sitebom-automation-state-1', **previous}
    changed = []
    model_key = {**signature(source), 'pipelineSha256': pipeline_digest()}
    if force or previous.get('model') != model_key:
        env = {**os.environ, 'SITE_BOM_MONROE_MODEL': str(source)}
        scan_changed = force or (previous.get('model') or {}).get('pipelineSha256') != model_key['pipelineSha256']
        run(PYTHON, 'scripts/scan-monroe-model.py',
            *(['--force'] if scan_changed else []), env=env)
        run(PYTHON, 'scripts/build-monroe-estimates.py', env=env)
        if signature(source) != {key: model_key[key] for key in ('path', 'bytes', 'mtimeNs')}:
            raise RuntimeError('The raw model changed during processing; retry on the next run')
        run(PYTHON, 'scripts/audit-monroe-values.py', env=env)
        run('node', 'scripts/export-data.mjs', env=env)
        run('node', 'scripts/verify-data-exports.mjs', env=env)
        status['model'] = model_key
        status['modelProcessedAtUtc'] = datetime.now(timezone.utc).isoformat()
        write_state(status)
        changed.append('model quantities and G: exports')
    if index_drawings:
        core = DOCUMENTS / 'AI Core'
        if {path.name for path in core.glob('*.pdf')} != set(CORE_PDFS):
            raise ValueError('Monroe AI Core PDF set changed; review the source selection')
        pdf_key = source_signature(DOCUMENTS)
        if force or previous.get('drawings') != pdf_key:
            run(PYTHON, 'scripts/monroe_ai_sources.py', 'index')
            run(PYTHON, 'scripts/monroe_ai_sources.py', 'plan',
                '--repeats', '20', '--daily-cap', '20')
            status['drawings'] = pdf_key
            status['drawingsIndexedAtUtc'] = datetime.now(timezone.utc).isoformat()
            write_state(status)
            changed.append('current AI Core and older drawing index')
    print('Updated: ' + ', '.join(changed) if changed else 'Already current; no processing needed.')
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, help='Published Monroe raw model path')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--skip-drawing-index', action='store_true')
    args = parser.parse_args()
    process(args.model, args.force, not args.skip_drawing_index)


if __name__ == '__main__':
    main()
