"""Local admin schedule configuration; never starts a scheduler or ETL in HTTP."""
import sqlite3
from datetime import datetime
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from accounts.policy import can_access_etl, local_development
from .scheduler import Scheduler


def scheduler_context(root):
    """Read-only summary; UTC journal timestamps become aware datetimes for templates."""
    try:
        config, jobs = Scheduler(root).status()
        config = dict(config)
        jobs = [dict(job) for job in jobs]
        if config['updated']:
            config['updated'] = datetime.fromisoformat(config['updated'])
        for job in jobs:
            for key in ('started', 'finished'):
                if job[key]:
                    job[key] = datetime.fromisoformat(job[key])
        return dict(v2_config=config, v2_jobs=jobs, v2_error=False)
    except (sqlite3.Error, OSError, ValueError):
        return dict(v2_config=None, v2_jobs=[], v2_error=True)


def submitted_config(data):
    """Require one value per field and explicit confirmations on enable."""
    fields = {'enabled', 'clock', 'mode', 'confirm_apply', 'confirm_legacy_disabled', 'csrfmiddlewaretoken'}
    if set(data) - fields or any(len(data.getlist(key)) != 1 for key in data):
        raise ValueError('Permintaan konfigurasi tidak valid.')
    enabled = data.get('enabled')
    if enabled not in ('0', '1'):
        raise ValueError('Pilih status aktif atau nonaktif.')
    for key in ('confirm_apply', 'confirm_legacy_disabled'):
        if data.get(key) not in (None, 'yes'):
            raise ValueError('Konfirmasi tidak valid.')
    if enabled == '1' and data.get('confirm_legacy_disabled') != 'yes':
        raise ValueError('Konfirmasi scheduler Windows lama sudah nonaktif diperlukan.')
    return dict(enabled=enabled == '1', clock=data.get('clock'), mode=data.get('mode'),
                confirm_apply=data.get('confirm_apply') == 'yes')


@never_cache
@require_http_methods(['GET', 'POST'])
@csrf_protect
def scheduler_settings(request):
    if not local_development(settings.DEBUG, request.META.get('REMOTE_ADDR')):
        return HttpResponseForbidden('Development hanya untuk localhost.')
    user = request.user
    if not user.is_authenticated or not can_access_etl(user.role):
        return HttpResponseForbidden('Hanya ADMIN.')
    root = settings.EXTRACT_ROOT.parent
    context = scheduler_context(root)
    if context['v2_error']:
        return render(request, 'etl_scheduler_settings_v1.html', context, status=503)
    if request.method == 'POST':
        try:
            Scheduler(root).configure(**submitted_config(request.POST))
        except ValueError as exc:
            # Both validation functions raise fixed, non-sensitive messages.
            context['form_error'] = str(exc)
            return render(request, 'etl_scheduler_settings_v1.html', context, status=400)
        except (sqlite3.Error, OSError):
            context['form_error'] = 'Penyimpanan tidak dapat dipastikan. Periksa status sebelum mencoba lagi.'
            return render(request, 'etl_scheduler_settings_v1.html', context, status=503)
        return redirect('etl_scheduler_settings_v1')
    return render(request, 'etl_scheduler_settings_v1.html', context)
