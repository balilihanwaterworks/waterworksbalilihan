# consumers/urls.py
from django.urls import path
from . import views

app_name = 'consumers'  # Enables {% url 'consumers:view_name' %}

urlpatterns = [
    # Auth
    path('login/', views.staff_login, name='staff_login'),
    path('logout/', views.staff_logout, name='staff_logout'),

    # Profile Management
    path('profile/edit/', views.edit_profile, name='edit_profile'),

    # Password Recovery
    path('forgot-password/', views.forgot_password_request, name='forgot_password'),
    path('forgot-username/', views.forgot_username, name='forgot_username'),
    path('account-recovery/', views.account_recovery, name='account_recovery'),
    path('reset-password/<str:token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('reset-complete/', views.password_reset_complete, name='password_reset_complete'),

    # Dashboard
    path('home/', views.home, name='home'),

    # Consumer Management
    path('consumer-management/', views.consumer_management, name='consumer_management'),
    path('consumer/add/', views.add_consumer, name='add_consumer'),
    path('consumers/', views.consumer_list, name='consumer_list'),
    path('consumer/<int:consumer_id>/', views.consumer_detail, name='consumer_detail'),
    path('consumer/<int:consumer_id>/edit/', views.edit_consumer, name='edit_consumer'),
    path('consumer/<int:consumer_id>/bills/', views.consumer_bill, name='consumer_bill'),
    path('consumer/import/', views.import_consumers_csv, name='import_consumers_csv'),
    path('consumer/import/template/', views.download_consumer_template, name='download_consumer_template'),

    # Meter Readings
    path('meter-reading-overview/', views.meter_reading_overview, name='meter_reading_overview'),
    path('meter-readings/', views.meter_readings, name='meter_readings'),
    path('meter-readings/print/', views.meter_readings_print, name='meter_readings_print'),
    path('meter-readings/barangay/<int:barangay_id>/', views.barangay_meter_readings, name='barangay_meter_readings'),
    path('meter-readings/barangay/<int:barangay_id>/print/', views.barangay_meter_readings_print, name='barangay_meter_readings_print'),
    path('meter-readings/barangay/<int:barangay_id>/confirm-all/', views.confirm_all_readings, name='confirm_all_readings'),
    path('meter-readings/confirm-all-global/', views.confirm_all_readings_global, name='confirm_all_readings_global'),
    path('meter-readings/barangay/<int:barangay_id>/export/', views.export_barangay_readings, name='export_barangay_readings'),
    path('meter-readings/<int:reading_id>/confirm/', views.confirm_reading, name='confirm_reading'),
    path('meter-readings/<int:reading_id>/reject/', views.reject_reading, name='reject_reading'),
    path('meter-readings/pending/', views.pending_readings_view, name='pending_readings'),
    path('meter-readings/barangay/<int:barangay_id>/confirm-selected/', views.confirm_selected_readings, name='confirm_selected_readings'),

    # Smart Meter
    path('smart-meter-webhook/', views.smart_meter_webhook, name='smart_meter_webhook'),

    # Consumer Status Filters
    path('connected-consumers/', views.connected_consumers, name='connected_consumers'),
    path('disconnected/', views.disconnected_consumers_list, name='disconnected_consumers'),  # ← View must be named `disconnected_consumers`
    path('disconnect/<int:consumer_id>/', views.disconnect_consumer, name='disconnect_consumer'),
     path('reconnect/<int:consumer_id>/', views.reconnect_consumer, name='reconnect_consumer'),
    path('delinquent-consumers/', views.delinquent_consumers, name='delinquent_consumers'),
    path('delinquent-consumers/export/', views.export_delinquent_consumers, name='export_delinquent_consumers'),
    path('delinquent-report/print/', views.delinquent_report_printable, name='delinquent_report_print'),

    # AJAX
    path('ajax/load-puroks/', views.load_puroks, name='ajax_load_puroks'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/barangay/<int:barangay_id>/', views.barangay_report, name='barangay_report'),
    path('reports/export-excel/', views.export_report_excel, name='export_report_excel'),

    path('system-settings-verification/', views.system_settings_verification, name='system_settings_verification'),
    path('system-management/', views.system_management, name='system_management'),
    path('system/backup/', views.backup_database, name='backup_database'),

    # Database Documentation
    path('database-documentation/', views.database_documentation, name='database_documentation'),

    # Payments
    path('payment/', views.inquire, name='inquire'),
    path('payment/process/', views.process_payment, name='process_payment'),
    path('payment/water-bill/<int:consumer_id>/print/', views.water_bill_print, name='water_bill_print'),
    path('payment/receipt/<int:payment_id>/', views.payment_receipt, name='payment_receipt'),
    path('payment/history/', views.payment_history, name='payment_history'),

    # API Endpoints (Android App)
    path('api/login/', views.api_login, name='api_login'),
    path('api/logout/', views.api_logout, name='api_logout'),
    path('api/consumers/', views.api_consumers, name='api_consumers'),
    path('api/consumers/<int:consumer_id>/previous-reading/', views.api_get_previous_reading, name='api_get_previous_reading'),
    path('api/consumers/<int:consumer_id>/bill/', views.api_get_consumer_bill, name='api_get_consumer_bill'),
    path('api/consumers/<int:consumer_id>/bills/', views.api_get_consumer_bills, name='api_get_consumer_bills'),
    path('api/meter-readings/', views.api_submit_reading, name='api_submit_reading'),
    path('api/rates/', views.api_get_current_rates, name='api_get_current_rates'),
    path('api/settings/', views.api_get_system_settings, name='api_get_system_settings'),
    path('api/settings/check-version/', views.api_check_settings_version, name='api_check_settings_version'),

    # Manual Reading with Proof (requires admin confirmation)
    path('api/readings/manual/', views.api_submit_manual_reading, name='api_submit_manual_reading'),
    path('api/readings/pending/', views.api_get_pending_readings, name='api_get_pending_readings'),
    path('api/readings/<int:reading_id>/confirm/', views.api_confirm_reading, name='api_confirm_reading'),
    path('api/readings/<int:reading_id>/reject/', views.api_reject_reading, name='api_reject_reading'),

    # Notifications API
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    path('api/notifications/count/', views.api_get_notification_count, name='api_get_notification_count'),
    path('api/notifications/<int:notification_id>/mark-read/', views.api_mark_notification_read, name='api_mark_notification_read'),

    # User Management & Security
    path('admin-verification/', views.admin_verification, name='admin_verification'),
    path('user-login-history/', views.user_login_history, name='user_login_history'),
    path('user-login-history/<int:user_id>/', views.user_specific_login_history, name='user_specific_login_history'),
    path('session/<int:session_id>/activities/', views.session_activities, name='session_activities'),
    path('user-management/', views.user_management, name='user_management'),
    path('user/create/', views.create_user, name='create_user'),
    path('user/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('user/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('user/<int:user_id>/reset-password/', views.reset_user_password, name='reset_user_password'),

    # Notifications
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    # Debug/Admin Tools
    path('test-email/', views.test_email, name='test_email'),
]