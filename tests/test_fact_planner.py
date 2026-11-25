import unittest
from datetime import datetime, date, timedelta
from tempfile import TemporaryDirectory
from etl.quality.demo import create_demo
from etl.quality.validator import read_run
from etl.load.fact_planner import build_plan, report, resolve, index_history, check_calendar, day_window, SPECS, TABLES

class FactPlannerTests(unittest.TestCase):
    def setUp(self):
        t=TemporaryDirectory(); self.addCleanup(t.cleanup); from pathlib import Path
        root=Path(t.name); self.data=read_run(root/'canonical_v2',create_demo(root)); self.cut=datetime.fromisoformat('2026-11-25T10:00:00+07:00')
        self.hist={k:[dict(r,**{pk:1},berlaku_mulai=self.cut,berlaku_sampai=None,aktif=True) for r in self.data[k]] for k,(_,pk,_,_) in SPECS.items()}
    def plan(self): return build_plan(self.data,self.cut,self.hist)
    def test_demo_counts(self):
        p,s=self.plan(); r=report(p,s); self.assertEqual(list(r['counts'].values()),[7,3,6,3]); self.assertEqual(r['actual_pack'],290); self.assertEqual(r['unresolved_version_refs'],38)
    def test_unknown_historical_dimension(self):
        p,_=self.plan(); self.assertTrue(all(r['id_produk_versi'] is None for rows in p.values() for r in rows))
    def test_forecast_ref(self):
        p,_=self.plan(); self.assertEqual([r['forecast_ref'] for r in p[TABLES[2]] if r['jenis_metrik']=='FORECAST_LATEST'],[('REVISI','2')])
    def test_day_boundary(self):
        start,end=day_window('2026-11-25'); r=self.hist['produk'][0]; ix=index_history([r],'id_produk_versi','kode_produk'); self.assertIsNone(resolve(ix,r['kode_produk'],'id_produk_versi',start,end)); self.assertEqual(resolve(ix,r['kode_produk'],'id_produk_versi',self.cut),1)
    def test_actual_group_versions(self):
        r=self.hist['produk'][0]; boundary=datetime.fromisoformat('2026-11-03T00:00:00+07:00'); self.hist['produk']=[dict(r,berlaku_mulai=datetime.fromisoformat('2025-01-01T00:00:00+07:00'),berlaku_sampai=boundary,aktif=False),dict(r,id_produk_versi=2,berlaku_mulai=boundary)]; p,s=self.plan(); a=[r for r in p[TABLES[2]] if r['jenis_metrik']=='ACTUAL' and r['bulan']=='2026-11-01']; self.assertEqual(sorted(r['qty_pack'] for r in a),[40,50]); self.assertEqual(s['actual_pack'],290)
    def test_empty(self):
        for k in self.data:
            if k not in ('produk','distributor','harga_produk'): self.data[k]=[]
        p,s=self.plan(); self.assertEqual([len(x) for x in p.values()],[0]*4)
    def test_calendar(self):
        p,_=self.plan(); with_dates={date.fromisoformat(r[k]) for rows in p.values() for r in rows for k in ('tanggal_po','tanggal_transaksi','tanggal_snapshot','bulan') if k in r}; check_calendar(p,with_dates)
        with self.assertRaises(ValueError): check_calendar(p,set())
    def test_missing_dimension(self):
        self.hist['produk']=[]
        with self.assertRaises(ValueError): self.plan()
