from django.urls import path
from etl import views
urlpatterns = [path("", views.monitor, name="monitor"), path("extract/run/", views.run_extract, name="run_extract")]

from etl.monitoring_views import etl_monitor

urlpatterns += [
    path("etl/monitoring/", etl_monitor, name="etl_monitor_v1"),
]

from django.urls import include

urlpatterns += [
    path("accounts/", include("accounts.urls")),
]

from etl.manual_views import trigger_manual_etl

urlpatterns += [path("etl/manual/run/", trigger_manual_etl, name="etl_manual_run_v1")]

from etl.scheduler_views import scheduler_settings

urlpatterns += [path("etl/scheduler/", scheduler_settings, name="etl_scheduler_settings_v1")]
