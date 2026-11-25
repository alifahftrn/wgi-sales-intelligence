from django import forms
from django.contrib.auth import authenticate, login, logout
from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from .policy import normalize_role

class LoginForm(forms.Form):
    email = forms.EmailField(max_length=150, label='Email')
    password = forms.CharField(max_length=1024, strip=False, label='Password', widget=forms.PasswordInput)

@require_http_methods(['GET','POST'])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect('accounts:portal')
    form = LoginForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = authenticate(request, username=form.cleaned_data['email'], password=form.cleaned_data['password'])
        except DatabaseError:
            return render(request, 'wgi_login.html', {'form':form,'error':'Database akun tidak dapat diakses.'}, status=503)
        if user is not None:
            login(request, user)
            return redirect('accounts:portal')
        form.add_error(None, 'Email atau password tidak valid, atau akun tidak diizinkan.')
    return render(request, 'wgi_login.html', {'form':form})

@require_GET
def portal(request):
    return render(request, 'wgi_account_portal.html', {'account_name':request.user.name,'role':normalize_role(request.user.role)})

@require_POST
def sign_out(request):
    logout(request)
    return redirect('accounts:login')
