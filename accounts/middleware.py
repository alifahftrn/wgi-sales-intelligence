from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import add_never_cache_headers
from .policy import local_development, allowed_role, can_access_etl

class LocalRoleGuard(MiddlewareMixin):
    """Default-deny for all Django views except explicit account routes.
    Static assets served by runserver are not sensitive and bypass this guard.
    """
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not local_development(settings.DEBUG, request.META.get('REMOTE_ADDR')):
            return HttpResponseForbidden('Development hanya untuk localhost.')
        name = request.resolver_match.view_name if request.resolver_match else ''
        if name == 'accounts:login':
            return None
        user = request.user
        if not user.is_authenticated:
            return redirect('accounts:login')
        if not allowed_role(user.role):
            return HttpResponseForbidden('Peran tidak diizinkan.')
        if name in {'accounts:portal', 'accounts:logout'}:
            return None
        if not can_access_etl(user.role):
            return HttpResponseForbidden('Akses ini hanya untuk ADMIN.')
        return None

    def process_response(self, request, response):
        add_never_cache_headers(response)
        return response
