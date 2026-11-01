"""Verify structural schedule reconciliation and diameter-specific rod arithmetic."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from monroe_structural_schedule import load_pile_schedule, rod_lengths_by_diameter


class StructuralScheduleTest(unittest.TestCase):
    def test_pile_rows_and_diameter_subtotals_reconcile(self):
        schedule = load_pile_schedule()
        self.assertEqual(schedule['totalPiles'], 48)
        self.assertEqual({row['diameterIn']: row['count'] for row in schedule['byDiameter']},
                         {'3 1/2"': 9, '4 1/2"': 22, '2 7/8"': 17})

    def test_rod_cut_length_stays_separate_by_diameter(self):
        result = rod_lengths_by_diameter([
            {'sourceId': 'HD-1', 'kind': 'hold_down', 'diameterIn': '1"'},
            {'sourceId': 'HD-2', 'kind': 'hold_down', 'diameterIn': '1"'},
            {'sourceId': 'LA-1', 'kind': 'l_angle', 'diameterIn': '7/8"'},
        ])
        self.assertEqual(result['1"']['totalIn'], 42)
        self.assertEqual(result['1"']['totalFt'], 3.5)
        self.assertEqual(result['7/8"']['totalIn'], 21)
        self.assertEqual(result['7/8"']['totalFt'], 1.75)
        with self.assertRaises(ValueError):
            rod_lengths_by_diameter([
                {'sourceId': 'HD-1', 'kind': 'hold_down', 'diameterIn': '1"'},
                {'sourceId': 'HD-1', 'kind': 'l_angle', 'diameterIn': '1"'},
            ])


if __name__ == '__main__':
    unittest.main()
