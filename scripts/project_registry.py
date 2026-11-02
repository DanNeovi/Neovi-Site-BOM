"""Private Drive registry and source discovery for local SiteBOM projects."""

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


SITE_ROOT = Path(os.environ.get('SITE_BOM_DRIVE_ROOT', 'G:/My Drive/SiteBOM'))
SITE_DRIVE_URL = 'https://drive.google.com/drive/folders/1De_DSfiGKjwYZo4jTm8FuVKu59tZFs1a'
SCHEMA = 'sitebom-project-registry-1'
OWNER = 'danielb@neovi.co'
NEOVIONE_EXPORTS = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Neovi/One/Models/Exports'
DOWNLOADS = Path.home() / 'Downloads'
MODEL_SUFFIX = '.neovi-model.json'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def slug(name):
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
        raise ValueError('Project name must contain 2 to 80 characters')
    normalized = unicodedata.normalize('NFKD', name.strip()).encode('ascii', 'ignore').decode().lower()
    result = re.sub(r'[^a-z0-9]+', '-', normalized).strip('-')[:64].strip('-')
    if not result or result in {'con', 'prn', 'aux', 'nul'} or re.fullmatch(r'(com|lpt)[1-9]', result):
        raise ValueError('Choose a project name with letters or numbers')
    return result


def model_header(path):
    """Read only the small JSON prefix; never load a multi-GB model into memory."""
    path = Path(path)
    try:
        with path.open('rb') as stream:
            prefix = stream.read(65536).decode('utf-8', 'replace')
        decoder = json.JSONDecoder()
        def field(name):
            match = re.search(r'"' + name + r'"\s*:', prefix)
            return decoder.raw_decode(prefix[match.end():].lstrip())[0] if match else {}
        project = field('project')
        cloud = field('cloudSource')
        if not isinstance(project, dict) or not str(project.get('projectName', '')).strip():
            return None
        return {'projectName': str(project['projectName']).strip(),
                'projectNumber': str(project.get('projectNumber', '')).strip(),
                'title': str(project.get('title', '')).strip(),
                'cloudProjectGuid': str(cloud.get('cloudProjectGuid', '')).strip() if isinstance(cloud, dict) else '',
                'cloudModelGuid': str(cloud.get('cloudModelGuid', '')).strip() if isinstance(cloud, dict) else ''}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def export_candidates():
    paths = list(DOWNLOADS.glob('*' + MODEL_SUFFIX))
    if NEOVIONE_EXPORTS.is_dir():
        paths += list(NEOVIONE_EXPORTS.rglob('*' + MODEL_SUFFIX))
    seen, result = set(), []
    for path in paths:
        if not path.is_file():
            continue
        resolved = str(path.resolve()).casefold()
        if resolved in seen:
            continue
        seen.add(resolved)
        header = model_header(path)
        if header is None:
            continue
        stat = path.stat()
        result.append({'ref': hashlib.sha256(resolved.encode()).hexdigest()[:20],
                       'path': str(path), 'fileName': path.name, 'bytes': stat.st_size,
                       'modifiedUtc': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                       **header})
    return sorted(result, key=lambda row: row['modifiedUtc'], reverse=True)


def find_export(ref):
    return next((row for row in export_candidates() if row['ref'] == ref), None)


def registry_path(root=SITE_ROOT):
    return Path(root) / '_Internal/project-registry.json'


def raw_dir(root, project):
    return Path(root) / '00-Raw' / ('Monroe' if project['id'] == 'monroe' else project['id'])


def output_dir(root, project):
    if project['id'] == 'monroe':
        return Path(root)
    return Path(root) / '02-Projects' / ('Franklin' if project['id'] == 'franklin' else
                                         'Santa-Rita' if project['id'] == 'santa-rita' else project['id'])


def audit_dir(root, project):
    return Path(root) / '04-Audits' / ('Monroe-AI' if project['id'] == 'monroe' else project['id'])


def ensure_folders(root, project):
    for folder in (raw_dir(root, project) / 'Model', raw_dir(root, project) / 'AI Core',
                   output_dir(root, project), audit_dir(root, project)):
        folder.mkdir(parents=True, exist_ok=True)


def seeds():
    return [
        {'id': 'monroe', 'name': 'Monroe', 'modelProjectName': '206 Monroe Drive',
         'projectNumber': '00004', 'processor': 'monroe', 'sourcePath': None,
         'driveFolderUrl': 'https://drive.google.com/drive/folders/16THLj6mzXs2A1D3Ioq3GBkQN5ML6bQgz'},
        {'id': 'franklin', 'name': 'Franklin', 'modelProjectName': '560 FRANKLIN ST.',
         'projectNumber': '00003', 'processor': 'intake', 'sourcePath': None},
        {'id': 'santa-rita', 'name': 'Santa Rita', 'modelProjectName': '898 Santa Rita Ave',
         'projectNumber': '00005', 'processor': 'intake', 'sourcePath': None},
    ]


