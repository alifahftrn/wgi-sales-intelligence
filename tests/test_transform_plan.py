import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml
from etl.quality.demo import create_demo
from etl.quality.validator import read_run
from etl.transform.plan_engine import CONFIG, preview, run_preview, monthly_metrics

class TransformPlanTests(unittest.TestCase):
    def setUp(self):
        t=TemporaryDirectory(); self.addCleanup(t.cleanup); self.root=Path(t.name)
        self.run=create_demo(self.root); self.canonical=self.root/'canonical_v2'; self.data=read_run(self.canonical,self.run)
        self.observed=datetime.fromisoformat('2026-11-25T10:00:00+07:00'); self.config=yaml.safe_load(CONFIG.read_text())
    def result(self,cutoff=None): return preview(self.data,self.observed,cutoff or self.observed,self.config)
    def test_demo(self):
        r=self.result(); s=r['summary']; self.assertEqual((s['asp_internal_rows'],s['asp_external_rows'],s['forecast_history_rows'],s['forecast_latest_rows'],s['monthly_metric_rows']),(1,1,3,1,6))
        self.assertFalse(r['load_ready']); self.assertEqual(s['actual_pack'],290)
        a=r['achievement'][-1]; self.assertEqual(a['asp_internal_achievement_pct']['pack'],'90.00'); self.assertEqual(a['asp_external_achievement_pct']['pack'],'75.00'); self.assertEqual(a['forecast_latest_achievement_pct']['pack'],'94.74'); self.assertEqual(a['asp_internal_prorata_achievement_pct']['pack'],'108.00')
        w=[w for w in r['wape'] if w['bulan']=='2026-11-01' and w['metric']=='liter'][0]; self.assertEqual(w['wape_pct'],'5.56'); self.assertTrue(w['provisional'])
    def test_cutoff_carry_forward(self):
        r=self.result(datetime.fromisoformat('2026-11-05T00:00:00+07:00')); self.assertEqual(len(r['forecast_history']),3); self.assertEqual([x['qty_pack'] for x in r['monthly_metrics'] if x['jenis_metrik']=='FORECAST_LATEST'],[100]); self.assertEqual(r['summary']['actual_pack'],290)
        r=self.result(datetime.fromisoformat('2026-11-02T00:00:00+07:00')); self.assertEqual([x['qty_pack'] for x in r['monthly_metrics'] if x['jenis_metrik']=='FORECAST_LATEST'],[110])
    def test_growth(self):
        g=[g for g in self.result()['growth'] if g['bulan']=='2026-11-01']; self.assertEqual(len(g),2); self.assertTrue(all(x['growth_pct']['pack']=='-10.00' and x['mode']=='SAME_ELAPSED_DAYS' for x in g))
    def test_same_elapsed_excludes_later_prior_delivery(self):
        self.data['delivery_order'][1]['tanggal_do']='2026-10-30'; g=[g for g in self.result()['growth'] if g['bulan']=='2026-11-01' and g['comparison']=='MOM'][0]; self.assertIsNone(g['growth_pct']['pack'])
    def test_no_transactions(self):
        for t in self.data:
            if t not in ('produk','distributor','harga_produk'): self.data[t]=[]
        r=self.result(); self.assertEqual(r['monthly_metrics'],[]); self.assertEqual(r['wape'],[])
    def test_missing_actual_is_not_zero(self):
        for t in ('purchase_order','purchase_order_detail','delivery_order','delivery_order_detail'): self.data[t]=[]
        r=self.result(); self.assertIsNone(r['achievement'][0]['asp_internal_achievement_pct']['pack']); self.assertTrue(all(x['wape_pct'] is None for x in r['wape']))
    def test_wape_absolute_before_rollup(self):
        base=dict(source_system='MYSQL',bulan='2026-10-01',kode_distributor='1')
        rows=[dict(base,kode_produk=p,jenis_metrik=k,qty_pack=q,total_liter=str(q),total_rupiah=str(q)) for p,k,q in [('1','ACTUAL',100),('1','FORECAST_LATEST',90),('2','ACTUAL',100),('2','FORECAST_LATEST',110)]]
        _,w=monthly_metrics(rows,self.observed.date()); self.assertTrue(all(x['wape_pct']=='10.00' for x in w))
    def test_future_cutoff_and_unzoned_rejected(self):
        for t in ('2026-11-26T00:00:00+07:00','2026-11-24T00:00:00'):
            with self.assertRaises(ValueError): self.result(datetime.fromisoformat(t))
    def test_persist_separate(self):
        r,p=run_preview(self.canonical,self.root/'out',self.run,True); self.assertTrue(r['synthetic']); self.assertTrue((p/'preview.json').is_file()); self.assertFalse(r['load_ready'])
        with self.assertRaises(ValueError): run_preview(self.canonical,self.root/'out',self.run,True)
        _,q=run_preview(self.canonical,self.root/'out',self.run,True,datetime.fromisoformat('2026-11-05T00:00:00+07:00')); self.assertNotEqual(p,q)
