import unittest
from copy import deepcopy
from unittest.mock import Mock
from etl.load.fact_writer import execute, transitions, ORDER, HISTORY, MONTH, SNAP
from etl.load.fact_planner import build_plan
from tests import test_fact_planner

class FactWriterTests(unittest.TestCase):
    def setUp(self):
        base=test_fact_planner.FactPlannerTests(); base.setUp(); self.addCleanup(base.doCleanups)
        self.plan,self.summary=base.plan()
        self.old_order=deepcopy(self.plan[ORDER]); self.old_history=deepcopy(self.plan[HISTORY]); self.old_asp=deepcopy([r for r in self.plan[MONTH] if r['jenis_metrik'].startswith('ASP_')])
    def changes(self): return transitions(self.plan,self.old_order,self.old_history,self.old_asp)
    def test_initial(self):
        o,h=transitions(self.plan,[],[],[]); self.assertEqual((len(o),len(h)),(7,3))
    def test_unchanged(self): self.assertEqual(self.changes(),([],[]))
    def test_order_correction(self):
        self.plan[ORDER][-1]['qty_pack']+=1; self.assertEqual(len(self.changes()[0]),1)
    def test_missing_order(self):
        self.plan[ORDER].pop(); self.assertRaisesRegex(ValueError,'identitas lama hilang',self.changes)
    def test_immutable_forecast(self):
        self.plan[HISTORY][0]['qty_pack']+=1; self.assertRaisesRegex(ValueError,'forecast immutable',self.changes)
    def test_immutable_asp(self):
        next(r for r in self.plan[MONTH] if r['jenis_metrik']=='ASP_INTERNAL')['qty_pack']+=1
        self.assertRaisesRegex(ValueError,'ASP immutable',self.changes)
    def test_missing_forecast(self):
        self.plan[HISTORY].pop(); self.assertRaisesRegex(ValueError,'identitas lama hilang',self.changes)
    def test_main_guard(self):
        c=Mock(); c.fetchone.return_value=('sales_datamart_scd_test',)
        self.assertRaises(ValueError,execute,c,{},True); self.assertEqual(c.execute.call_count,1)
    def test_test_guard(self):
        c=Mock(); c.fetchone.return_value=('sales_datamart',)
        self.assertRaises(ValueError,execute,c,{},True,test_only=True); self.assertEqual(c.execute.call_count,1)
    def test_idempotency(self):
        from datetime import datetime,timezone
        p=dict(run_id='x',digest='abc',cutoff=datetime.now(timezone.utc)); c=Mock()
        c.fetchone.side_effect=[('sales_datamart',),('SUCCESS','canonical_v2/mysql/x#sha256=abc',p['cutoff'])]
        self.assertEqual(execute(c,p,True)['status'],'ALREADY_APPLIED')