def validate(document):
    if (not isinstance(document, dict) or document.get('schema') != SCHEMA or
            document.get('owner') != OWNER or not isinstance(document.get('projects'), list)):
        raise ValueError('Invalid private project registry')
    ids = set()
    for project in document['projects']:
        if not isinstance(project, dict) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', project.get('id', '')):
            raise ValueError('Invalid project ID in private registry')
        if (project['id'] in ids or project.get('processor') not in {'monroe', 'intake'} or
                not isinstance(project.get('name'), str) or not project['name'].strip() or
                not isinstance(project.get('modelProjectName'), str) or
                project.get('sourcePath') is not None and not isinstance(project['sourcePath'], str)):
            raise ValueError('Duplicate project or invalid processor in private registry')
        ids.add(project['id'])
    return document


def save(root, document):
    validate(document)
    path = registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    try:
        temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load(root=SITE_ROOT):
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f'Private Google Drive is unavailable: {root}')
    path = registry_path(root)
    if path.is_file():
        return validate(json.loads(path.read_text(encoding='utf-8')))
    document = {'schema': SCHEMA, 'owner': OWNER, 'createdAtUtc': utc_now(),
                'projects': seeds()}
    for project in document['projects']:
        ensure_folders(root, project)
    save(root, document)
    return document


def create(root, name, source_ref=None):
    root = Path(root)
    document = load(root)
    project_id = slug(name)
    if any(p['id'] == project_id or p['name'].casefold() == name.strip().casefold()
           for p in document['projects']):
        raise ValueError('A project with this name already exists')
    source = find_export(source_ref) if source_ref else None
    if source_ref and source is None:
        raise ValueError('Selected model export is no longer available')
    if source:
        ensure_model_not_assigned(document, source)
    project = {'id': project_id, 'name': name.strip(),
               'modelProjectName': source['projectName'] if source else '',
               'projectNumber': source['projectNumber'] if source else '',
               'cloudProjectGuid': source['cloudProjectGuid'] if source else '',
               'cloudModelGuid': source['cloudModelGuid'] if source else '',
               'processor': 'intake', 'sourcePath': source['path'] if source else None,
               'createdAtUtc': utc_now()}
    ensure_folders(root, project)
    document['projects'].append(project)
    save(root, document)
    return project


def get(root, project_id):
    return next((p for p in load(root)['projects'] if p['id'] == project_id), None)


def assigned_project(document, header, project_id=None):
    for other in document['projects']:
        if other['id'] == project_id or not other.get('modelProjectName'):
            continue
        if (other['modelProjectName'].casefold() == header['projectName'].casefold() and
                other.get('projectNumber', '') == header['projectNumber'] and
                (not other.get('cloudModelGuid') or not header.get('cloudModelGuid') or
                 other['cloudModelGuid'].casefold() == header['cloudModelGuid'].casefold())):
            return other
    return None


def ensure_model_not_assigned(document, header, project_id=None):
    other = assigned_project(document, header, project_id)
    if other is not None:
        raise ValueError(f'This model already belongs to the {other["name"]} SiteBOM project')


def connect_model(root, project_id, source_ref):
    document = load(root)
    project = next((p for p in document['projects'] if p['id'] == project_id), None)
    if project is None or project['processor'] != 'intake':
        raise ValueError('This project cannot use the generic model intake')
    source = find_export(source_ref)
    if source is None:
        raise ValueError('Selected model export is no longer available')
    ensure_model_not_assigned(document, source, project_id)
    if project['modelProjectName'] and (project['modelProjectName'].casefold() != source['projectName'].casefold() or
                                        project['projectNumber'] != source['projectNumber']):
        raise ValueError('Selected export belongs to a different Revit project')
    project.update(modelProjectName=source['projectName'], projectNumber=source['projectNumber'],
                   cloudProjectGuid=source['cloudProjectGuid'], cloudModelGuid=source['cloudModelGuid'],
                   sourcePath=source['path'])
    save(root, document)
    return project


def connect_uploaded_model(root, project_id, path):
    document = load(root)
    project = next((p for p in document['projects'] if p['id'] == project_id), None)
    if project is None or project['processor'] != 'intake':
        raise ValueError('This project cannot use the generic model intake')
    path = Path(path)
    if path.parent.resolve() != (raw_dir(root, project) / 'Model').resolve():
        raise ValueError('Uploaded model must be inside this project folder')
    header = model_header(path)
    if header is None:
        raise ValueError('The uploaded file is not a Neovi model export')
    ensure_model_not_assigned(document, header, project_id)
    if project['modelProjectName'] and (project['modelProjectName'].casefold() != header['projectName'].casefold() or
                                        project['projectNumber'] != header['projectNumber']):
        raise ValueError('The uploaded model belongs to a different Revit project')
    project.update(modelProjectName=header['projectName'], projectNumber=header['projectNumber'],
                   cloudProjectGuid=header['cloudProjectGuid'], cloudModelGuid=header['cloudModelGuid'],
                   sourcePath=str(path))
    save(root, document)
    return project
