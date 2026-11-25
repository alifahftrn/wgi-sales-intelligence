"""Localhost admin POST endpoint, with explicit authorization and CSRF."""
import sqlite3
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from accounts.policy import can_access_etl, local_development
from .manual_jobs import Journal, launch, BusyError, MODES


@require_POST
@csrf_protect
def trigger_manual_etl(request):
    if not local_development(settings.DEBUG, request.META.get('REMOTE_ADDR')):
        return HttpResponseForbidden('Development hanya untuk localhost.')
    user = request.user
    if not user.is_authenticated or not can_access_etl(user.role):
        return HttpResponseForbidden('Hanya ADMIN.')
    mode = request.POST.get('mode')
    if mode not in MODES or request.POST.getlist('mode') != [mode]:
        return HttpResponseBadRequest('Mode ETL tidak valid.')
    if mode == 'APPLY' and request.POST.get('confirm_apply') != 'yes':
        return HttpResponseBadRequest('Konfirmasi Apply diperlukan.')
    try:
        launch(Journal(settings.EXTRACT_ROOT.parent), settings.BASE_DIR, mode, user.pk)
    except BusyError:
        return HttpResponse('ETL sedang aktif atau lock tertinggal. Kembali ke ETL Monitoring dan periksa status.', status=409)
    except (OSError, sqlite3.Error):
        return HttpResponse('Permintaan tidak dapat dipastikan. Periksa riwayat manual sebelum mencoba lagi.', status=503)
    return redirect('etl_monitor_v1')
