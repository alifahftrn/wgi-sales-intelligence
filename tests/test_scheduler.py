from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import unittest
from etl.scheduler import Scheduler, due_slot, WIB
from etl.manual_jobs import Journal

NOW = datetime(2026,11,26,0,0,30,tzinfo=WIB)
RUN_ID = '20261125T170030Z_1234abcd'

class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = Scheduler(self.root)
    def configure(self, clock='00:00', mode='PREVIEW', enabled=True, confirm=False):
        self.s.configure(enabled=enabled, clock=clock, mode=mode, confirm_apply=confirm)
    def fake(self, *,apply,stdout):
        stdout.write('EXTRACT | OK | run-id='+RUN_ID+' | rows=15\n')
        stdout.write('FACTS | OK\n')
        stdout.write(('ETL_APPLIED' if apply else 'ETL_PREVIEW_ONLY')+' | run-id='+RUN_ID+' | x=y\n')
    def test_default_read_only(self):
        self.assertEqual(self.s.status()[0]['enabled'],0)
        self.assertEqual(self.s.tick(self.fake,NOW),'DISABLED')
        self.assertFalse(self.s.path.exists())
    def test_config_validation(self):
        for clock in ('24:00','0:00','00:60'):
            with self.assertRaises(ValueError): self.configure(clock=clock)
        with self.assertRaises(ValueError): self.configure(mode='APPLY')
        self.configure(mode='APPLY',confirm=True)
        self.assertEqual(self.s.status()[0]['mode'],'APPLY')
    def test_timezone_and_window(self):
        self.configure(); config,_ = self.s.status()
        self.assertEqual(due_slot(config,NOW.astimezone(timezone.utc)), '2026-11-26')
        self.assertIsNone(due_slot(config,NOW+timedelta(minutes=5)))
        self.assertIsNone(due_slot(config,NOW-timedelta(minutes=1)))
        with self.assertRaises(ValueError): due_slot(config,NOW.replace(tzinfo=None))
    def test_midnight_crossing(self):
        self.configure(clock='23:59')
        self.assertEqual(due_slot(self.s.status()[0],NOW),'2026-11-25')
    def test_preview_and_persistence(self):
        self.configure(); self.assertEqual(self.s.tick(self.fake,NOW),'SUCCESS')
        j=Scheduler(self.root).status()[1][0]
        self.assertEqual((j['mode'],j['status'],j['run_id'],j['stage'],j['outcome']),('PREVIEW','SUCCESS',RUN_ID,'FACTS','ETL_PREVIEW_ONLY'))
        self.assertEqual(Scheduler(self.root).tick(self.fake,NOW),'ALREADY_ATTEMPTED')
    def test_apply(self):
        self.configure(mode='APPLY',confirm=True); self.assertEqual(self.s.tick(self.fake,NOW),'SUCCESS')
        self.assertEqual(self.s.status()[1][0]['outcome'],'ETL_APPLIED')
    def test_shared_lock(self):
        self.configure(); (self.root/'.pipeline.lock').mkdir()
        self.assertEqual(self.s.tick(self.fake,NOW),'BUSY')
        self.assertEqual(self.s.status()[1],[])
        (self.root/'.pipeline.lock').rmdir(); self.assertEqual(self.s.tick(self.fake,NOW),'SUCCESS')
    def test_manual_pending(self):
        self.configure(); j=Journal(self.root); job=j.reserve('PREVIEW',1)
        self.assertEqual(self.s.tick(self.fake,NOW),'BUSY')
        j.finish(job,'FAILED',expected='PENDING'); self.assertEqual(self.s.tick(self.fake,NOW),'SUCCESS')
    def test_concurrent_claim(self):
        self.configure()
        with ThreadPoolExecutor(max_workers=2) as p:
            states=list(p.map(lambda _:Scheduler(self.root).claim(NOW)[0],range(2)))
        self.assertCountEqual(states,['CLAIMED','ACTIVE_OR_INTERRUPTED'])
    def test_failed_no_retry_or_secret(self):
        self.configure()
        def fail(**kwargs): raise RuntimeError('private password')
        self.assertEqual(self.s.tick(fail,NOW),'FAILED')
        self.assertNotIn('private',str(self.s.status()))
        self.assertEqual(self.s.tick(self.fake,NOW),'ALREADY_ATTEMPTED')
    def test_unconfirmed_outcome(self):
        self.configure(); self.assertEqual(self.s.tick(lambda **kw:None,NOW),'FAILED')
    def test_recovery_requires_confirmation(self):
        self.configure(); self.s.claim(NOW)
        self.assertEqual(self.s.tick(self.fake,NOW+timedelta(days=1)),'ACTIVE_OR_INTERRUPTED')
        with self.assertRaises(ValueError): self.s.recover('2026-11-26')
        (self.root/'.pipeline.lock').mkdir()
        with self.assertRaises(ValueError): self.s.recover('2026-11-26',confirmed=True)
        (self.root/'.pipeline.lock').rmdir()
        self.assertTrue(self.s.recover('2026-11-26',confirmed=True))
        self.assertEqual(self.s.tick(self.fake,NOW),'ALREADY_ATTEMPTED')
    def test_schedule_change_and_next_day(self):
        self.configure(); self.s.tick(self.fake,NOW)
        self.configure(clock='01:00'); self.assertEqual(self.s.tick(self.fake,NOW+timedelta(hours=1)),'ALREADY_ATTEMPTED')
        self.assertEqual(self.s.tick(self.fake,NOW+timedelta(days=1,hours=1)),'SUCCESS')
    def test_disabled(self):
        self.configure(enabled=False); self.assertEqual(self.s.tick(self.fake,NOW),'DISABLED')
