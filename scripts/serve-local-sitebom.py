"""Host SiteBOM on this computer and process newly published raw files."""

import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from auto_process_monroe import CORE_PDFS, DRIVE, STATE
from private_drive_sources import CORE_FOLDER, DRIVE_ROOT, MODEL_FOLDER, MODEL_NAME, PRIVATE_FOLDER_URL


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
DASHBOARD = ROOT / 'local-site/index.html'
LOG = STATE.parent / 'automation.log'
worker_lock = threading.Lock()
worker = {'running': False, 'lastStartedUtc': None, 'lastFinishedUtc': None,
          'lastExitCode': None, 'lastError': None}


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
            'log': str(LOG), 'checkIntervalSeconds': 300}


def process_once():
    if not worker_lock.acquire(blocking=False):
        return False
    def work():
        worker.update(running=True, lastStartedUtc=datetime.now(timezone.utc).isoformat(),
                      lastError=None)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        try:
            with LOG.open('a', encoding='utf-8') as log:
                log.write(f"\n[{worker['lastStartedUtc']}] Processing raw sources\n")
                log.flush()
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/auto_process_monroe.py')],
                                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                        check=False)
                worker['lastExitCode'] = result.returncode
                if result.returncode:
                    worker['lastError'] = f'Processing exited with code {result.returncode}; see automation.log'
        except Exception as error:
            worker['lastExitCode'] = -1
            worker['lastError'] = str(error)
        finally:
            worker['running'] = False
            worker['lastFinishedUtc'] = datetime.now(timezone.utc).isoformat()
            worker_lock.release()
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

    def do_GET(self):
        if not self.local_host_only():
            return
        path = urlsplit(self.path).path
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        if path == '/api/status':
            payload = json.dumps(status(), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == '/':
            self.path = '/dashboard'
            path = '/dashboard'
        if path == '/dashboard':
            body = DASHBOARD.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
        if urlsplit(self.path).path != '/api/process':
            self.send_error(404)
            return
        origin = self.headers.get('Origin')
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if origin != expected or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send_error(403, 'Use the local SiteBOM dashboard')
            return
        started = process_once()
        body = json.dumps({'started': started, 'running': worker['running']}).encode()
        self.send_response(202 if started else 409)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    if not (SITE / 'index.html').is_file() or not DASHBOARD.is_file():
        raise FileNotFoundError('Build the SiteBOM site and local dashboard first')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    def poll():
        while True:
            process_once()
            time.sleep(300)
    threading.Thread(target=poll, daemon=True, name='sitebom-poll').start()
    if sys.stdout:
        print(f'SiteBOM local: http://127.0.0.1:{args.port}/dashboard', flush=True)
    server.serve_forever(poll_interval=0.5)


if __name__ == '__main__':
    main()
