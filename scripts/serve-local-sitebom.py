"""Host SiteBOM on this computer and process newly published raw files."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from auto_process_monroe import CORE_PDFS, DRIVE, STATE
from private_drive_sources import CORE_FOLDER, DRIVE_ROOT, MODEL_FOLDER, MODEL_NAME, PRIVATE_FOLDER_URL
from project_intake import state_path
from project_registry import (SITE_DRIVE_URL, SITE_ROOT, assigned_project, connect_model, connect_uploaded_model,
                              create, export_candidates, get, load, model_header,
                              output_dir, raw_dir)


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
DASHBOARD = ROOT / 'local-site/index.html'
PROJECT_PAGE = ROOT / 'local-site/project.html'
LOG = STATE.parent / 'automation.log'
worker_state_lock = threading.Lock()
registry_lock = threading.Lock()
upload_guard = threading.Lock()
uploads_in_progress = set()
worker = {'running': False, 'lastStartedUtc': None, 'lastFinishedUtc': None,
          'lastExitCode': None, 'lastError': None, 'rerunRequested': False}


def details(path):
    if not path.is_file():
        return {'path': str(path), 'exists': False}
    stat = path.stat()
    return {'path': str(path), 'exists': True, 'bytes': stat.st_size,
            'modifiedUtc': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()}


def status():
    try:
        saved = json.loads(STATE.read_text(encoding='utf-8')) if STATE.is_file() else {}
    except (OSError, ValueError):
        saved = {'error': 'Automation state could not be read'}
    models = sorted(MODEL_FOLDER.glob('*.neovi-model.json'),
                    key=lambda path: path.stat().st_mtime_ns, reverse=True) if MODEL_FOLDER.is_dir() else []
    model = models[0] if models else MODEL_FOLDER / MODEL_NAME
    core = CORE_FOLDER
    pdfs = [details(core / name) for name in CORE_PDFS]
    plan = DRIVE / '04-Audits/Monroe-AI/page-plan.json'
    return {'schema': 'sitebom-local-status-1', 'worker': dict(worker),
            'sourceModel': details(model), 'corePdfs': pdfs,
            'driveAvailable': DRIVE.is_dir(),
            'privateRawAvailable': DRIVE_ROOT.is_dir(),
            'privateRawFolderUrl': PRIVATE_FOLDER_URL,
            'driveExport': details(DRIVE / 'NeoviBOM.html'),
            'aiPlan': details(plan), 'automation': saved,
            'log': str(LOG), 'processingTrigger': 'upload_connect_or_manual'}


def project_status(project):
    raw = raw_dir(SITE_ROOT, project)
    models = sorted((raw / 'Model').glob('*.neovi-model.json'),
                    key=lambda path: path.stat().st_mtime_ns, reverse=True)
    pdfs = sorted((raw / 'AI Core').glob('*.pdf'))
    output = output_dir(SITE_ROOT, project)
    reports = sorted(path.name for path in output.iterdir() if path.is_file() and
                     path.suffix.lower() in {'.csv', '.pdf', '.json'}) if output.is_dir() else []
    summary_path = output / 'model-summary.json'
    try:
        summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.is_file() else None
    except (OSError, ValueError):
        summary = None
    intake_path = state_path(SITE_ROOT, project)
    try:
        intake = json.loads(intake_path.read_text(encoding='utf-8')) if intake_path.is_file() else None
    except (OSError, ValueError):
        intake = {'status': 'error', 'error': 'Intake state could not be read'}
    if project['id'] == 'monroe':
        reports = ['NeoviBOM.html', 'NeoviBOM.json', 'NeoviBOM.xlsx']
    return {'id': project['id'], 'name': project['name'], 'processor': project['processor'],
            'modelProjectName': project.get('modelProjectName') or None,
            'projectNumber': project.get('projectNumber') or None,
            'createdAtUtc': project.get('createdAtUtc'),
            'rawFolder': str(raw), 'outputFolder': str(output),
            'driveFolderUrl': project.get('driveFolderUrl'), 'siteDriveUrl': SITE_DRIVE_URL,
            'model': details(models[0]) if models else None,
            'pdfs': [details(path) for path in pdfs], 'reports': reports,
            'summary': summary, 'intake': intake,
            'quantityStatus': 'monroe_review_pipeline' if project['id'] == 'monroe' else
                              'project_rules_not_configured'}


def process_once():
    with worker_state_lock:
        if worker['running']:
            worker['rerunRequested'] = True
            return False
        worker['running'] = True
        worker['rerunRequested'] = False
    def work():
        worker.update(lastStartedUtc=datetime.now(timezone.utc).isoformat(), lastError=None)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        try:
            with LOG.open('a', encoding='utf-8') as log:
                log.write(f"\n[{worker['lastStartedUtc']}] Processing raw sources\n")
                log.flush()
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/auto_process_projects.py')],
                                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                        check=False)
                worker['lastExitCode'] = result.returncode
                if result.returncode:
                    worker['lastError'] = f'Processing exited with code {result.returncode}; see automation.log'
        except Exception as error:
            worker['lastExitCode'] = -1
            worker['lastError'] = str(error)
        finally:
            worker['lastFinishedUtc'] = datetime.now(timezone.utc).isoformat()
            with worker_state_lock:
                rerun = worker['rerunRequested']
                worker['running'] = False
                worker['rerunRequested'] = False
            if rerun:
                process_once()
    threading.Thread(target=work, daemon=True, name='sitebom-processor').start()
    return True


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def log_message(self, format, *args):
        # pythonw.exe has no console stderr when started at Windows sign-in.
        return

    def local_host_only(self):
        allowed = {f'127.0.0.1:{self.server.server_port}',
                   f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in allowed:
            self.send_error(403, 'Use the local SiteBOM address')
            return False
        return True

    def send_json(self, value, code=200):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_page(self, page):
        body = page.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def same_origin(self):
        host = self.headers.get('Host')
        return self.headers.get('Origin') == f'http://{host}'

    def do_GET(self):
        if not self.local_host_only():
            return
        path = unquote(urlsplit(self.path).path)
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        if path == '/api/status':
            self.send_json(status())
            return
        if path == '/api/projects':
            try:
                document = load(SITE_ROOT)
                self.send_json({'schema': document['schema'], 'owner': document['owner'],
                                'projects': [project_status(p) for p in document['projects']],
                                'worker': dict(worker), 'processingTrigger': 'upload_connect_or_manual'})
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_json({'error': str(error)}, 503)
            return
        if path == '/api/model-exports':
            try:
                document = load(SITE_ROOT)
                exports = export_candidates()
                for row in exports:
                    assigned = assigned_project(document, row)
                    row['assignedProjectId'] = assigned['id'] if assigned else None
                self.send_json({'exports': exports})
            except (OSError, ValueError) as error:
                self.send_json({'error': str(error)}, 503)
            return
        match = re.fullmatch(r'/api/projects/([a-z0-9][a-z0-9-]{0,63})', path)
        if match:
            project = get(SITE_ROOT, match.group(1))
            if project is None:
                self.send_error(404, 'Unknown project')
            else:
                payload = project_status(project)
                if project['id'] == 'monroe':
                    payload['monroe'] = status()
                self.send_json(payload)
            return
        if path == '/':
            self.path = '/dashboard'
            path = '/dashboard'
        if path == '/dashboard':
            self.send_page(DASHBOARD)
            return
        if re.fullmatch(r'/projects/[a-z0-9][a-z0-9-]{0,63}', path):
            if get(SITE_ROOT, path.rsplit('/', 1)[1]) is None:
                self.send_error(404, 'Unknown project')
            else:
                self.send_page(PROJECT_PAGE)
            return
        report = re.fullmatch(r'/projects/([a-z0-9][a-z0-9-]{0,63})/reports/([^/]+)', path)
        if report:
            project = get(SITE_ROOT, report.group(1))
            name = report.group(2)
            if (project is None or project['id'] == 'monroe' or
                    name not in project_status(project)['reports']):
                self.send_error(404, 'Unknown project report')
            else:
                self.directory = str(output_dir(SITE_ROOT, project))
                self.path = '/' + name
                super().do_GET()
            return
        if path.startswith('/bom/'):
            self.path = path[4:] or '/'
            return super().do_GET()
        if path == '/preview/NeoviBOM.html':
            self.directory = str(DRIVE)
            self.path = '/NeoviBOM.html'
            return super().do_GET()
        self.send_error(404, 'Unknown SiteBOM path')

    def do_POST(self):
        if not self.local_host_only():
            return
        if not self.same_origin():
            self.send_error(403, 'Use the local SiteBOM website')
            return
        path = unquote(urlsplit(self.path).path)
        if path == '/api/process':
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.send_error(415)
                return
            started = process_once()
            self.send_json({'started': started, 'queued': not started, 'running': worker['running']}, 202)
            return
        if path == '/api/projects':
            try:
                data = self.read_json()
                with registry_lock:
                    project = create(SITE_ROOT, data.get('name'), data.get('sourceRef'))
                if data.get('sourceRef'):
                    process_once()
                self.send_json(project_status(project), 201)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        match = re.fullmatch(r'/api/projects/([a-z0-9][a-z0-9-]{0,63})/model', path)
        if match:
            try:
                data = self.read_json()
                with registry_lock:
                    project = connect_model(SITE_ROOT, match.group(1), data.get('sourceRef'))
                process_once()
                self.send_json(project_status(project))
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        match = re.fullmatch(r'/api/projects/([a-z0-9][a-z0-9-]{0,63})/upload', path)
        if match:
            self.upload(match.group(1))
            return
        self.send_error(404, 'Unknown SiteBOM action')

    def read_json(self):
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise ValueError('Expected a JSON request')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 16384:
            raise ValueError('Invalid request size')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object')
        return data

    def upload(self, project_id):
        try:
            project = get(SITE_ROOT, project_id)
        except (OSError, ValueError) as error:
            self.send_json({'error': str(error)}, 503)
            return
        if project is None or project['processor'] != 'intake':
            self.send_error(404, 'Unknown project upload')
            return
        query = parse_qs(urlsplit(self.path).query)
        kind = (query.get('kind') or [''])[0]
        name = (query.get('name') or [''])[0]
        if (not name or name in {'.', '..'} or len(name) > 180 or
                re.search(r'[<>:"/\\|?*\x00-\x1f]', name)):
            self.send_json({'error': 'Invalid file name'}, 400)
            return
        if kind == 'model' and name.lower().endswith('.neovi-model.json'):
            folder, limit = raw_dir(SITE_ROOT, project) / 'Model', 8 * 1024**3
        elif kind == 'pdf' and name.lower().endswith('.pdf'):
            folder, limit = raw_dir(SITE_ROOT, project) / 'AI Core', 250 * 1024**2
        else:
            self.send_json({'error': 'Choose a Neovi model JSON or PDF for this upload'}, 400)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if not 0 < length <= limit:
            self.send_json({'error': 'File is empty or exceeds this upload limit'}, 413)
            return
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        key = (project_id, kind, name.casefold())
        with upload_guard:
            if key in uploads_in_progress:
                self.send_json({'error': 'This file is already uploading'}, 409)
                return
            uploads_in_progress.add(key)
        if target.exists():
            with upload_guard:
                uploads_in_progress.discard(key)
            self.send_json({'error': 'A file with this name already exists in this project'}, 409)
            return
        temporary = folder / (name + '.uploading-' + uuid.uuid4().hex)
        digest = hashlib.sha256()
        try:
            remaining = length
            with temporary.open('xb') as output:
                while remaining:
                    block = self.rfile.read(min(4 * 1024 * 1024, remaining))
                    if not block:
                        raise ValueError('Upload ended before all bytes arrived')
                    output.write(block)
                    digest.update(block)
                    remaining -= len(block)
                output.flush()
                os.fsync(output.fileno())
            if kind == 'model':
                header = model_header(temporary)
                if header is None or (project['modelProjectName'] and
                        (project['modelProjectName'].casefold() != header['projectName'].casefold() or
                         project['projectNumber'] != header['projectNumber'])):
                    raise ValueError('Model does not match this Revit project')
            else:
                with temporary.open('rb') as source:
                    if source.read(5) != b'%PDF-':
                        raise ValueError('The uploaded drawing is not a PDF')
            if kind == 'model':
                with registry_lock:
                    other = assigned_project(load(SITE_ROOT), header, project_id)
                    if other is not None:
                        raise ValueError(f'This model already belongs to the {other["name"]} SiteBOM project')
                    temporary.replace(target)
                    try:
                        connect_uploaded_model(SITE_ROOT, project_id, target)
                    except Exception:
                        target.unlink(missing_ok=True)
                        raise
            else:
                temporary.replace(target)
            process_once()
            self.send_json({'fileName': name, 'bytes': length, 'sha256': digest.hexdigest(),
                            'projectId': project_id, 'kind': kind}, 201)
        except (OSError, ValueError) as error:
            self.send_json({'error': str(error)}, 400)
        finally:
            if temporary.exists():
                temporary.unlink()
            with upload_guard:
                uploads_in_progress.discard(key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    if not (SITE / 'index.html').is_file() or not DASHBOARD.is_file() or not PROJECT_PAGE.is_file():
        raise FileNotFoundError('Build the SiteBOM site and local project pages first')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    if sys.stdout:
        print(f'SiteBOM local: http://127.0.0.1:{args.port}/dashboard', flush=True)
    server.serve_forever(poll_interval=0.5)


if __name__ == '__main__':
    main()
