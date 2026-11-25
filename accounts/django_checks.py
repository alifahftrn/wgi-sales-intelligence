"""Django checks with mocked MySQL users; no migrations and no DB writes."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from django.contrib.auth.hashers import make_password
from django.test import SimpleTestCase, RequestFactory, Client
from accounts.backend import EmailBackend
from accounts.middleware import LocalRoleGuard
from accounts.models import User
from django.http import HttpResponse

class AuthenticationTests(SimpleTestCase):
    def test_backend_password(self):
        user = User(id=1, email='test@example.invalid', role='ADMIN', password=make_password('fictional-test-only-password'))
        with patch('accounts.backend.User.objects') as manager:
            manager.using.return_value.filter.return_value.order_by.return_value.__getitem__.return_value = [user]
            self.assertIs(EmailBackend().authenticate(None, username=user.email, password='fictional-test-only-password'), user)
            self.assertIsNone(EmailBackend().authenticate(None, username=user.email, password='wrong'))
            user.role='UNKNOWN'
            self.assertIsNone(EmailBackend().authenticate(None, username=user.email, password='fictional-test-only-password'))
    def test_duplicates_denied(self):
        with patch('accounts.backend.User.objects') as manager:
            manager.using.return_value.filter.return_value.order_by.return_value.__getitem__.return_value = [object(), object()]
            self.assertIsNone(EmailBackend().authenticate(None, username='test@example.invalid', password='fictional-test-only-password'))
    def test_legacy_plaintext_denied(self):
        user=User(id=1, email='test@example.invalid',role='ADMIN',password='legacy-plaintext')
        with patch('accounts.backend.User.objects') as manager:
            manager.using.return_value.filter.return_value.order_by.return_value.__getitem__.return_value = [user]
            self.assertIsNone(EmailBackend().authenticate(None, username=user.email, password='legacy-plaintext'))
    def test_unauthenticated_monitor_redirect(self):
        with self.settings(DEBUG=True):
            self.assertRedirects(Client().get('/etl/monitoring/'), '/accounts/login/', fetch_redirect_response=False)
    def test_csrf_required(self):
        with self.settings(DEBUG=True):
            response=Client(enforce_csrf_checks=True).post('/accounts/login/', {'email':'test@example.invalid','password':'fictional'})
            self.assertEqual(response.status_code,403)
    def test_role_guard(self):
        guard=LocalRoleGuard(lambda request: HttpResponse('ok'))
        with self.settings(DEBUG=True):
            req=RequestFactory().get('/etl/monitoring/')
            req.resolver_match=SimpleNamespace(view_name='etl_monitor_v1')
            for role, expected in [('SALES',403),('BOD',403),('ADMIN',None),('unknown',403)]:
                req.user=SimpleNamespace(is_authenticated=True,role=role)
                response=guard.process_view(req,lambda request:None,(),{})
                self.assertEqual(response.status_code if response is not None else None,expected)
            req.META['REMOTE_ADDR']='192.168.1.5'
            self.assertEqual(guard.process_view(req,lambda request:None,(),{}).status_code,403)
