from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
from etl.quality.demo import create_demo
from etl.quality.validator import read_run,validate

class QualityTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root=Path(temp.name)
        self.run=create_demo(self.root); self.canonical=self.root/'canonical_v2'; self.data=read_run(self.canonical,self.run)
    def result(self): return validate(self.data)
    def rules(self): return {i['rule'] for i in self.result()['issues']}
    def test_demo(self):
        r=self.result(); self.assertEqual((r['status'],r['rows'],r['errors'],r['warnings']),('REVIEW',27,0,1)); self.assertFalse(r['load_ready'])
    def test_missing_parent(self):
        self.data['distributor']=[]; self.assertIn('foreign_key:purchase_order.kode_distributor',self.rules())
    def test_overdelivery(self):
        self.data['delivery_order_detail'][0]['qty_pack']=101; self.assertIn('overdelivery',self.rules())
    def test_wrong_order(self):
        self.data['delivery_order_detail'][0]['id_po_detail']='2'; self.assertIn('do_po_mismatch',self.rules())
    def test_duplicate_asp(self):
        self.data['asp_detail'].append(dict(self.data['asp_detail'][0],id_asp_detail='99')); self.assertIn('duplicate_asp',self.rules())
    def test_revision_missing(self):
        self.data['revisi_forecast_detail'][0]['revisi_liter']=None; self.assertIn('revision_incomplete',self.rules())
    def test_cancel_over(self):
        self.data['purchase_order_detail'][2]['qty_batal_pack']=70; self.assertIn('shipped_plus_cancel_exceeds_po',self.rules())
    def test_checksum(self):
        (self.canonical/'mysql'/self.run/'produk.jsonl').write_text('broken');
        with self.assertRaises(ValueError): read_run(self.canonical,self.run)
    def test_no_transactions(self):
        for t in self.data:
            if t not in ('produk','distributor','harga_produk'): self.data[t]=[]
        self.assertEqual((self.result()['status'],self.result()['transaction_rows']),('PASS',0))
