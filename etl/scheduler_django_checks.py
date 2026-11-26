"""Local scheduler HTTP tests; temporary SQLite only, no business DB access."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory, Client, override_settings
from etl.scheduler import Scheduler
from etl.scheduler_views import scheduler_settings, scheduler_context


@override_settings(DEBUG=True)
class SchedulerEndpointTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        settings = self.settings(EXTRACT_ROOT=self.root / 'extracts')
        settings.enable()
        self.addCleanup(settings.disable)
        self.scheduler = Scheduler(self.root)

    def req(self, data=None, *, method='post', role='ADMIN', auth=True, remote='127.0.0.1'):
        req = getattr(RequestFactory(), method)('/etl/scheduler/', data or {}, REMOTE_ADDR=remote)
        req.user = SimpleNamespace(is_authenticated=auth, role=role, pk=42)
        req._dont_enforce_csrf_checks = True
        return req

    def preview(self, **overrides):
        return dict({'enabled':'1','clock':'08:45','mode':'PREVIEW','confirm_legacy_disabled':'yes'}, **overrides)

    def test_get_read_only(self):
        response = scheduler_settings(self.req(method='get'))
        self.assertContains(response, 'Pengaturan Scheduler V2')
        self.assertFalse(self.scheduler.path.exists())

    def test_preview_persist(self):
        response = scheduler_settings(self.req(self.preview()))
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,'/etl/scheduler/')
        config, jobs = self.scheduler.status()
        self.assertEqual((config['enabled'],config['clock'],config['mode']), (1,'08:45','PREVIEW'))
        self.assertEqual(jobs, [])

    def test_disable(self):
        self.scheduler.configure(enabled=True,clock='08:45',mode='PREVIEW')
        response = scheduler_settings(self.req({'enabled':'0','clock':'00:00','mode':'PREVIEW'}))
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.scheduler.status()[0]['enabled'],0)

    def test_apply_confirmation(self):
        self.assertEqual(scheduler_settings(self.req(self.preview(mode='APPLY'))).status_code,400)
        self.assertFalse(self.scheduler.path.exists())
        self.assertEqual(scheduler_settings(self.req(self.preview(mode='APPLY',confirm_apply='yes'))).status_code,302)
        self.assertEqual(self.scheduler.status()[0]['mode'],'APPLY')

    def test_legacy_confirmation(self):
        self.assertEqual(scheduler_settings(self.req(self.preview(confirm_legacy_disabled='no'))).status_code,400)
        self.assertFalse(self.scheduler.path.exists())

    def test_invalid_fields(self):
        for overrides in ({'clock':'25:00'},{'mode':'OTHER'},{'enabled':'2'},{'clock':['08:45','00:00']},{'unexpected':'x'}):
            with self.subTest(overrides=overrides):
                self.assertEqual(scheduler_settings(self.req(self.preview(**overrides))).status_code,400)
        self.assertFalse(self.scheduler.path.exists())

    def test_roles_and_localhost(self):
        for role in ('SALES','BOD','UNKNOWN'):
            self.assertEqual(scheduler_settings(self.req(self.preview(),role=role)).status_code,403)
        self.assertEqual(scheduler_settings(self.req(self.preview(),auth=False)).status_code,403)
        self.assertEqual(scheduler_settings(self.req(self.preview(),remote='192.168.0.10')).status_code,403)
        self.assertFalse(self.scheduler.path.exists())

    def test_method(self):
        self.assertEqual(scheduler_settings(self.req(method='put')).status_code,405)

    def test_csrf(self):
        response = Client(enforce_csrf_checks=True).post('/etl/scheduler/',self.preview())
        self.assertEqual(response.status_code,403)
        self.assertFalse(self.scheduler.path.exists())

    def test_anonymous_redirect(self):
        response = Client().get('/etl/scheduler/')
        self.assertRedirects(response,'/accounts/login/',fetch_redirect_response=False)

    def test_storage_failure(self):
        with patch('etl.scheduler_views.Scheduler.configure',side_effect=OSError('private path')):
            response = scheduler_settings(self.req(self.preview()))
        self.assertContains(response,'Penyimpanan tidak dapat dipastikan',status_code=503)
        self.assertNotContains(response,'private path',status_code=503)

    def test_unreadable_journal(self):
        self.scheduler.path.write_text('not sqlite')
        self.assertTrue(scheduler_context(self.root)['v2_error'])
        response = scheduler_settings(self.req(self.preview()))
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.scheduler.path.read_text(),'not sqlite')
