import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from etl.pipeline import pipeline_lock, prepare_run, load_atomic


class PipelineTests(unittest.TestCase):
    def test_lock_release(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                with pipeline_lock(d):
                    with self.assertRaises(ValueError):
                        with pipeline_lock(d): pass
                    raise RuntimeError('test')
            self.assertFalse((Path(d)/'.pipeline.lock').exists())

    def test_bad_run_id(self):
        with self.assertRaises(ValueError): prepare_run('/unused','../bad',extract=Mock())

    @patch('etl.pipeline.load_facts')
    @patch('etl.pipeline.load_dimensions')
    def test_preview_defers_new_dims(self,d,f):
        d.return_value={'status':'DRY_RUN','rows_written':0}
        result=load_atomic(Mock(),{},apply=False)
        self.assertEqual(result['fact_db_check'],'DEFERRED_UNTIL_APPLY'); f.assert_not_called()
        self.assertEqual(d.call_args.args[2],False)

    @patch('etl.pipeline.load_facts')
    @patch('etl.pipeline.load_dimensions')
    def test_preview_existing_dims(self,d,f):
        d.return_value={'status':'ALREADY_APPLIED'}; f.return_value={'status':'DRY_RUN'}
        self.assertEqual(load_atomic(Mock(),{})['fact_db_check'],'COMPLETE')
        self.assertEqual(f.call_args.args[2],False)

    @patch('etl.pipeline.load_facts')
    @patch('etl.pipeline.load_dimensions')
    def test_apply_same_cursor(self,d,f):
        d.return_value={'status':'DIMENSIONS_APPLIED'}; f.return_value={'status':'FACTS_APPLIED'}
        c=Mock(); p={}
        self.assertEqual(load_atomic(c,p,apply=True)['status'],'ETL_APPLIED')
        d.assert_called_once_with(c,p,True,test_only=False); f.assert_called_once_with(c,p,True,test_only=False)

    @patch('etl.pipeline.load_facts')
    @patch('etl.pipeline.load_dimensions')
    def test_repeat(self,d,f):
        d.return_value=f.return_value={'status':'ALREADY_APPLIED'}
        self.assertEqual(load_atomic(Mock(),{},apply=True)['status'],'ETL_ALREADY_APPLIED')

    @patch('etl.pipeline.load_facts')
    @patch('etl.pipeline.load_dimensions')
    def test_fact_failure_propagates(self,d,f):
        d.return_value={'status':'DIMENSIONS_APPLIED'}; f.side_effect=ValueError('failure')
        with self.assertRaisesRegex(ValueError,'failure'): load_atomic(Mock(),{},apply=True)

    @patch('etl.pipeline.load_facts')
    @patch('etl.pipeline.load_dimensions')
    def test_dimension_failure_stops(self,d,f):
        d.side_effect=ValueError('failure')
        with self.assertRaises(ValueError): load_atomic(Mock(),{},apply=True)
        f.assert_not_called()

    @patch('etl.pipeline.map_full_run')
    @patch('etl.pipeline.prepare')
    def test_quarantine_stops(self,p,m):
        m.return_value={'status':'PARTIAL','quarantine':1}
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'quarantine'):
                prepare_run(Path(t)/'extracts','20261125T011526Z_fe5b47a2',extract=Mock())
        p.assert_not_called()

    @patch('etl.pipeline.preview')
    @patch('etl.pipeline.prepare')
    @patch('etl.pipeline.map_full_run')
    def test_resume_existing_mapping(self,m,p,v):
        run='20261125T011526Z_fe5b47a2'
        p.return_value={'data':{},'cutoff':None,'warnings':0}; v.return_value={'summary':{'actual_pack':0,'monthly_metric_rows':0}}
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); (root/'canonical_v2'/'mysql'/run).mkdir(parents=True); extract=Mock()
            self.assertEqual(prepare_run(root/'extracts',run,extract=extract)[0],p.return_value)
            extract.assert_not_called(); m.assert_not_called()

    @patch('etl.pipeline.preview')
    @patch('etl.pipeline.prepare')
    @patch('etl.pipeline.map_full_run')
    def test_fresh_extract(self,m,p,v):
        run='20261125T011526Z_fe5b47a2'; e=Mock(return_value={'run_id':run,'total_rows':15})
        m.return_value={'status':'SUCCESS','quarantine':0,'ready':15}; p.return_value={'data':{},'cutoff':None,'warnings':0}; v.return_value={'summary':{'actual_pack':0,'monthly_metric_rows':0}}
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); prepare_run(root/'extracts',extract=e)
            e.assert_called_once_with(source='mysql'); m.assert_called_once_with(root/'extracts',root/'canonical_v2',run)
