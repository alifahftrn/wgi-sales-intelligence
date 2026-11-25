import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from etl.quality.demo import create_demo
from etl.quality.validator import read_run
from etl.transform.order_engine import preview,run_preview,CONFIG
import yaml

class TransformOrderTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root=Path(temp.name)
        self.run=create_demo(self.root); self.canonical=self.root/'canonical_v2'
        self.data=read_run(self.canonical,self.run)
        self.cutoff=datetime(2026,11,25,2,tzinfo=timezone.utc)
        self.config=yaml.safe_load(CONFIG.read_text())
    def result(self): return preview(self.data,self.cutoff,self.config)
    def test_demo(self):
        r=self.result(); s=r['summary']; self.assertEqual((s['po_valid_pack'],s['actual_pack'],s['actual_liter'],s['actual_rupiah']), (370,290,'2784.000','32190000.00'))
        self.assertEqual((s['outstanding_bod_pack'],s['outstanding_eligible_pack'],s['fulfillment_pct']), (80,70,'78.38'))
        self.assertEqual((s['order_rows'],s['monthly_rows'],s['snapshot_rows']), (7,3,3)); self.assertFalse(r['load_ready'])
        self.assertEqual([m['qty_pack'] for m in r['actual_monthly']],[100,100,90])
    def test_no_transactions(self):
        for t in self.data:
            if t not in ('produk','distributor','harga_produk'): self.data[t]=[]
        s=self.result()['summary']; self.assertEqual(s['actual_pack'],0); self.assertIsNone(s['fulfillment_pct']); self.assertEqual(s['monthly_rows'],0)
    def test_unknown_status(self):
        self.data['purchase_order'][0]['status_po']='OTHER'
        with self.assertRaisesRegex(ValueError,'status PO'): self.result()
    def test_inconsistent_status(self):
        self.data['purchase_order'][0]['status_po']='OPEN'
        with self.assertRaisesRegex(ValueError,'tidak konsisten'): self.result()
    def test_cancelled_do_excluded(self):
        self.data['delivery_order'][-1]['status_do']='CANCELLED'
        self.assertEqual(self.result()['summary']['actual_pack'],240)
    def test_full_cancel_excluded(self):
        self.data['delivery_order'][0]['status_do']='CANCELLED'
        self.data['purchase_order'][0]['status_po']='CANCELLED'; self.data['purchase_order_detail'][0]['qty_batal_pack']=100
        s=self.result()['summary']; self.assertEqual((s['po_valid_pack'],s['actual_pack'],s['outstanding_bod_pack']),(270,190,80))
    def test_partial_cancel_all_remaining(self):
        self.data['purchase_order'][2]['status_po']='CANCELLED'; self.data['purchase_order_detail'][2]['qty_batal_pack']=60
        s=self.result()['summary']; self.assertEqual((s['outstanding_bod_pack'],s['outstanding_eligible_pack']),(80,20))
    def test_missing_snapshot(self):
        self.data['purchase_order_detail'][0]['harga_pack_setelah_ppn']=None
        with self.assertRaisesRegex(ValueError,'po_snapshot_incomplete'): self.result()
    def test_overdelivery(self):
        self.data['delivery_order_detail'][0]['qty_pack']=101
        with self.assertRaisesRegex(ValueError,'overdelivery'): self.result()
    def test_future(self):
        self.data['delivery_order'][-1]['tanggal_do']='2027-01-01'
        with self.assertRaisesRegex(ValueError,'melewati'): self.result()
    def test_config(self):
        self.config['steps'].reverse()
        with self.assertRaisesRegex(ValueError,'konfigurasi'): self.result()
    def test_persist(self):
        r,p=run_preview(self.canonical,self.root/'out',self.run,demo=True)
        self.assertTrue(r['synthetic']); self.assertTrue((p/'preview.json').exists()); self.assertEqual(p.parent.name,'demo')
        with self.assertRaisesRegex(ValueError,'sudah ada'): run_preview(self.canonical,self.root/'out',self.run,demo=True)
