from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("planner/", views.weekly_planner, name="weekly-planner"),
    path("planner/advanced/", views.advanced_planner, name="advanced-planner"),
    path("kanban/", views.kanban_board, name="kanban"),
    path("reliability/", views.reliability_dashboard, name="reliability"),
    path("generate/", views.generate_orders_ui, name="generate-orders"),
    path("orders/<int:pk>/", views.work_order_detail, name="work-order-detail"),
    path("orders/<int:pk>/release/", views.release_work_order_ui, name="release-work-order"),
    path("orders/<int:pk>/schedule/", views.schedule_work_order_ui, name="schedule-work-order"),
    path("orders/<int:pk>/auto-assign/", views.auto_assign_ui, name="auto-assign"),
    path("orders/<int:pk>/reserve-parts/", views.reserve_parts_ui, name="reserve-parts"),
    path("orders/<int:pk>/start/", views.start_work_order_ui, name="start-work-order"),
    path("orders/<int:pk>/complete/", views.complete_work_order_ui, name="complete-work-order"),
    path("orders/<int:pk>/parts/<int:part_pk>/issue/", views.issue_part_ui, name="issue-part"),
    path("assets/<int:pk>/meter/", views.meter_reading_ui, name="meter-reading"),
    path("assets/<int:pk>/condition/", views.condition_reading_ui, name="condition-reading"),
    path("assets/<int:pk>/failure/", views.report_failure_ui, name="report-failure"),
]
