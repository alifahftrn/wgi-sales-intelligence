import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch
from etl.manual_jobs import Journal, BusyError, execute_job, launch

RUN_ID = '20261125T011526Z_fe5b47a2'

class ManualJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.j = Journal(self.root)

    def test_empty_read_does_not_create(self):
        self.assertEqual(self.j.history(), [])
        self.assertFalse(self.j.path.exists())

    def test_reserve_and_claim_once(self):
        job = self.j.reserve('PREVIEW', 1)
        self.assertEqual(self.j.claim(job), 'PREVIEW')
        self.assertIsNone(self.j.claim(job))
        self.assertEqual(self.j.history()[0]['actor_id'], 1)
        with self.assertRaises(BusyError): self.j.reserve('APPLY', 2)

    def test_concurrent_reservations(self):
        def attempt(i):
            try: return self.j.reserve('PREVIEW', i)
            except BusyError: return None
        with ThreadPoolExecutor(max_workers=5) as pool:
            jobs = list(pool.map(attempt, range(1,6)))
        self.assertEqual(sum(j is not None for j in jobs), 1)

    def test_pipeline_lock_blocks(self):
        (self.root / '.pipeline.lock').mkdir()
        with self.assertRaises(BusyError): self.j.reserve('PREVIEW', 1)
        self.assertFalse(self.j.path.exists())

    def test_invalid_input(self):
        for mode, actor in [('bad',1), ('APPLY',0), ('PREVIEW',True)]:
            with self.assertRaises(ValueError): self.j.reserve(mode, actor)

    def run_mode(self, mode, outcome):
        job = self.j.reserve(mode, 7)
        def run(*, apply, stdout):
            self.assertEqual(apply, mode == 'APPLY')
            stdout.write('EXTRACT | START\n')
            stdout.write(f'EXTRACT | OK | run-id={RUN_ID} | rows=5\n')
            stdout.write('MAPPING | OK\n')
            stdout.write('raw secret should not persist\n')
            stdout.write(f'{outcome} | run-id={RUN_ID} | source_coverage=NOT_VERIFIED\n')
        self.assertTrue(execute_job(self.j, job, run))
        row = self.j.history()[0]
        self.assertEqual((row['status'], row['run_id'], row['outcome']), ('SUCCESS',RUN_ID,outcome))
        self.assertNotIn('raw secret', str(row))
        self.assertIsNotNone(row['finished'])
        self.assertFalse(execute_job(self.j, job, Mock(side_effect=AssertionError)))
        self.j.reserve('PREVIEW', 1)

    def test_preview(self): self.run_mode('PREVIEW','ETL_PREVIEW_ONLY')
    def test_apply(self): self.run_mode('APPLY','ETL_APPLIED')

    def test_failure_does_not_expose_exception(self):
        job = self.j.reserve('APPLY', 1)
        self.assertFalse(execute_job(self.j, job, Mock(side_effect=RuntimeError('secret text'))))
        row = self.j.history()[0]
        self.assertEqual(row['status'], 'FAILED')
        self.assertNotIn('secret text', str(row))
        self.j.reserve('PREVIEW', 2)

    def test_unconfirmed_outcome(self):
        job = self.j.reserve('APPLY', 1)
        self.assertFalse(execute_job(self.j, job, Mock()))
        self.assertEqual(self.j.history()[0]['reason'], 'OUTCOME_UNCONFIRMED_CHECK_ETL_LOG')

    @patch('etl.manual_jobs.subprocess.Popen', side_effect=OSError('private error'))
    def test_launch_failure(self, popen):
        with self.assertRaises(OSError): launch(self.j, self.root, 'PREVIEW', 1)
        self.assertEqual(self.j.history()[0]['reason'], 'WORKER_START_FAILED')
        self.j.reserve('APPLY', 1)

    @patch('etl.manual_jobs.threading.Thread')
    @patch('etl.manual_jobs.subprocess.Popen')
    def test_launch_argv(self, popen, thread):
        job = launch(self.j, self.root, 'APPLY', 1)
        args, kwargs = popen.call_args
        self.assertEqual(args[0][-3:], ['run_manual_etl','--job-id',job])
        self.assertFalse(kwargs['shell'])
        self.assertEqual(self.j.history()[0]['status'], 'PENDING')

    def test_recovery_is_explicit(self):
        job = self.j.reserve('APPLY', 1)
        self.j.claim(job)
        lock = self.root / '.pipeline.lock'; lock.mkdir()
        with self.assertRaises(BusyError): self.j.interrupt(job)
        lock.rmdir()
        self.assertTrue(self.j.interrupt(job))
        self.assertEqual(self.j.history()[0]['status'], 'INTERRUPTED')
        self.assertFalse(self.j.interrupt(job))
        self.j.reserve('PREVIEW', 1)
