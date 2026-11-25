"""Django endpoint tests; no MySQL/PostgreSQL access."""
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory, Client, override_settings
from etl.manual_views import trigger_manual_etl
from etl.manual_jobs import BusyError

@override_settings(DEBUG=True)
class ManualEndpointTests(SimpleTestCase):
    def request(self, data=None, role='ADMIN', method='post', auth=True):
        req = getattr(RequestFactory(), method)('/etl/manual/run/', data or {})
        req.user = SimpleNamespace(is_authenticated=auth, role=role, pk=42)
        # These unit tests isolate the view; separate client test enforces CSRF.
        req._dont_enforce_csrf_checks = True
        return req

    @patch('etl.manual_views.launch')
    def test_preview(self, launch):
        response = trigger_manual_etl(self.request({'mode':'PREVIEW'}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/etl/monitoring/')
        self.assertEqual(launch.call_args.args[-2:], ('PREVIEW',42))

    @patch('etl.manual_views.launch')
    def test_apply_confirmation(self, launch):
        self.assertEqual(trigger_manual_etl(self.request({'mode':'APPLY'})).status_code,400)
        launch.assert_not_called()
        self.assertEqual(trigger_manual_etl(self.request({'mode':'APPLY','confirm_apply':'yes'})).status_code,302)
        self.assertEqual(launch.call_args.args[-2:], ('APPLY',42))

    @patch('etl.manual_views.launch')
    def test_invalid_role_and_remote(self, launch):
        for role in ('SALES','BOD','UNKNOWN'):
            self.assertEqual(trigger_manual_etl(self.request({'mode':'PREVIEW'},role)).status_code,403)
        self.assertEqual(trigger_manual_etl(self.request({'mode':'PREVIEW'},auth=False)).status_code,403)
        req = self.request({'mode':'PREVIEW'}); req.META['REMOTE_ADDR']='192.168.1.10'
        self.assertEqual(trigger_manual_etl(req).status_code,403)
        launch.assert_not_called()

    @patch('etl.manual_views.launch')
    def test_invalid_mode_and_get(self, launch):
        self.assertEqual(trigger_manual_etl(self.request({'mode':'other'})).status_code,400)
        self.assertEqual(trigger_manual_etl(self.request({'mode':['PREVIEW','APPLY']})).status_code,400)
        self.assertEqual(trigger_manual_etl(self.request(method='get')).status_code,405)
        launch.assert_not_called()

    @patch('etl.manual_views.launch', side_effect=BusyError)
    def test_busy(self, launch):
        self.assertEqual(trigger_manual_etl(self.request({'mode':'PREVIEW'})).status_code,409)

    @patch('etl.manual_views.launch', side_effect=OSError('private'))
    def test_launch_error(self, launch):
        response = trigger_manual_etl(self.request({'mode':'PREVIEW'}))
        self.assertEqual(response.status_code,503)
        self.assertNotIn(b'private', response.content)

    @patch('etl.manual_views.launch')
    def test_csrf(self, launch):
        # Global CSRF middleware precedes LocalRoleGuard in the existing settings.
        response = Client(enforce_csrf_checks=True).post('/etl/manual/run/', {'mode':'PREVIEW'})
        self.assertEqual(response.status_code,403)
        launch.assert_not_called()

    @patch('etl.manual_views.launch')
    def test_anonymous_redirect(self, launch):
        response = Client().post('/etl/manual/run/', {'mode':'PREVIEW'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,'/accounts/login/')
        launch.assert_not_called()
