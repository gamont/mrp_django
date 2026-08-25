from django.urls import path
from . import views

app_name = "ui"

urlpatterns = [
    path("", views.home, name="home"),
    path("planner/", views.planner, name="planner"),
    path("planner/orders/<int:pk>/", views.planned_order_detail, name="planned-order-detail"),
    path("planner/orders/<int:pk>/firm/", views.firm_planned_order, name="firm-planned-order"),
    path("planner/orders/<int:pk>/convert/", views.convert_planned_order_ui, name="convert-planned-order"),
    path("production/", views.production, name="production"),
    path("production/orders/<int:pk>/", views.work_order_detail, name="work-order-detail"),
    path("production/orders/<int:pk>/release/", views.release_work_order_ui, name="release-work-order"),
    path("production/orders/<int:pk>/complete/", views.complete_work_order_ui, name="complete-work-order"),
    path("production/orders/<int:pk>/operations/<int:operation_pk>/action/", views.work_order_operation_action_ui, name="work-order-operation-action"),
    path("production/orders/<int:pk>/operations/<int:operation_pk>/report/", views.report_work_order_operation_ui, name="report-work-order-operation"),
    path("production/orders/<int:pk>/materials/<int:material_pk>/issue/", views.issue_work_order_material_ui, name="issue-work-order-material"),
    path("purchasing/", views.purchasing, name="purchasing"),
    path("purchasing/orders/<int:pk>/", views.purchase_order_detail, name="purchase-order-detail"),
    path("purchasing/lines/<int:pk>/receive/", views.receive_purchase_line_ui, name="receive-purchase-line"),
    path("inventory/", views.inventory, name="inventory"),
    path("quality/", views.quality, name="quality"),
    path("quality/inspections/<int:pk>/", views.inspection_detail, name="inspection-detail"),
    path("quality/inspections/<int:pk>/start/", views.start_inspection_ui, name="start-inspection"),
    path("quality/inspections/<int:pk>/complete/", views.complete_inspection_ui, name="complete-inspection"),
    path("quality/inspections/<int:pk>/characteristics/<int:characteristic_pk>/result/", views.record_inspection_result_ui, name="record-inspection-result"),
    path("costing/", views.costing, name="costing"),
    path("costing/items/<int:pk>/", views.item_cost_detail, name="item-cost-detail"),
    path("costing/periods/<int:pk>/final-close/", views.final_close_period_ui, name="final-close-period"),
    path("select-plant/", views.select_plant, name="select-plant"),
]
