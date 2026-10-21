"""Check Monroe story drivers, fastener arithmetic and full catalog coverage."""
import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('build_monroe_estimates', ROOT / 'scripts/build-monroe-estimates.py')
monroe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monroe)


class MonroeEstimatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((ROOT / 'outputs/NeoviBOM/05-Monroe/Monroe-Item-Formulas.json').read_text())
        cls.items = {item['lineId']: item for item in cls.report['items']}

    def test_complete_catalog_with_no_unexplained_quantity(self):
        catalog = json.loads((ROOT / 'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())
        self.assertEqual(set(self.items), {line['lineId'] for line in catalog})
        self.assertEqual(len(self.items), len(catalog))
        for item in self.items.values():
            self.assertGreaterEqual(item['quantity'], 0)
            self.assertTrue(item['formula'])
            self.assertTrue(item['assumption'])
            self.assertTrue(item['references'])
            self.assertGreaterEqual(item['baseKitQuantity'], item['quantity'])
            self.assertIn('averagePerLivableSqft', item['averageMetrics'])
            if item['basis'] not in ('PLANNING_PLACEHOLDER', 'PLANNING_CONDITIONAL_ZERO'):
                self.assertTrue(math.isclose(item['averageMetrics']['averagePerLivableSqft'],
                                             item['quantity'] / self.report['drivers']['floorArea']['value']))

    def test_story_areas_and_wall_runs_reconcile(self):
        d = self.report['drivers']
        first, second = d['firstStoryArea']['value'], d['secondStoryArea']['value']
        self.assertTrue(math.isclose(first + second, d['floorArea']['value']))
        self.assertGreater(first, second)
        audit = self.report['storyAreaAudit']['FIRST FLOOR']
        self.assertGreater(audit['overlapSqft'], 1200)
        self.assertTrue(math.isclose(audit['areaSqft'] - audit['garageOverlapSqft'], first))
        self.assertLess(first, audit['rawElementAreaSumSqft'])
        self.assertEqual(self.items['PAN-040']['quantity'], math.ceil(d['roofProxyArea']['value']))
        self.assertIn('roofProxyArea', self.items['PAN-040']['formula'])
        self.assertEqual(self.items['PAN-036']['quantity'],
                         math.ceil(d['exteriorWallNetFaceAreaProxy']['value'] * 0.1))
        self.assertLess(d['exteriorWallNetFaceAreaProxy']['value'],
                        d['exteriorWallGrossFaceArea']['value'])
        self.assertTrue(math.isclose(d['interiorWallLength']['value'] +
                                     d['exteriorWallLength']['value'], d['wallLength']['value']))
        self.assertTrue(math.isclose(d['garageWallLength']['value'] +
                                     d['nonGarageExteriorWallLength']['value'],
                                     d['exteriorWallLength']['value']))
        self.assertGreater(d['garageRoomPerimeter']['value'], d['garageWallLength']['value'])
        self.assertTrue(math.isclose(d['firstStoryWallLength']['value'] +
                                     d['secondStoryWallLength']['value'], d['wallLength']['value']))
        for lid in ('PAN-009', 'PAN-010', 'PAN-030'):
            item = self.items[lid]
            allocation = item['storyAllocation']
            self.assertEqual(sum(part['quantity'] for part in allocation.values()), item['quantity'])
            self.assertGreater(allocation['FIRST FLOOR']['quantity'], 0)
            self.assertGreater(allocation['SECOND FLOOR']['raw'], 0)
        self.assertEqual(self.items['PAN-009']['quantity'], math.ceil(4 * d['wallLength']['value']))

    def test_model_connections_and_corresponding_planning_hardware(self):
        d = self.report['drivers']
        self.assertEqual(self.items['PAN-002']['basis'], 'MODEL_MEASURED')
        self.assertEqual(self.items['PAN-002']['quantity'], d['floorPlates']['value'])
        self.assertEqual(self.items['PAN-002']['baseKitQuantity'], 250)
        self.assertEqual(self.items['PAN-006']['quantity'], 8 * d['floorPlates']['value'])
        self.assertEqual(self.items['PAN-013']['quantity'], d['holdDowns']['value'])
        self.assertEqual(self.items['PAN-029']['quantity'], 2 * d['holdDowns']['value'])
        self.assertEqual(self.items['FND-014']['quantity'], 2 * d['pileProxy']['value'])
        self.assertEqual(self.items['PAN-016']['quantity'], 8 * d['trussCount']['value'])
        self.assertEqual(d['floorClipFastenerPositions']['value'], 3858)

    def test_fastener_averages_use_relevant_denominators(self):
        d = self.report['drivers']
        truss = self.items['PAN-016']['averageMetrics']
        self.assertEqual(truss['primaryDriver'], 'trussCount')
        self.assertEqual(truss['averagePerPrimaryDriver'], 8)
        self.assertEqual(truss['areaDriver'], 'roofProxyArea')
        self.assertTrue(math.isclose(truss['averagePerApplicableSqft'],
                                     400 / d['roofProxyArea']['value']))
        self.assertEqual(self.items['PAN-040']['averageMetrics']['primaryDriver'], 'roofProxyArea')
        self.assertEqual(self.items['PAN-036']['averageMetrics']['primaryDriver'],
                         'exteriorWallNetFaceAreaProxy')
        self.assertEqual(self.items['FIN-107']['quantity'], math.ceil(d['trussFinishBoardArea']['value']))
        self.assertEqual(self.items['FIN-108']['quantity'],
                         math.ceil(8 * d['trussFinishBoardArea']['value']))
        self.assertEqual(self.items['FIN-108']['averageMetrics']['areaDriver'],
                         'trussFinishBoardArea')
        self.assertTrue(math.isclose(self.items['PAN-021']['averageMetrics']['averagePerApplicableSqft'],
                                     self.items['PAN-021']['quantity'] / d['roofProxyArea']['value']))
        self.assertTrue(math.isclose(self.items['FIN-166']['averageMetrics']['averagePerApplicableSqft'],
                                     self.items['FIN-166']['quantity'] / d['garageArea']['value']))

    def test_floor_area_and_wall_run_budgets_split_by_story(self):
        d = self.report['drivers']
        for lid, driver_prefix in [('PAN-012', 'WallLength'),
                                   ('FIN-001', 'Area'), ('FIN-015', 'Area'),
                                   ('FIN-018', 'Area'), ('FIN-103', 'Area')]:
            item = self.items[lid]
            allocation = item['storyAllocation']
            self.assertEqual(sum(part['quantity'] for part in allocation.values()), item['quantity'])
            self.assertGreater(allocation['FIRST FLOOR']['quantity'], 0)
            self.assertGreater(allocation['SECOND FLOOR']['raw'], 0)
            self.assertGreater(allocation['FIRST FLOOR']['raw'],
                               allocation['SECOND FLOOR']['raw'] if driver_prefix == 'Area' else 0)
        self.assertTrue(math.isclose(self.items['FIN-001']['storyAllocation']['FIRST FLOOR']['raw'],
                                     d['firstStoryArea']['value'] * 0.6))
        self.assertTrue(math.isclose(self.items['PAN-012']['storyAllocation']['SECOND FLOOR']['raw'],
                                     d['secondStoryWallLength']['value'] * 0.1))
        self.assertNotIn('storyAllocation', self.items['PAN-015'])

    def test_finish_quantities_avoid_duplicate_model_representations(self):
        d = self.report['drivers']
        self.assertLess(d['ledProfileLength']['value'], d['ledProfileRawSum']['value'])
        self.assertIn('spatial duplicates excluded', d['ledProfileLength']['description'])
        self.assertEqual(self.items['FIN-162']['quantity'], d['shadeCount']['value'])
        self.assertEqual(self.items['FIN-104']['quantity'], math.ceil(d['dryFloorArea']['value']))
        self.assertEqual(self.items['FIN-161']['quantity'], math.ceil(d['windowTrimLength']['value']))
        self.assertEqual(self.items['FIN-112']['quantity'], 4 * d['solarPanels']['value'])
        self.assertEqual(d['operableWindows']['value'] + d['fixedWindows']['value'], d['windows']['value'])
        self.assertEqual(self.items['FIN-159']['quantity'], d['operableWindows']['value'])
        self.assertEqual(self.items['FIN-160']['quantity'], d['operableWindows']['value'])
        for lid, plural in [('FIN-084', 'Doors'), ('FIN-088', 'Windows')]:
            item = self.items[lid]
            self.assertEqual(item['storyAllocation']['FIRST FLOOR']['quantity'],
                             8 * d['firstStory' + plural]['value'])
            self.assertEqual(item['storyAllocation']['SECOND FLOOR']['quantity'],
                             8 * d['secondStory' + plural]['value'])
            self.assertEqual(sum(part['quantity'] for part in item['storyAllocation'].values()),
                             item['quantity'])

    def test_split_system_materials_are_explicitly_conditional(self):
        for line in ('FIN-054', 'FIN-055', 'FIN-056'):
            item = self.items[line]
            self.assertEqual(item['basis'], 'PLANNING_CONDITIONAL_ZERO')
            self.assertEqual(item['quantity'], 0)
            self.assertIn('split', item['assumption'].lower())

    def test_electrical_allowances_follow_outlet_classes(self):
        d = self.report['drivers']
        self.assertEqual(d['standardOutlets']['value'], 143)
        self.assertEqual(d['highAmp30']['value'], 3)
        self.assertEqual(d['highAmp50']['value'], 3)
        self.assertEqual(self.items['FIN-058']['quantity'], 131)
        self.assertEqual(self.items['FIN-002']['quantity'], 2 * d['standardOutlets']['value'])
        self.assertEqual(self.items['FIN-003']['quantity'], 20 * d['highAmp30']['value'])
        self.assertEqual(self.items['FIN-005']['quantity'], 20 * d['highAmp50']['value'])
        self.assertEqual(self.items['FIN-137']['quantity'], 2 * d['standardOutlets']['value'])
        self.assertEqual(self.items['FIN-138']['quantity'], 2 * d['highAmp30']['value'])
        self.assertEqual(d['smartControls']['value'], 26)
        self.assertEqual(self.items['FIN-098']['quantity'], 2 * d['smartControls']['value'])
        self.assertEqual(self.items['FIN-061']['quantity'], 57)

    def test_measured_lengths_and_confirmed_standards_stay_distinct(self):
        gutter = self.items['FIN-115']
        self.assertTrue(math.isclose(gutter['quantity'], gutter['modelQuantity']))
        self.assertNotEqual(gutter['quantity'], round(gutter['quantity']))
        self.assertEqual(self.items['FND-009']['quantity'], 3)
        self.assertEqual(self.items['FND-009']['basis'], 'CONFIRMED_STANDARD')
        self.assertEqual(self.items['FND-006']['basis'], 'PLANNING_ESTIMATE')

    def test_reusable_hoses_are_complete_units_with_length_assumption(self):
        for lid in ('FND-037', 'FIN-146'):
            item = self.items[lid]
            self.assertEqual(item['unit'], 'EA')
            self.assertEqual(item['quantity'], 1)
            self.assertIn('100-ft hose', item['assumption'])
        self.assertEqual(self.items['FND-054']['unit'], 'EA')
        self.assertEqual(self.items['FND-054']['quantity'], 10)
        self.assertIn('10 leveling-string sets', self.items['FND-054']['assumption'])

    def test_foundation_rental_and_retired_placeholders(self):
        self.assertEqual(self.items['FND-011']['quantity'], 14)
        self.assertEqual(self.items['FND-011']['unit'], 'DAY')
        self.assertIn('two-week', self.items['FND-011']['assumption'].lower())
        self.assertEqual(self.items['FND-060']['quantity'], 1)
        self.assertEqual(self.items['FND-061']['quantity'], 10)
        for lid in ('FND-003', 'FND-005'):
            self.assertNotIn(lid, self.items)
        catalog = json.loads((ROOT / 'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())
        by_id = {line['lineId']: line for line in catalog}
        for lid in ('FND-055', 'FND-056', 'FND-057', 'FND-020', 'FND-037', 'FND-060'):
            self.assertEqual(by_id[lid]['stage'], 'Helical Piles')
        self.assertEqual(by_id['FND-061']['stage'], 'Site Setup and Support')

    def test_complete_consumable_packages_are_counted_in_eaches(self):
        expected = {
            'FND-048': 4, 'PAN-035': 1, 'FIN-143': 1,
            'FIN-144': 1, 'FIN-151': 1, 'FIN-152': 1,
            'FIN-089': 16, 'FIN-123': 1, 'FIN-125': 1, 'FIN-176': 1,
        }
        for lid, quantity in expected.items():
            with self.subTest(lid=lid):
                self.assertEqual(self.items[lid]['unit'], 'EA')
                self.assertEqual(self.items[lid]['quantity'], quantity)
                self.assertIn('assumed', self.items[lid]['assumption'].lower())


if __name__ == '__main__':
    unittest.main()
