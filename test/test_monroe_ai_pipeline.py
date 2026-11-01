"""Checks that AI extraction cannot silently become an approved takeoff."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from monroe_ai_extract import parse_findings, run  # noqa: E402
from monroe_ai_review import build_report, pile_check  # noqa: E402
from monroe_ai_sources import make_plan, planned_jobs  # noqa: E402


class PipelineTests(unittest.TestCase):
    def test_twenty_passes_cover_each_page_before_next_pass(self):
        manifest = {'files': [{'path': f'AI Core/{name}', 'sha256': 'a' * 64,
                               'suffix': '.pdf', 'role': 'current_core', 'pages': 2}
                              for name in (
            'Monroe SE sheets.pdf',
            'Neovi - Monroe_Steel Shop Drawings_REV 1 2025.12.18.pdf',
            'Neovi - Monroe_Fabrication Shop Drawing Package - Wall Panels 2026-08-26.pdf',
            'Neovi - Monroe_Fabrication 2000 Series - Floor Cassettes 2026-08-19.pdf')]}
        plan = make_plan(manifest, 'gemini-3.5-flash-lite', 20, 20)
        jobs = list(planned_jobs(plan))
        self.assertEqual((plan['pagesPerPass'], plan['plannedRequests']), (8, 160))
        self.assertEqual([job['repeat'] for job in jobs[:9]], [1] * 8 + [2])

    def test_invalid_quantity_and_missing_evidence_rejected(self):
        base = {'item': 'Bolt', 'category': 'bedframe', 'quantity': -1,
                'installationScope': 'site_installed', 'evidence': 'bolt note'}
        response = {'candidates': [{'content': {'parts': [{'text': json.dumps({'findings': [base]})}]}}]}
        with self.assertRaisesRegex(ValueError, 'invalid quantity'):
            parse_findings(response)
        base['quantity'] = 2
        base['evidence'] = ''
        response['candidates'][0]['content']['parts'][0]['text'] = json.dumps({'findings': [base]})
        with self.assertRaisesRegex(ValueError, 'lacks drawing evidence'):
            parse_findings(response)

    def test_schedule_flags_wrong_ai_row_even_if_total_looks_plausible(self):
        schedule = json.loads((ROOT / 'config/monroe-helical-pile-schedule.json').read_text())
        findings = [{'item': row['pileId'], 'quantity': row['count'],
                     'size': row['diameterIn']} for row in schedule['rows']]
        findings[3]['quantity'] += 2
        document = {'page': 3, 'repeat': 1, 'result': {'findings': findings}}
        check = pile_check(document, schedule)
        self.assertEqual(check['status'], 'review_discrepancy')
        self.assertEqual(check['mismatches'][0]['pileId'], 'HP-2a')

    def test_daily_cap_blocks_network_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'drawing.pdf').write_bytes(b'test')
            plan = {'model': 'gemini-3.5-flash-lite', 'localDailyCap': 1,
                    'plannedRequests': 1, 'repeatsPerPage': 1,
                    'sources': [{'path': 'drawing.pdf', 'sha256': 'wrong',
                                 'pages': 1, 'scope': 'test'}]}
            with patch('monroe_ai_extract.request_gemini') as request:
                with self.assertRaisesRegex(ValueError, 'Source changed'):
                    run(plan, root, root / 'output', 1, 1)
                request.assert_not_called()

    def test_review_handles_unknown_and_numeric_quantities_for_same_item(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'extractions'
            folder.mkdir()
            source = 'AI Core/Monroe SE sheets.pdf'
            plan = {'model': 'gemini-3.5-flash-lite', 'pagesPerPass': 1,
                    'plannedRequests': 2, 'sources': [{'path': source,
                    'sha256': 'a' * 64, 'pages': 1}]}
            (root / 'page-plan.json').write_text(json.dumps(plan))
            for repeat in (1, 2):
                document = {'project': 'Monroe', 'reviewStatus': 'candidate_only',
                            'source': source, 'sourceSha256': 'a' * 64,
                            'model': plan['model'], 'page': 1, 'repeat': repeat,
                            'result': {'findings': [
                                {'item': 'Bolt', 'category': 'bedframe', 'quantity': None,
                                 'installationScope': 'unknown', 'evidence': 'Bolt'},
                                {'item': 'Bolt', 'category': 'bedframe', 'quantity': repeat,
                                 'installationScope': 'unknown', 'evidence': 'Bolt'}]}}
                (folder / f'{repeat}.json').write_text(json.dumps(document))
            report = build_report(root)
            self.assertEqual(report['completedRequests'], 2)
            self.assertEqual(len(report['pagePassDisagreements']), 1)


if __name__ == '__main__':
    unittest.main()
