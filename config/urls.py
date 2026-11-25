from django.urls import path
from etl import views
urlpatterns = [path("", views.monitor, name="monitor"), path("extract/run/", views.run_extract, name="run_extract")]

from etl.monitoring_views import etl_monitor

urlpatterns += [
    path("etl/monitoring/", etl_monitor, name="etl_monitor_v1"),
]