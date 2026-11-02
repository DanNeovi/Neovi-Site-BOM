"""Check A7.1 operation mapping against model-style Mark and Type Mark data."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from monroe_window_schedule import classify_window_operations, load_window_schedule


def window(row, family):
    return {'key': 'host:window-' + row['mark'], 'family': family,
            'parameters': [{'name': 'Mark', 'hasValue': True, 'displayValue': row['mark']},
                           {'name': 'Type Mark', 'hasValue': True,
                            'displayValue': row['typeMark']}]}


class MonroeWindowScheduleTest(unittest.TestCase):
    def setUp(self):
        self.schedule = load_window_schedule(source_pdf=None)
        self.windows = [window(row, 'AGRV_GLAZ_Hung-A2-A1_-A2-A1_21181'
                               if row['mark'] == '204' else
                               'Neovi_WD_Fixed' if row['operation'] == 'FIXED' else
                               'Neovi_WD_Tilt&Turn') for row in self.schedule['rows']]

    def test_fixed_204_is_not_operable_because_family_contains_hung(self):
        fixed, operable = classify_window_operations(self.windows, self.schedule)
        self.assertEqual((len(fixed), len(operable)), (5, 19))
        self.assertIn('host:window-204', {element['key'] for element in fixed})

    def test_unscheduled_or_duplicate_mark_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate or unscheduled'):
            classify_window_operations(self.windows + [self.windows[0]], self.schedule)
        bad = list(self.windows)
        bad[0] = window({'mark': '999', 'typeMark': 'A1'}, 'Neovi_WD_Tilt&Turn')
        with self.assertRaisesRegex(ValueError, 'Duplicate or unscheduled'):
            classify_window_operations(bad, self.schedule)

    def test_type_mark_disagreement_is_rejected(self):
        bad = list(self.windows)
        bad[0] = window({'mark': '101', 'typeMark': 'B2'}, 'Neovi_WD_Tilt&Turn')
        with self.assertRaisesRegex(ValueError, 'Type Mark differs'):
            classify_window_operations(bad, self.schedule)


if __name__ == '__main__':
    unittest.main()
