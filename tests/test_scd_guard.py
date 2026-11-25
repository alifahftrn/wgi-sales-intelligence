import unittest
from unittest.mock import Mock
from etl.load.dimensions import execute

class SCDGuardTests(unittest.TestCase):
    def test_default_rejects_test_database(self):
        c=Mock(); c.fetchone.return_value=('sales_datamart_scd_test',)
        with self.assertRaises(ValueError): execute(c,{},True)
        self.assertEqual(c.execute.call_count,1)
    def test_test_mode_rejects_main_database(self):
        c=Mock(); c.fetchone.return_value=('sales_datamart',)
        with self.assertRaises(ValueError): execute(c,{},True,test_only=True)
        self.assertEqual(c.execute.call_count,1)
    def test_test_mode_accepts_only_dedicated_database(self):
        c=Mock(); c.fetchone.side_effect=[('sales_datamart_scd_test',),None,(None,)]; c.fetchall.side_effect=[[],[]]
        from tests.test_load_dimensions import LoadDimensionsTests
        self.assertEqual(execute(c,LoadDimensionsTests().prepared(),test_only=True)['planned_writes'],2)
