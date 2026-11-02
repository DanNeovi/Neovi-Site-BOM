import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts/auto_process_monroe.py'
spec = importlib.util.spec_from_file_location('auto_process_monroe', MODULE_PATH)
automation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(automation)


class AutoProcessMonroeTests(unittest.TestCase):
    def test_rejects_wrong_project_before_processing(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary) / 'wrong.neovi-model.json'
            model.write_text('{"project":{"projectName":"Fernando"},"elements":[]}')
            with patch.object(automation, 'DRIVE', Path(temporary)), patch.object(automation, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'not the Monroe export'):
                    automation.process(model, index_drawings=False)
                run.assert_not_called()

    def test_only_changed_model_and_drawings_trigger_rebuild(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            model = folder / 'monroe.neovi-model.json'
            model.write_text('{"project":{"projectName":"206 Monroe Drive"},"elements":[]}')
            documents = folder / 'documents'
            core = documents / 'AI Core'
            core.mkdir(parents=True)
            for name in automation.CORE_PDFS:
                (core / name).write_bytes(b'%PDF-1.4\n')
            state = folder / 'automation-state.json'
            with (patch.object(automation, 'DRIVE', folder),
                  patch.object(automation, 'DOCUMENTS', documents),
                  patch.object(automation, 'STATE', state),
                  patch.object(automation, 'run') as run):
                first = automation.process(model)
                self.assertEqual(2, len(first))
                self.assertEqual(7, run.call_count)
                self.assertEqual([], automation.process(model))
                self.assertEqual(7, run.call_count)
                (core / automation.CORE_PDFS[0]).write_bytes(b'%PDF-1.5\n')
                self.assertEqual(['current AI Core and older drawing index'], automation.process(model))
                self.assertEqual(9, run.call_count)
                saved = json.loads(state.read_text())
                self.assertEqual(4, len(saved['drawings']))


if __name__ == '__main__':
    unittest.main()
