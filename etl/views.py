import logging
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.http import HttpResponseForbidden
from .extractor import latest, ExtractBusy
from .services import extract

log = logging.getLogger(__name__)

def local_only(request):
    return settings.DEBUG and request.META.get("REMOTE_ADDR") in ("127.0.0.1", "::1")

def page(request, error=None, message=None, status=200):
    return render(request, "monitor.html", {"manifest": latest(settings.EXTRACT_ROOT), "error": error, "message": message}, status=status)

@require_GET
def monitor(request):
    if not local_only(request):
        return HttpResponseForbidden("Local development only")
    return page(request)

@require_POST
def run_extract(request):
    if not local_only(request):
        return HttpResponseForbidden("Local development only")
    try:
        result = extract()
    except ExtractBusy:
        return page(request, error="Extract sedang berjalan atau lock tertinggal. Periksa README.", status=409)
    except Exception:
        log.exception("Extract failed")
        return page(request, error="Extract gagal. Lihat terminal VS Code atau jalankan python manage.py extract_sales untuk detail. Hasil terakhir tidak diubah.", status=500)
    return page(request, message=f"Extract berhasil: {result['total_rows']} baris. Data MySQL tidak diubah.")
