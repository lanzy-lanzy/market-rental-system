from django.urls import path

from core.views.auth import login_view, logout_view
from core.views.dashboard import dashboard_view
from core.views.tenants import (
    tenant_list, tenant_add, tenant_edit, tenant_delete,
    tenant_view, tenant_search, tenant_add_modal, tenant_edit_modal,
)
from core.views.stalls import (
    stall_list, stall_add, stall_edit, stall_delete,
    stall_view, stall_add_modal, stall_edit_modal,
)
from core.views.contracts import (
    contract_list, contract_add, contract_edit, contract_delete,
    contract_view, contract_add_modal, contract_edit_modal, contract_terminate,
)
from core.views.billing import (
    billing_list, billing_generate, billing_view,
    billing_generate_all, billing_add_modal, billing_edit_modal,
)
from core.views.payments import (
    payment_list, payment_add, payment_view,
    payment_receipt, payment_print_receipt,
    payment_add_modal, payment_edit_modal, payment_void,
)
from core.views.reports import (
    report_dashboard, report_daily, report_weekly, report_monthly,
    report_annual, report_section, report_collector,
    report_paid_tenants, report_unpaid_tenants, report_overdue,
    report_ledger, report_occupancy, report_vacant,
    report_export_pdf, report_export_excel,
)
from core.views.ledger import ledger_list, ledger_view, ledger_print
from core.views.notices import notice_list, notice_add, notice_print, notice_mark_served
from core.views.settings_views import settings_view, settings_update
from core.views.audit import audit_log_list
from core.views.users import user_list, user_add, user_edit, user_deactivate

urlpatterns = [
    path('', dashboard_view, name='dashboard'),

    # Tenants
    path('tenants/', tenant_list, name='tenant_list'),
    path('tenants/add/', tenant_add, name='tenant_add'),
    path('tenants/<int:pk>/edit/', tenant_edit, name='tenant_edit'),
    path('tenants/<int:pk>/delete/', tenant_delete, name='tenant_delete'),
    path('tenants/<int:pk>/', tenant_view, name='tenant_view'),
    path('tenants/search/', tenant_search, name='tenant_search'),
    path('tenants/add-modal/', tenant_add_modal, name='tenant_add_modal'),
    path('tenants/<int:pk>/edit-modal/', tenant_edit_modal, name='tenant_edit_modal'),

    # Stalls
    path('stalls/', stall_list, name='stall_list'),
    path('stalls/add/', stall_add, name='stall_add'),
    path('stalls/<int:pk>/edit/', stall_edit, name='stall_edit'),
    path('stalls/<int:pk>/delete/', stall_delete, name='stall_delete'),
    path('stalls/<int:pk>/', stall_view, name='stall_view'),
    path('stalls/add-modal/', stall_add_modal, name='stall_add_modal'),
    path('stalls/<int:pk>/edit-modal/', stall_edit_modal, name='stall_edit_modal'),

    # Contracts
    path('contracts/', contract_list, name='contract_list'),
    path('contracts/add/', contract_add, name='contract_add'),
    path('contracts/<int:pk>/edit/', contract_edit, name='contract_edit'),
    path('contracts/<int:pk>/delete/', contract_delete, name='contract_delete'),
    path('contracts/<int:pk>/', contract_view, name='contract_view'),
    path('contracts/add-modal/', contract_add_modal, name='contract_add_modal'),
    path('contracts/<int:pk>/edit-modal/', contract_edit_modal, name='contract_edit_modal'),
    path('contracts/<int:pk>/terminate/', contract_terminate, name='contract_terminate'),

    # Billing
    path('billing/', billing_list, name='billing_list'),
    path('billing/generate/', billing_generate, name='billing_generate'),
    path('billing/generate-all/', billing_generate_all, name='billing_generate_all'),
    path('billing/<int:pk>/', billing_view, name='billing_view'),
    path('billing/add-modal/', billing_add_modal, name='billing_add_modal'),
    path('billing/<int:pk>/edit-modal/', billing_edit_modal, name='billing_edit_modal'),

    # Payments
    path('payments/', payment_list, name='payment_list'),
    path('payments/add/', payment_add, name='payment_add'),
    path('payments/<int:pk>/', payment_view, name='payment_view'),
    path('payments/<int:pk>/receipt/', payment_receipt, name='payment_receipt'),
    path('payments/<int:pk>/print/', payment_print_receipt, name='payment_print_receipt'),
    path('payments/add-modal/', payment_add_modal, name='payment_add_modal'),
    path('payments/<int:pk>/edit-modal/', payment_edit_modal, name='payment_edit_modal'),
    path('payments/<int:pk>/void/', payment_void, name='payment_void'),

    # Reports
    path('reports/', report_dashboard, name='report_dashboard'),
    path('reports/daily/', report_daily, name='report_daily'),
    path('reports/weekly/', report_weekly, name='report_weekly'),
    path('reports/monthly/', report_monthly, name='report_monthly'),
    path('reports/annual/', report_annual, name='report_annual'),
    path('reports/section/', report_section, name='report_section'),
    path('reports/collector/', report_collector, name='report_collector'),
    path('reports/paid-tenants/', report_paid_tenants, name='report_paid_tenants'),
    path('reports/unpaid-tenants/', report_unpaid_tenants, name='report_unpaid_tenants'),
    path('reports/overdue/', report_overdue, name='report_overdue'),
    path('reports/ledger/', report_ledger, name='report_ledger'),
    path('reports/occupancy/', report_occupancy, name='report_occupancy'),
    path('reports/vacant/', report_vacant, name='report_vacant'),
    path('reports/export/pdf/', report_export_pdf, name='report_export_pdf'),
    path('reports/export/excel/', report_export_excel, name='report_export_excel'),

    # Ledger
    path('ledger/', ledger_list, name='ledger_list'),
    path('ledger/<int:pk>/', ledger_view, name='ledger_view'),
    path('ledger/<int:pk>/print/', ledger_print, name='ledger_print'),

    # Notices
    path('notices/', notice_list, name='notice_list'),
    path('notices/add/', notice_add, name='notice_add'),
    path('notices/<int:pk>/print/', notice_print, name='notice_print'),
    path('notices/<int:pk>/mark-served/', notice_mark_served, name='notice_mark_served'),

    # Settings
    path('settings/', settings_view, name='settings_view'),
    path('settings/update/', settings_update, name='settings_update'),

    # Audit Logs
    path('audit-logs/', audit_log_list, name='audit_log_list'),

    # Users
    path('users/', user_list, name='user_list'),
    path('users/add/', user_add, name='user_add'),
    path('users/<int:pk>/edit/', user_edit, name='user_edit'),
    path('users/<int:pk>/deactivate/', user_deactivate, name='user_deactivate'),
]
