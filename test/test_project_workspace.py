"""Project creation, source isolation, and the local HTTP workflow."""

import http.client
import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_intake  # noqa: E402
import project_registry  # noqa: E402
import auto_process_projects  # noqa: E402


def model(name='Test House', number='T1'):
    return json.dumps({'project': {'projectName': name, 'projectNumber': number,
                                    'title': 'Test model'},
                       'elements': [{'category': 'Walls', 'sourceKey': 'host'},
                                    {'category': 'Doors', 'sourceKey': 'host'}]}).encode()


class ProjectRegistryTests(unittest.TestCase):
    def test_live_sheet_sync_runs_only_after_changed_export_and_pin_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            pin = Path(temporary) / 'pin.txt'
            with patch.object(auto_process_projects, 'PIN_FILE', pin), \
                    patch.object(auto_process_projects.subprocess, 'run',
                                 return_value=SimpleNamespace(returncode=0)) as run:
                auto_process_projects.sync_live_if_export_changed(['model quantities and G: exports'])
                run.assert_not_called()
                pin.write_text('test-only-placeholder', encoding='utf-8')
                auto_process_projects.sync_live_if_export_changed(['current AI Core and older drawing index'])
                run.assert_not_called()
                auto_process_projects.sync_live_if_export_changed(['model quantities and G: exports'])
                run.assert_called_once()

    def test_project_creation_does_not_copy_unapproved_existing_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = project_registry.load(root)
            self.assertEqual([p['id'] for p in document['projects']],
                             ['monroe', 'franklin', 'santa-rita'])
            self.assertTrue((root / '00-Raw/Monroe/Model').is_dir())
            self.assertFalse(list((root / '00-Raw/franklin/Model').iterdir()))
            created = project_registry.create(root, 'Test House')
            self.assertEqual(created['id'], 'test-house')
            for relative in ('00-Raw/test-house/Model', '00-Raw/test-house/AI Core',
                             '02-Projects/test-house', '04-Audits/test-house'):
                self.assertTrue((root / relative).is_dir())
            with self.assertRaisesRegex(ValueError, 'already exists'):
                project_registry.create(root, 'Test House')
            with self.assertRaises(ValueError):
                project_registry.create(root, '..')
            with patch.object(project_registry, 'find_export', return_value={
                    'projectName': '206 Monroe Drive', 'projectNumber': '00004',
                    'cloudProjectGuid': '', 'cloudModelGuid': '', 'path': 'unused'}):
                with self.assertRaisesRegex(ValueError, 'Monroe SiteBOM project'):
                    project_registry.create(root, 'Duplicate Monroe', 'selected-export')

    def test_uploaded_model_identity_and_raw_census(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = project_registry.create(root, 'Test House')
            path = root / '00-Raw/test-house/Model/test.neovi-model.json'
            path.write_bytes(model())
            project_registry.connect_uploaded_model(root, project['id'], path)
            result = project_intake.process(root, project_registry.get(root, project['id']))
            self.assertEqual(result['elements'], 2)
            self.assertEqual(result['categories'], {'Doors': 1, 'Walls': 1})
            self.assertEqual(result['quantityStatus'], 'raw_model_only_needs_project_rules')
            self.assertEqual(project_intake.process(root, project_registry.get(root, project['id']))['generatedAtUtc'],
                             result['generatedAtUtc'])
            wrong = path.parent / 'wrong.neovi-model.json'
            wrong.write_bytes(model('Another Project'))
            with self.assertRaisesRegex(ValueError, 'different Revit project'):
                project_registry.connect_uploaded_model(root, project['id'], wrong)


class ProjectHttpTests(unittest.TestCase):
    def test_server_start_does_not_scan_sources(self):
        spec = importlib.util.spec_from_file_location('sitebom_server_start', ROOT / 'scripts/serve-local-sitebom.py')
        server_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server_module)
        fake_server = Mock()
        with patch.object(server_module, 'ThreadingHTTPServer', return_value=fake_server), \
                patch.object(server_module, 'process_once') as process, \
                patch.object(sys, 'argv', ['serve-local-sitebom.py']):
            server_module.main()
            process.assert_not_called()
            fake_server.serve_forever.assert_called_once()

    def test_file_added_during_processing_queues_one_more_run(self):
        spec = importlib.util.spec_from_file_location('sitebom_server_queue', ROOT / 'scripts/serve-local-sitebom.py')
        server_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server_module)
        entered, release, reran = threading.Event(), threading.Event(), threading.Event()
        calls = []
        def run(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                entered.set()
                self.assertTrue(release.wait(5))
            else:
                reran.set()
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(server_module, 'LOG', Path(temporary) / 'automation.log'), \
                patch.object(server_module.subprocess, 'run', side_effect=run):
            self.assertTrue(server_module.process_once())
            self.assertTrue(entered.wait(5))
            self.assertFalse(server_module.process_once())
            self.assertTrue(server_module.worker['rerunRequested'])
            release.set()
            self.assertTrue(reran.wait(5))
            deadline = time.monotonic() + 5
            while server_module.worker['running'] and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(server_module.worker['running'])
            self.assertEqual(len(calls), 2)

    def test_create_upload_and_private_routes(self):
        spec = importlib.util.spec_from_file_location('sitebom_server', ROOT / 'scripts/serve-local-sitebom.py')
        server_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server_module)
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(server_module, 'SITE_ROOT', Path(temporary)), \
                patch.object(server_module, 'process_once', return_value=True) as trigger:
            ai_folder = Path(temporary) / '04-Audits/Monroe-AI'
            ai_folder.mkdir(parents=True)
            (ai_folder / 'page-plan.json').write_text(json.dumps({'model': 'test-gemini',
                'pagesPerPass': 2}), encoding='utf-8')
            (ai_folder / 'review-report.json').write_text(json.dumps({'pagesReadAtLeastOnce': 2,
                'completedRequests': 2, 'candidateFindings': 4}), encoding='utf-8')
            (ai_folder / 'candidate-findings.csv').write_text('item\nTest\n', encoding='utf-8')
            server = server_module.ThreadingHTTPServer(('127.0.0.1', 0), server_module.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f'http://127.0.0.1:{server.server_port}'
            def request(method, path, body=None, headers=None):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                result = response.status, response.read()
                connection.close()
                return result
            try:
                code, html = request('GET', '/dashboard')
                self.assertEqual(code, 200)
                self.assertIn(b'Your Site BOM projects', html)
                code, payload = request('GET', '/api/projects')
                self.assertEqual(code, 200)
                self.assertEqual(len(json.loads(payload)['projects']), 3)
                monroe = json.loads(payload)['projects'][0]
                self.assertEqual(monroe['gemini']['pagesReadAtLeastOnce'], 2)
                self.assertEqual(monroe['gemini']['candidateFindings'], 4)
                self.assertEqual(request('GET', '/projects/monroe/gemini/review-report.json')[0], 200)
                self.assertEqual(request('GET', '/projects/monroe/gemini/candidate-findings.csv')[0], 200)
                self.assertEqual(request('GET', '/projects/monroe/gemini/page-plan.json')[0], 404)
                data = json.dumps({'name': 'Test House'}).encode()
                headers = {'Origin': origin, 'Content-Type': 'application/json'}
                code, payload = request('POST', '/api/projects', data, headers)
                self.assertEqual(code, 201, payload)
                self.assertEqual(json.loads(payload)['id'], 'test-house')
                duplicate = json.dumps({'name': 'Second Site'}).encode()
                code, payload = request('POST', '/api/projects', duplicate, headers)
                self.assertEqual(code, 201, payload)
                self.assertEqual(trigger.call_count, 0)
                self.assertTrue((Path(temporary) / '00-Raw/test-house/Model').is_dir())
                self.assertEqual(request('POST', '/api/projects', data, headers)[0], 400)
                self.assertEqual(request('POST', '/api/projects', data,
                                         {**headers, 'Origin': 'http://untrusted.example'})[0], 403)
                upload_headers = {'Origin': origin, 'Content-Type': 'application/octet-stream'}
                code, payload = request('POST', '/api/projects/test-house/upload?kind=model&name=test.neovi-model.json',
                                        model(), upload_headers)
                self.assertEqual(code, 201, payload)
                self.assertEqual(trigger.call_count, 1)
                duplicate_path = '/api/projects/second-site/upload?kind=model&name=duplicate.neovi-model.json'
                code, payload = request('POST', duplicate_path, model(), upload_headers)
                self.assertEqual(code, 400, payload)
                self.assertFalse((Path(temporary) / '00-Raw/second-site/Model/duplicate.neovi-model.json').exists())
                project = project_registry.get(Path(temporary), 'test-house')
                result = project_intake.process(Path(temporary), project)
                self.assertEqual(result['categories']['Walls'], 1)
                code, payload = request('POST', '/api/projects/test-house/upload?kind=pdf&name=plans.pdf',
                                        b'%PDF-1.4\n%%EOF', upload_headers)
                self.assertEqual(code, 201, payload)
                self.assertEqual(trigger.call_count, 2)
                code, payload = request('GET', '/api/projects/test-house')
                self.assertEqual(code, 200)
                self.assertEqual(len(json.loads(payload)['pdfs']), 1)
                self.assertEqual(request('GET', '/projects/test-house')[0], 200)
                self.assertEqual(request('GET', '/projects/test-house/reports/model-summary.json')[0], 200)
                self.assertEqual(request('GET', '/preview/00-Raw/test-house/Model/test.neovi-model.json')[0], 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
