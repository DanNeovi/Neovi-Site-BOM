"""Stage verified Monroe source files in Daniel's private Google Drive folder.

The APS gateway only supplies a temporary Autodesk download. NeoviOne saves
that download locally; this bridge detects the local export and copies it to
the mounted private Drive before SiteBOM reads it.
"""

import hashlib
import os
import shutil
from pathlib import Path

from project_registry import model_header


DRIVE_ROOT = Path('G:/My Drive/SiteBOM/00-Raw/Monroe')
PRIVATE_FOLDER_URL = 'https://drive.google.com/drive/folders/16THLj6mzXs2A1D3Ioq3GBkQN5ML6bQgz'
MODEL_FOLDER = DRIVE_ROOT / 'Model'
CORE_FOLDER = DRIVE_ROOT / 'AI Core'
MODEL_NAME = 'Neovi_206 Monroe Dr_00004_ShopDrawing.neovi-model.json'
LOCAL_RAW = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Neovi/SiteBOM/Raw/Monroe'
NEOVIONE_EXPORTS = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Neovi/One/Models/Exports'
DOWNLOADS = Path.home() / 'Downloads'
DOCUMENTS = DOWNLOADS / 'Data for SiteBOM'
CORE_PDFS = (
    'Monroe SE sheets.pdf',
    'Neovi - Monroe_Steel Shop Drawings_REV 1 2025.12.18.pdf',
    'Neovi - Monroe_Fabrication Shop Drawing Package - Wall Panels 2026-08-26.pdf',
    'Neovi - Monroe_Fabrication 2000 Series - Floor Cassettes 2026-08-19.pdf',
)


def is_monroe_model(path):
    header = model_header(path)
    return bool(header and header['projectName'] == '206 Monroe Drive' and
                header['projectNumber'] == '00004')


def local_model_candidates():
    candidates = [LOCAL_RAW / MODEL_NAME, DOWNLOADS / MODEL_NAME,
                  DOCUMENTS / 'AI Core' / MODEL_NAME]
    if NEOVIONE_EXPORTS.is_dir():
        candidates += list(NEOVIONE_EXPORTS.rglob('*.neovi-model.json'))
    return [path for path in candidates if path.is_file() and is_monroe_model(path)]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def stage(source, target):
    """Copy a changed source atomically and verify the full copy before use."""
    source = Path(source)
    target = Path(target)
    if source.resolve() == target.resolve():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    source_stat = source.stat()
    if target.is_file():
        target_stat = target.stat()
        # Drive for desktop retains modification times to the millisecond.
        if (source_stat.st_size == target_stat.st_size and
                source_stat.st_mtime_ns // 1_000_000 == target_stat.st_mtime_ns // 1_000_000):
            return False
        if target_stat.st_mtime_ns > source_stat.st_mtime_ns + 1_000_000:
            return False  # A newer edit in the private Drive is authoritative.
    temporary = target.with_name(target.name + '.partial')
    try:
        if temporary.exists():
            temporary.unlink()
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != source_stat.st_size or digest(temporary) != digest(source):
            raise IOError(f'Private Drive copy did not verify: {source}')
        if source.stat().st_size != source_stat.st_size or source.stat().st_mtime_ns != source_stat.st_mtime_ns:
            raise IOError(f'Source changed during private Drive copy: {source}')
        temporary.replace(target)
        return True
    finally:
        if temporary.exists():
            temporary.unlink()


def sync(model_override=None):
    if not DRIVE_ROOT.is_dir():
        raise FileNotFoundError(f'Private Google Drive folder unavailable: {DRIVE_ROOT}')
    existing = sorted(MODEL_FOLDER.glob('*.neovi-model.json'),
                      key=lambda path: path.stat().st_mtime_ns, reverse=True) if MODEL_FOLDER.is_dir() else []
    candidates = ([Path(model_override)] if model_override else local_model_candidates() + existing)
    candidates = [path for path in candidates if path.is_file() and is_monroe_model(path)]
    model = max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None
    if model is not None:
        target = MODEL_FOLDER / model.name
        if stage(model, target):
            print(f'Copied verified Monroe model to private Drive: {target}', flush=True)
    else:
        raise FileNotFoundError('No verified Monroe model in local sources or private Drive')
    for name in CORE_PDFS:
        source = DOCUMENTS / 'AI Core' / name
        destination = CORE_FOLDER / name
        if source.is_file():
            if stage(source, destination):
                print(f'Copied Monroe drawing to private Drive: {destination}', flush=True)
        elif not destination.is_file():
            raise FileNotFoundError(f'Missing Monroe AI Core PDF: {name}')
    return target
