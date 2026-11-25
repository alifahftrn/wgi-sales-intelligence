from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock
from etl.monitoring import scheduler_attempts, summarize_db_row, read_database

STAMP = '20261125T063830709Z_e26dec79'
START = 'START | mode=APPLY | utc=2026-11-25T06:38:30.7090000Z\n'
END = 'SUCCESS | exit_code=0 | utc=2026-11-25T06:38:33.7090000Z\n'
RUN = '20261125T063303Z_e7a2c2f6'

class MonitoringTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def make(self, content, output='', err=''):
        (self.root/(STAMP+'.status.txt')).write_text(content,encoding='utf-8-sig')
        (self.root/(STAMP+'.stdout.log')).write_text(output,encoding='utf-8')
        (self.root/(STAMP+'.stderr.log')).write_text(err,encoding='utf-8')
        return scheduler_attempts(self.root)[0]
    def test_success(self):
        r=self.make(START+END, f'EXTRACT | OK | run-id={RUN}\nETL_APPLIED | run-id={RUN} | source_coverage=NOT_VERIFIED\n')
        self.assertEqual((r['status'],r['mode'],r['run_id'],r['exit_code']),('SUCCESS','APPLY',RUN,0))
        self.assertFalse(r['stderr_present']); self.assertIn(('EXTRACT','OK'),r['stages'])
    def test_failed_redacted(self):
        r=self.make(START+'FAILED | exit_code=1 | utc=2026-11-25T06:38:33Z | secret\n','secret','password')
        self.assertEqual(r['status'],'FAILED'); self.assertTrue(r['stderr_present']); self.assertNotIn('secret',str(r)); self.assertNotIn('password',str(r))
    def test_incomplete(self):
        self.assertEqual(self.make(START)['status'],'NO_FINAL_STATUS')
    def test_bad_status(self):
        self.assertEqual(self.make(START+END.replace('exit_code=0','exit_code=1'))['status'],'UNKNOWN')
    def test_missing(self):
        self.assertEqual(scheduler_attempts(self.root/'missing'),[])
    def test_ignore_untrusted_names(self):
        (self.root/'password.status.txt').write_text(START+END)
        self.assertEqual(scheduler_attempts(self.root),[])
    def test_db_row(self):
        now=datetime.now(timezone.utc)
        r=summarize_db_row((1,'DIM_V1:'+RUN,now,now,now,'PARTIAL',10,0,0))
        self.assertEqual((r['stage'],r['run_id'],r['rows_written'],r['duration']),('DIMENSIONS',RUN,0,0))
    def test_db_queries(self):
        c=Mock(); c.fetchall.return_value=[]; c.fetchone.return_value=None
        self.assertEqual(read_database(c),([],None))
        self.assertEqual(c.execute.call_count,2)
        for call in c.execute.call_args_list:
            self.assertTrue(call.args[0].startswith('SELECT'))
