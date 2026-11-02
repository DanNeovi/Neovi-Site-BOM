"""Project creation, source isolation, and the local HTTP workflow."""

import http.client
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_intake  # noqa: E402
import project_registry  # noqa: E402


def model(name='Test House', number='T1'):
    return json.dumps({'project': {'projectName': name, 'projectNumber': number,
                                    'title': 'Test model'},
                       'elements': [{'category': 'Walls', 'sourceKey': 'host'},
                                    {'category': 'Doors', 'sourceKey': 'host'}]}).encode()


class ProjectRegistryTests(unittest.TestCase):
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
    def test_create_upload_and_private_routes(self):
        spec = importlib.util.spec_from_file_location('sitebom_server', ROOT / 'scripts/serve-local-sitebom.py')
        server_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server_module)
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(server_module, 'SITE_ROOT', Path(temporary)), \
                patch.object(server_module, 'process_once', return_value=True):
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
                data = json.dumps({'name': 'Test House'}).encode()
                headers = {'Origin': origin, 'Content-Type': 'application/json'}
                code, payload = request('POST', '/api/projects', data, headers)
                self.assertEqual(code, 201, payload)
                self.assertEqual(json.loads(payload)['id'], 'test-house')
                duplicate = json.dumps({'name': 'Second Site'}).encode()
                code, payload = request('POST', '/api/projects', duplicate, headers)
                self.assertEqual(code, 201, payload)
                self.assertTrue((Path(temporary) / '00-Raw/test-house/Model').is_dir())
                self.assertEqual(request('POST', '/api/projects', data, headers)[0], 400)
                self.assertEqual(request('POST', '/api/projects', data,
                                         {**headers, 'Origin': 'http://untrusted.example'})[0], 403)
                upload_headers = {'Origin': origin, 'Content-Type': 'application/octet-stream'}
                code, payload = request('POST', '/api/projects/test-house/upload?kind=model&name=test.neovi-model.json',
                                        model(), upload_headers)
                self.assertEqual(code, 201, payload)
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
