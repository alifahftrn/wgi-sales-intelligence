import unittest
from accounts.policy import normalize_role, allowed_role, can_access_etl, local_development

class AuthPolicyTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_role(' admin '), 'ADMIN')
    def test_three_roles(self):
        self.assertTrue(all(allowed_role(r) for r in ('ADMIN','SALES','BOD')))
    def test_unknown_denied(self):
        self.assertTrue(all(not allowed_role(r) for r in (None,'','manager','superadmin')))
    def test_admin_only(self):
        self.assertTrue(can_access_etl('Admin'))
        self.assertFalse(can_access_etl('BOD'))
        self.assertFalse(can_access_etl('SALES'))
    def test_loopback(self):
        self.assertTrue(local_development(True,'127.0.0.1'))
        self.assertTrue(local_development(True,'::1'))
    def test_nonlocal_and_production_denied(self):
        self.assertFalse(local_development(True,'192.168.0.1'))
        self.assertFalse(local_development(False,'127.0.0.1'))
