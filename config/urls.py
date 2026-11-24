from django.urls import path
from etl import views
urlpatterns = [path("", views.monitor, name="monitor"), path("extract/run/", views.run_extract, name="run_extract")]
