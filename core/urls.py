from django.urls import path

from core.views.auth import login_view, logout_view
from core.views.dashboard import dashboard_view
from core.views.landing import landing_view
from core.views.tenants import (
    tenant_list, tenant_add, tenant_edit, tenant_delete,
    tenant_view, tenant_search, tenant_add_modal, tenant_edit_modal,
    tenant_list_print, tenant_list_export_pdf, tenant_view_print, tenant_view_export_pdf,
)
from core.views.stalls import (
    stall_list, stall_add, stall_edit, stall_delete,
    stall_view, stall_add_modal, stall_edit_modal,
    stall_list_print, stall_list_export_pdf, stall_view_print, stall_view_export_pdf,
)
from core.views.contracts import (
    contract_list, contract_add, contract_edit, contract_delete,
    contract_view, contract_add_modal, contract_edit_modal, contract_terminate,
    contract_list_print, contract_list_export_pdf, contract_view_print, contract_view_export_pdf,
)
from core.views.billing import (
    billing_list, billing_generate, billing_view,
    billing_generate_all, billing_add_modal, billing_edit_modal,
    billing_collect, billing_quick_pay,
    billing_list_print, billing_list_export_pdf, billing_view_print, billing_view_export_pdf,
)
from core.views.payments import (
    payment_list, payment_add, payment_view,
    payment_receipt, payment_print_receipt,
    payment_add_modal, payment_edit_modal, payment_void,
    payment_list_print, payment_list_export_pdf, payment_receipt_export_pdf,
)
from core.views.reports import (
    report_dashboard, report_daily, report_weekly, report_monthly,
    report_annual, report_section, report_collector,
    report_paid_tenants, report_unpaid_tenants, report_overdue,
    report_ledger, report_occupancy, report_vacant,
    report_export_pdf, report_export_excel,
)
from core.views.ledger import ledger_list, ledger_view, ledger_print, ledger_list_print, ledger_list_export_pdf, ledger_view_export_pdf
from core.views.notices import notice_list, notice_add, notice_print, notice_mark_served, notice_list_print, notice_list_export_pdf, notice_export_pdf
from core.views.settings_views import settings_view, settings_update
from core.views.audit import audit_log_list
from core.views.users import user_list, user_add, user_edit, user_deactivate
from core.views.tenant_portal import tenant_portal_dashboard, tenant_portal_history, tenant_portal_password

