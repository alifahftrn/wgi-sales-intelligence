import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock
from etl.load.dimensions import prepare, plan_table, execute
from etl.quality.demo import create_demo
from etl.mapping.full_engine import map_full_run
from etl.quality.validator import read_run

T=datetime(2026,1,1,tzinfo=timezone.utc)
P={'kode_produk':'001','kode_apc_lama':None,'nama_produk':'Produk','brand':'B','jenis_produk':'2W','segment':'Top','kemasan_liter':'0.800','isi_karton':12,'liter_per_karton':'9.600'}
D={'kode_distributor':'001','nama_distributor':'D','area':'Jawa','region':'Region 1','wilayah':'W'}

def old(p=P,start=T,end=None):
    return {**p,'id_produk_versi':1,'berlaku_mulai':start,'berlaku_sampai':end,'aktif':end is None}

class LoadDimensionsTests(unittest.TestCase):
    def test_initial(self):
        self.assertEqual(plan_table('produk',[P],[],T)[0][0],'insert')
    def test_unchanged_decimal(self):
        self.assertEqual(plan_table('produk',[P],[old({**P,'kemasan_liter':'0.8'})],T)[0][0],'unchanged')
    def test_changed(self):
        a=plan_table('produk',[{**P,'brand':'C'}],[old()],T+timedelta(days=1))[0]
        self.assertEqual((a[0],a[3]),('version',1))
    def test_same_timestamp_change(self):
        with self.assertRaises(ValueError): plan_table('produk',[{**P,'brand':'C'}],[old()],T)
    def test_old_snapshot(self):
        with self.assertRaises(ValueError): plan_table('produk',[P],[old()],T-timedelta(days=1))
    def test_overlap(self):
        with self.assertRaises(ValueError): plan_table('produk',[P],[old(end=T+timedelta(days=2)),old(start=T+timedelta(days=1))],T+timedelta(days=3))
    def test_missing_code(self):
        with self.assertRaises(ValueError): plan_table('produk',[{**P,'kode_produk':'002'}],[old()],T)
    def test_no_active(self):
        with self.assertRaises(ValueError): plan_table('produk',[P],[old(end=T+timedelta(days=1))],T+timedelta(days=2))
    def test_demo_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); run=create_demo(root)
            with self.assertRaisesRegex(ValueError,'demo ditolak'): prepare(root/'extracts',root/'canonical_v2',run)
    def test_prepare_and_checksum(self):
        # Test fixture only: label a simulated full source to exercise the real-path gate.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); run=create_demo(root)
            path=root/'extracts'/run/'manifest.json'; m=json.loads(path.read_text()); m.pop('synthetic'); m.update(mode='FULL_EXTRACT',database='salesdashboard'); path.write_text(json.dumps(m))
            map_full_run(root/'extracts',root/'mapped',run)
            p=prepare(root/'extracts',root/'mapped',run)
            self.assertEqual(len(p['data']['produk']),1)
            path.write_text(json.dumps(m)+' ')
            with self.assertRaisesRegex(ValueError,'checksum'): prepare(root/'extracts',root/'mapped',run)
    def cursor(self):
        c=Mock(); c.fetchone.side_effect=[('sales_datamart',),None,(None,)]; c.fetchall.side_effect=[[],[]]; c.rowcount=1; return c
    def prepared(self):
        return {'run_id':'20260101T000000Z_12345678','digest':'a'*64,'cutoff':T,'data':{'produk':[P],'distributor':[D]}}
    def test_dry_run_no_dml(self):
        c=self.cursor(); r=execute(c,self.prepared()); self.assertEqual((r['status'],r['planned_writes']),('DRY_RUN',2))
        self.assertFalse(any(x.args[0].startswith(('INSERT','UPDATE','DELETE')) for x in c.execute.call_args_list))
    def test_apply_sql_shape(self):
        c=self.cursor(); r=execute(c,self.prepared(),apply=True); self.assertEqual(r['rows_written'],2)
        sql=[x.args[0] for x in c.execute.call_args_list]
        self.assertEqual(sum(x.startswith('INSERT') for x in sql),3)
        self.assertTrue(any("status='PARTIAL'" in x and x.startswith('UPDATE') for x in sql))
    def test_idempotent(self):
        p=self.prepared(); c=Mock(); ref=f"canonical_v2/mysql/{p['run_id']}#sha256={p['digest']}"; c.fetchone.side_effect=[('sales_datamart',),('PARTIAL',ref,T)]
        self.assertEqual(execute(c,p,True)['status'],'ALREADY_APPLIED')
        self.assertFalse(any(x.args[0].startswith(('INSERT','UPDATE')) for x in c.execute.call_args_list))
    def test_wrong_database(self):
        c=Mock(); c.fetchone.return_value=('other',)
        with self.assertRaises(ValueError): execute(c,self.prepared(),True)
        self.assertEqual(c.execute.call_count,1)
    def test_stale_run_global(self):
        c=self.cursor(); c.fetchone.side_effect=[('sales_datamart',),None,(T,)]
        with self.assertRaises(ValueError): execute(c,self.prepared(),True)
