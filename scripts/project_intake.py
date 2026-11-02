"""Stage project models and report raw model coverage without inventing BOM quantities."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import ijson

from private_drive_sources import stage
from project_registry import (SITE_ROOT, audit_dir, export_candidates, model_header,
                              output_dir, raw_dir)


def signature(path):
    stat = path.stat()
    return {'bytes': stat.st_size, 'mtimeNs': stat.st_mtime_ns}


def matches(project, header):
    if not header or not project.get('modelProjectName'):
        return False
    if header['projectName'].casefold() != project['modelProjectName'].casefold():
        return False
    if project.get('projectNumber') and header['projectNumber'] != project['projectNumber']:
        return False
    if project.get('cloudModelGuid') and \
            header.get('cloudModelGuid', '').casefold() != project['cloudModelGuid'].casefold():
        return False
    return True


def candidate_models(root, project):
    folder = raw_dir(root, project) / 'Model'
    existing = list(folder.glob('*.neovi-model.json')) if folder.is_dir() else []
    if not project.get('sourcePath') and not existing:
        return []  # Existing reports do not implicitly authorize a multi-GB copy.
    paths = existing + [Path(row['path']) for row in export_candidates()]
    if project.get('sourcePath'):
        paths.append(Path(project['sourcePath']))
    found = {}
    for path in paths:
        if path.is_file() and matches(project, model_header(path)):
            found[str(path.resolve()).casefold()] = path
    return sorted(found.values(), key=lambda path: path.stat().st_mtime_ns, reverse=True)


def census(path, project):
    before = signature(path)
    category_counts = Counter()
    source_counts = Counter()
    count = 0
    with path.open('rb') as stream:
        for element in ijson.items(stream, 'elements.item', use_float=True):
            count += 1
            category_counts[str(element.get('category') or 'Unclassified')] += 1
            source_counts[str(element.get('sourceKey') or 'Unclassified')] += 1
    if signature(path) != before:
        raise RuntimeError('Model changed during source census; retry on next check')
    return {'schema': 'sitebom-project-model-census-1', 'projectId': project['id'],
            'model': str(path), 'modelSignature': before, 'modelHeader': model_header(path),
            'elements': count, 'categories': dict(sorted(category_counts.items())),
            'sources': dict(sorted(source_counts.items())),
            'generatedAtUtc': datetime.now(timezone.utc).isoformat(),
            'quantityStatus': 'raw_model_only_needs_project_rules'}


def process(root, project):
    if project['processor'] != 'intake':
        return None
    candidates = candidate_models(root, project)
    if not candidates:
        return None
    source = candidates[0]
    target = raw_dir(root, project) / 'Model' / source.name
    stage(source, target)
    summary_path = output_dir(root, project) / 'model-summary.json'
    try:
        current = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.is_file() else {}
    except (OSError, ValueError):
        current = {}
    if current.get('model') == str(target) and current.get('modelSignature') == signature(target):
        return current
    summary = census(target, project)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = summary_path.with_name(summary_path.name + '.tmp')
    try:
        temporary.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        temporary.replace(summary_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return summary


def state_path(root, project):
    return audit_dir(root, project) / 'intake-state.json'


def process_all(root=SITE_ROOT, projects=None):
    from project_registry import load
    projects = projects if projects is not None else load(root)['projects']
    errors = []
    for project in projects:
        if project['processor'] != 'intake':
            continue
        state = {'schema': 'sitebom-intake-state-1', 'projectId': project['id'],
                 'checkedAtUtc': datetime.now(timezone.utc).isoformat()}
        try:
            summary = process(root, project)
            state['status'] = 'model_indexed' if summary else 'waiting_for_model'
            state['elements'] = summary['elements'] if summary else None
        except Exception as error:
            state['status'] = 'error'
            state['error'] = str(error)
            errors.append((project['id'], error))
        path = state_path(root, project)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.tmp')
        try:
            temporary.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
    return errors