urlpatterns = [
    path('', landing_view, name='landing'),
    path('dashboard/', dashboard_view, name='dashboard'),

    # Tenant self-service portal (RBAC: tenant role only, own data only)
    path('portal/', tenant_portal_dashboard, name='tenant_portal'),
    path('portal/history/', tenant_portal_history, name='tenant_portal_history'),
    path('portal/password/', tenant_portal_password, name='tenant_portal_password'),

    # Tenants
    path('tenants/', tenant_list, name='tenant_list'),
    path('tenants/print/', tenant_list_print, name='tenant_list_print'),
    path('tenants/export/pdf/', tenant_list_export_pdf, name='tenant_list_export_pdf'),
    path('tenants/add/', tenant_add, name='tenant_add'),
    path('tenants/<int:pk>/edit/', tenant_edit, name='tenant_edit'),
    path('tenants/<int:pk>/delete/', tenant_delete, name='tenant_delete'),
    path('tenants/<int:pk>/', tenant_view, name='tenant_view'),
    path('tenants/<int:pk>/print/', tenant_view_print, name='tenant_view_print'),
    path('tenants/<int:pk>/export/pdf/', tenant_view_export_pdf, name='tenant_view_export_pdf'),
    path('tenants/search/', tenant_search, name='tenant_search'),
    path('tenants/add-modal/', tenant_add_modal, name='tenant_add_modal'),
    path('tenants/<int:pk>/edit-modal/', tenant_edit_modal, name='tenant_edit_modal'),

    # Stalls
    path('stalls/', stall_list, name='stall_list'),
    path('stalls/print/', stall_list_print, name='stall_list_print'),
    path('stalls/export/pdf/', stall_list_export_pdf, name='stall_list_export_pdf'),
    path('stalls/add/', stall_add, name='stall_add'),
    path('stalls/<int:pk>/edit/', stall_edit, name='stall_edit'),
    path('stalls/<int:pk>/delete/', stall_delete, name='stall_delete'),
    path('stalls/<int:pk>/', stall_view, name='stall_view'),
    path('stalls/<int:pk>/print/', stall_view_print, name='stall_view_print'),
    path('stalls/<int:pk>/export/pdf/', stall_view_export_pdf, name='stall_view_export_pdf'),
    path('stalls/add-modal/', stall_add_modal, name='stall_add_modal'),
    path('stalls/<int:pk>/edit-modal/', stall_edit_modal, name='stall_edit_modal'),

    # Contracts
    path('contracts/', contract_list, name='contract_list'),
    path('contracts/print/', contract_list_print, name='contract_list_print'),
    path('contracts/export/pdf/', contract_list_export_pdf, name='contract_list_export_pdf'),
    path('contracts/add/', contract_add, name='contract_add'),
    path('contracts/<int:pk>/edit/', contract_edit, name='contract_edit'),
    path('contracts/<int:pk>/delete/', contract_delete, name='contract_delete'),
    path('contracts/<int:pk>/', contract_view, name='contract_view'),
    path('contracts/<int:pk>/print/', contract_view_print, name='contract_view_print'),
    path('contracts/<int:pk>/export/pdf/', contract_view_export_pdf, name='contract_view_export_pdf'),
    path('contracts/add-modal/', contract_add_modal, name='contract_add_modal'),
    path('contracts/<int:pk>/edit-modal/', contract_edit_modal, name='contract_edit_modal'),
    path('contracts/<int:pk>/terminate/', contract_terminate, name='contract_terminate'),

    # Billing
    path('billing/', billing_list, name='billing_list'),
    path('billing/print/', billing_list_print, name='billing_list_print'),
    path('billing/export/pdf/', billing_list_export_pdf, name='billing_list_export_pdf'),
    path('billing/generate/', billing_generate, name='billing_generate'),
    path('billing/generate-all/', billing_generate_all, name='billing_generate_all'),
    path('billing/<int:pk>/', billing_view, name='billing_view'),
    path('billing/<int:pk>/print/', billing_view_print, name='billing_view_print'),
    path('billing/<int:pk>/export/pdf/', billing_view_export_pdf, name='billing_view_export_pdf'),
    path('billing/<int:pk>/collect/', billing_collect, name='billing_collect'),
    path('billing/<int:pk>/quick-pay/', billing_quick_pay, name='billing_quick_pay'),
    path('billing/add-modal/', billing_add_modal, name='billing_add_modal'),
    path('billing/<int:pk>/edit-modal/', billing_edit_modal, name='billing_edit_modal'),

    # Payments
    path('payments/', payment_list, name='payment_list'),
    path('payments/print/', payment_list_print, name='payment_list_print'),
    path('payments/export/pdf/', payment_list_export_pdf, name='payment_list_export_pdf'),
    path('payments/add/', payment_add, name='payment_add'),
    path('payments/<int:pk>/', payment_view, name='payment_view'),
    path('payments/<int:pk>/receipt/', payment_receipt, name='payment_receipt'),
    path('payments/<int:pk>/print/', payment_print_receipt, name='payment_print_receipt'),
    path('payments/<int:pk>/export/pdf/', payment_receipt_export_pdf, name='payment_receipt_export_pdf'),
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
    path('ledger/print/', ledger_list_print, name='ledger_list_print'),
    path('ledger/export/pdf/', ledger_list_export_pdf, name='ledger_list_export_pdf'),
    path('ledger/<int:pk>/', ledger_view, name='ledger_view'),
    path('ledger/<int:pk>/print/', ledger_print, name='ledger_print'),
    path('ledger/<int:pk>/export/pdf/', ledger_view_export_pdf, name='ledger_view_export_pdf'),

    # Notices
    path('notices/', notice_list, name='notice_list'),
    path('notices/print/', notice_list_print, name='notice_list_print'),
    path('notices/export/pdf/', notice_list_export_pdf, name='notice_list_export_pdf'),
    path('notices/add/', notice_add, name='notice_add'),
    path('notices/<int:pk>/print/', notice_print, name='notice_print'),
    path('notices/<int:pk>/export/pdf/', notice_export_pdf, name='notice_export_pdf'),
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
