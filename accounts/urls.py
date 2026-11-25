from django.urls import path
from . import views
app_name = 'accounts'
urlpatterns = [path('login/', views.sign_in, name='login'), path('', views.portal, name='portal'), path('logout/', views.sign_out, name='logout')]
