from django.urls import path

from . import views

app_name = "shopfloor"

urlpatterns = [
    path("login/", views.terminal_login, name="login"),
    path("logout/", views.terminal_logout, name="logout"),
    path("stations/", views.stations, name="stations"),
    path("andon/", views.andon, name="andon"),
    path("oee/history/", views.oee_history, name="oee-history"),
    path("stations/select/", views.select_station, name="select-station"),
    path("terminal/<int:station_pk>/", views.terminal, name="terminal"),
    path("terminal/<int:station_pk>/dispatch/", views.dispatch_next_ui, name="dispatch-next"),
    path("terminal/<int:station_pk>/operations/<int:operation_pk>/action/", views.operation_action_ui, name="operation-action"),
    path("terminal/<int:station_pk>/operations/<int:operation_pk>/report/", views.report_complete_ui, name="report-complete"),
    path("terminal/<int:station_pk>/downtime/start/", views.start_downtime_ui, name="downtime-start"),
    path("terminal/<int:station_pk>/downtime/end/", views.end_downtime_ui, name="downtime-end"),
]
