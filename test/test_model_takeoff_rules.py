import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model_takeoff_rules import measured, parameter, select_unique, outlet_class, add_extended_rules, add_hardware_rules, add_circuit_rules, eligible
from opening_takeoffs import add_opening_rules
from planning_estimates import estimate_rules
from project_model_mapper import map_model

def element(key='host:a',**kwargs):
    return dict(key=key,sourceKey='host',phaseCreated='New Construction',parameters=[],**kwargs)

class MappingTests(unittest.TestCase):
    def circuit_fixture(self,key='host:circuit',size='12/2',length=10,runs=2,state='Circuit'):
        e=element(key,category='Electrical Circuits',revitClass='Autodesk.Revit.DB.Electrical.ElectricalSystem')
        e['phaseCreated']=''
        e['parameters']=[dict(name=k,scope='instance',hasValue=True,displayValue=v,stringValue=v) for k,v in [('Panel','Panel A'),('Circuit Number',key),('Circuit State',state),('System Type','Power'),('Cable Size',size),('Cable Type','Residential'),('Connection Type','Breaker')]]
        e['parameters'] += [dict(name='Length',scope='instance',hasValue=True,doubleValue=length,dataType='autodesk.spec.aec:length-2.0.0'),dict(name='# of Runs',scope='instance',hasValue=True,integerValue=runs)]
        return e

    def test_nonphased_circuit_included_but_spare_excluded(self):
        self.assertTrue(eligible(self.circuit_fixture()))
        self.assertFalse(eligible(self.circuit_fixture(state='Spare')))
        e=self.circuit_fixture();e['category']='Generic Models'
        self.assertFalse(eligible(e))

    def test_circuit_route_size_and_runs_not_pole_count(self):
        out={};add_circuit_rules([self.circuit_fixture(),self.circuit_fixture('host:b','8/3',7,1)],out)
        self.assertEqual(out['FIN-001']['value'],20)
        self.assertEqual(out['FIN-005']['value'],7)
        self.assertEqual(out['FIN-061']['value'],2)
        self.assertEqual(out['FIN-001']['status'],'MODEL_ROUTE_QUANTITY')
        self.assertIn('NOT specified',out['FIN-001']['description'])

    def test_circuit_missing_length_blocks_partial_route(self):
        a=self.circuit_fixture();b=self.circuit_fixture('host:b');b['parameters']=[p for p in b['parameters'] if p['name']!='Length']
        out={};add_circuit_rules([a,b],out);self.assertNotIn('FIN-001',out)

    def test_planning_rates_keep_provenance_and_do_not_mutate_measurements(self):
        drivers={'length':{'value':120,'references':['host:wall']}}
        out=estimate_rules(drivers,{'FIN-085':{'driver':'length','rate':1/144,'assumption':'0.5 x 2 inch gap'}})
        self.assertAlmostEqual(out['FIN-085']['value'],120/144)
        self.assertEqual(out['FIN-085']['status'],'PLANNING_ESTIMATE')
        self.assertEqual(out['FIN-085']['references'],['host:wall'])
        self.assertEqual(drivers['length']['value'],120)

    def test_missing_planning_driver_not_assumed_zero(self):
        self.assertEqual(estimate_rules({}, {'X':{'driver':'missing','rate':2,'assumption':'test'}}),{})

    def test_invalid_planning_rate_rejected(self):
        with self.assertRaises(ValueError):
            estimate_rules({}, {'X':{'driver':'missing','rate':float('nan'),'assumption':'test'}})

    def test_hardware_pattern_count_and_location_are_distinct(self):
        bolts=[]
        for key,location,count in [('a','Site',2),('b','Shop',7)]:
            e=element(key,category='Bolts');e['sourceKey']='host/structural'
            e['parameters']=[dict(name='Location',scope='instance',hasValue=True,integerValue=0,displayValue=location),
                             dict(name='Number',scope='instance',hasValue=True,integerValue=count)]
            bolts.append(e)
        out={};extra=add_hardware_rules(bolts,out)
        self.assertEqual(extra['Site bolts']['value'],2)
        self.assertEqual(extra['Shop bolts']['value'],7)
        self.assertNotIn('FND-015',out)

    def test_pile_cap_requires_explicit_host(self):
        e=element(family='Base Plate U Saddle');e['sourceKey']='host/structural'
        e['parameters']=[dict(name='Host',scope='instance',hasValue=True,stringValue='Level : GARAGE SLAB')]
        out={};add_hardware_rules([e],out);self.assertNotIn('FND-008',out)
        e['parameters'][0]['stringValue']='Level : Pile Cap'
        add_hardware_rules([e],out);self.assertEqual(out['FND-008']['value'],1)

    def test_monroe_plate_and_hold_down_families_are_selected(self):
        plate=element('host/structural:plate',category='Structural Connections',
                      family='BIMSF-Plate1',type='16 GA. 3"x4" Plate')
        hold=element('host/structural:hold',category='Structural Connections',
                     family='CF_SHD15S_3d_Cad_MULT_Prod',type='CF_SHD15S_3d_Cad_MULT_Prod')
        plate['sourceKey']=hold['sourceKey']='host/structural'
        mapped,_=map_model([plate,hold])
        self.assertEqual(mapped['PAN-002']['value'],1)
        self.assertEqual(mapped['PAN-013']['value'],1)

    def test_quad_outlet_uses_standard_cover_class(self):
        from model_takeoff_rules import outlet_class
        quad=element(category='Electrical Fixtures',family='Neovi_EF-Outlet_Horizontal',
                     type='Quad_Outlet_Cutout @ 44"')
        self.assertEqual(outlet_class(quad),'FIN-058')

    def opening_fixture(self, function=1):
        def p(name,value,spec='length',scope='type'):
            return dict(name=name,scope=scope,hasValue=True,doubleValue=value,dataType='autodesk.spec.aec:'+spec+'-2.0.0')
        wall=element(category='Walls',family='Basic Wall',type='Stud_6',uniqueId='wall')
        wall['parameters']=[p('Function',function),p('Length',10,scope='instance')]
        door=element('host:door',category='Doors',family='Door',type='Door',hostUniqueId='wall')
        door['parameters']=[p('Function',0),p('Rough Width',3),p('Rough Height',7)]
        return wall,door

    def test_host_wall_classification_drives_flashing(self):
        wall,door=self.opening_fixture(1);out={}
        add_opening_rules([wall,door],out)
        self.assertEqual(out['FIN-083']['value'],17)
        self.assertEqual(out['FIN-082']['value'],1)

    def test_trim_counts_interior_twice_exterior_once(self):
        wall,door=self.opening_fixture(0);out={}
        extra=add_opening_rules([wall,door],out)
        self.assertEqual(extra['supplemental']['WALL-TRIM']['value'],20)
        wall['parameters'][0]['doubleValue']=1
        self.assertEqual(add_opening_rules([wall,door],{})['supplemental']['WALL-TRIM']['value'],10)

    def test_missing_opening_dimension_never_returns_partial_flashing(self):
        wall,door=self.opening_fixture(1);door['parameters']=door['parameters'][:-1];out={}
        add_opening_rules([wall,door],out)
        self.assertNotIn('FIN-083',out)

    def test_missing_measurement_blocks_partial_sum(self):
        out={}; a=element(); b=element('host:b')
        measured(out,'X',[a,b],lambda e:12 if e['key']=='host:a' else None,'sum','test')
        self.assertNotIn('X',out)

    def test_duplicate_instances_count_once(self):
        a=element();out={}
        measured(out,'X',[a,a],lambda e:1,'count','test')
        self.assertEqual(out['X']['value'],1)

    def test_conflicting_duplicate_rejected(self):
        a=element();b=element();b['type']='different'
        with self.assertRaises(ValueError):select_unique([a,b])

    def test_demolished_and_options_excluded(self):
        a=element(); b=element('host:b'); b['phaseDemolished']='New Construction'
        c=element('host:c'); c['designOption']='Option A'
        self.assertEqual(select_unique([a,b,c]),[a])

    def test_dimension_units_and_ambiguity(self):
        e=element(); p=dict(name='Length',scope='instance',hasValue=True,doubleValue=12,dataType='autodesk.spec.aec:area-2.0.0')
        e['parameters']=[p];self.assertIsNone(parameter(e,'Length','length'))
        p['dataType']='autodesk.spec.aec:length-2.0.0';self.assertEqual(parameter(e,'Length','length'),12)
        e['parameters']=[p,p];self.assertIsNone(parameter(e,'Length','length'))

    def test_high_amp_exterior_is_not_counted_twice(self):
        e=element(category='Electrical Fixtures',family='Neovi_EF-Outlet_Horizontal',type='220V 30 AMP_Outlet_Cutout - Exterior')
        self.assertEqual(outlet_class(e),'FIN-059')

    def test_stacked_outlets_produce_two_covers(self):
        e=element(category='Electrical Fixtures',family='Neovi_EF-Outlet_Horizontal',type='Regular_Outlet_Cutout Stacked')
        out={};add_extended_rules([e],out)
        self.assertEqual(out['FIN-058']['value'],2)
        self.assertEqual(out['FIN-058']['status'],'DERIVED_ALLOWANCE')

    def test_unknown_outlet_type_not_assumed(self):
        e=element(category='Electrical Fixtures',family='Neovi_EF-Outlet_Horizontal',type='Unspecified')
        self.assertIsNone(outlet_class(e))

    def test_room_phase_parameter(self):
        e=element(category='Rooms');e['phaseCreated']=''
        e['parameters']=[dict(name='Phase',hasValue=True,displayValue='New Construction')]
        self.assertEqual(select_unique([e]),[e])

if __name__=='__main__':unittest.main()
