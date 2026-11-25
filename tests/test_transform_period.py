import unittest
from datetime import date,datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from etl.quality.demo import create_demo
from etl.quality.validator import read_run
from etl.transform.period_engine import period_bounds,windows,period_preview,run_preview

class TransformPeriodTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root=Path(temp.name)
        self.run=create_demo(self.root); self.canonical=self.root/'canonical_v2'; self.data=read_run(self.canonical,self.run)
        self.observed=datetime.fromisoformat('2026-11-25T10:00:00+07:00')
    def report(self,**query):
        return period_preview(self.data,self.observed,self.observed,**query)
    def test_month_yoy_elapsed(self):
        r=self.report(kind='month',year=2026,index=11)
        self.assertEqual(r['current']['end'],'2026-11-25'); self.assertEqual(r['reference']['end'],'2025-11-25')
        self.assertEqual(r['current']['actual']['pack'],'90.000000'); self.assertEqual(r['growth_pct']['pack'],'-10.00')
        self.assertEqual(r['current']['asp']['ASP_INTERNAL']['achievement_pct']['pack'],'108.00')
        self.assertEqual(r['current']['asp']['ASP_EXTERNAL']['achievement_pct']['pack'],'90.00')
    def test_qoq_missing_reference(self):
        r=self.report(kind='quarter',year=2026,index=4,compare='previous')
        self.assertEqual(r['current']['actual']['pack'],'190.000000'); self.assertEqual(r['reference']['start'],'2026-07-01'); self.assertEqual(r['reference']['end'],'2026-08-25')
        self.assertIsNone(r['growth_pct']['pack']); self.assertIsNone(r['current']['asp']['ASP_INTERNAL']['achievement_pct']['pack'])
    def test_ytd(self):
        r=self.report(kind='ytd',year=2026)
        self.assertEqual(r['current']['actual']['pack'],'190.000000'); self.assertEqual(r['reference']['actual']['pack'],'100.000000'); self.assertEqual(r['growth_pct']['pack'],'90.00')
        self.assertEqual(r['source_coverage'],'NOT_VERIFIED'); self.assertIsNone(r['current']['asp']['ASP_INTERNAL']['achievement_pct']['pack'])
    def test_custom_exact_do_dates_and_prorata(self):
        r=self.report(kind='custom',start=date(2026,11,2),end=date(2026,11,2),compare='none')
        self.assertEqual(r['current']['actual']['pack'],'40.000000'); self.assertEqual(r['current']['asp']['ASP_INTERNAL']['prorata_target']['pack'],'3.333333'); self.assertEqual(r['current']['asp']['ASP_INTERNAL']['achievement_pct']['pack'],'1200.00'); self.assertIsNone(r['reference'])
    def test_filter_combination(self):
        r=self.report(kind='month',year=2026,index=11,filters={'product':'99001','distributor':'99001','region':'Region 1','area':'Jawa','brand':'DEMO'})
        self.assertEqual(r['current']['actual']['pack'],'90.000000')
        r=self.report(kind='month',year=2026,index=11,filters={'product':'99001','region':'Region 2'})
        self.assertIsNone(r['current']['actual']['pack']); self.assertIsNone(r['growth_pct']['pack'])
    def test_full_vs_elapsed(self):
        self.data['delivery_order'][1]['tanggal_do']='2026-10-30'
        q=dict(kind='month',year=2026,index=11,compare='previous')
        r=self.report(**q); self.assertIsNone(r['reference']['actual']['pack'])
        r=self.report(**q,mode='full'); self.assertEqual(r['reference']['end'],'2026-10-31'); self.assertEqual(r['growth_pct']['pack'],'-10.00')
    def test_leap_and_completed_month(self):
        self.assertEqual(period_bounds('month',2024,2),(date(2024,2,1),date(2024,2,29)))
        c,r=windows('month',(date(2024,3,1),date(2024,3,31)),date(2024,3,30),'previous','elapsed')
        self.assertEqual(c[1],date(2024,3,29)); self.assertEqual(r[1],date(2024,2,29))
        c,r=windows('month',(date(2024,3,1),date(2024,3,31)),date(2024,4,1),'previous','elapsed')
        self.assertEqual(c[1],date(2024,3,31)); self.assertEqual(r[1],date(2024,2,29))
    def test_semester_and_year(self):
        self.assertEqual(period_bounds('semester',2026,2),(date(2026,7,1),date(2026,12,31)))
        self.assertEqual(period_bounds('year',2026),(date(2026,1,1),date(2026,12,31)))
    def test_invalid_query(self):
        for q in [dict(kind='quarter',year=2026,index=5),dict(kind='month',year=2027,index=1),dict(kind='custom',start=date(2026,11,3),end=date(2026,11,2)),dict(kind='month',year=2026,index=11,filters={'bad':'x'})]:
            with self.assertRaises(ValueError): self.report(**q)
    def test_empty_source(self):
        for t in self.data:
            if t not in ('produk','distributor','harga_produk'): self.data[t]=[]
        r=self.report(kind='month',year=2026,index=11); self.assertIsNone(r['current']['actual']['pack']); self.assertIsNone(r['current']['asp']['ASP_INTERNAL']['prorata_target']['pack'])
    def test_persist_and_no_overwrite(self):
        q=dict(kind='month',year=2026,index=11)
        r,p=run_preview(self.canonical,self.root/'out',self.run,True,**q)
        self.assertTrue(r['synthetic']); self.assertFalse(r['load_ready']); self.assertTrue((p/'preview.json').is_file())
        with self.assertRaises(ValueError): run_preview(self.canonical,self.root/'out',self.run,True,**q)
        _,p2=run_preview(self.canonical,self.root/'out',self.run,True,compare='previous',**q); self.assertNotEqual(p,p2)
