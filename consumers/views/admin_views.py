from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from ..decorators import (
    get_client_ip, get_user_agent, is_admin_user, is_superuser_only,
    consumer_edit_permission_required, disconnect_permission_required,
    user_management_permission_required, system_settings_permission_required,
    billing_permission_required, reports_permission_required, view_only_for_admin,
    rate_limit_login, role_required
)
from django.db.models import Q, Max, Count, Sum, OuterRef, Subquery, Value, F
from django.db.models.functions import Concat, TruncMonth
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from datetime import datetime, timedelta, date
try:
    from dateutil.relativedelta import relativedelta
except Exception:
    # Fallback: approximate relativedelta by using a timedelta of ~30 days per month
    # This keeps existing subtraction usages like relativedelta(months=5) working
    from datetime import timedelta as _td
    def relativedelta(months=0, **kwargs):
        return _td(days=30 * int(months))
from decimal import Decimal, InvalidOperation
import uuid
import json
import csv
import base64
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

# Cloudinary import with error handling (optional dependency)
try:
    from cloudinary import uploader as cloudinary_uploader  # type: ignore
    CLOUDINARY_AVAILABLE = True
except ImportError:
    cloudinary_uploader = None
    CLOUDINARY_AVAILABLE = False

from ..models import (
    Consumer, Barangay, Purok, MeterReading, Bill, SystemSetting, Payment,
    StaffProfile, UserLoginEvent, MeterBrand, PasswordResetToken, UserActivity,
    SystemSettingChangeLog, Notification
)
from ..forms import ConsumerForm


# Helper function to authenticate API requests using session token
def authenticate_api_request(request):
    """
    Authenticate API request using session token from Authorization header or request body.
    Returns the user if authenticated, None otherwise.
    """
    from django.contrib.sessions.models import Session

    token = None

    # Try Authorization header first (Bearer token)
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]

    # Try request body if no header token
    if not token and request.body:
        try:
            data = json.loads(request.body.decode('utf-8'))
            token = data.get('token')
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    if not token:
        return None

    try:
        # Find the session by key
        session = Session.objects.get(session_key=token)

        # Check if session is expired
        if session.expire_date < timezone.now():
            return None

        # Get user from session data
        session_data = session.get_decoded()
        user_id = session_data.get('_auth_user_id')

        if user_id:
            user = User.objects.get(id=user_id)
            return user
    except (Session.DoesNotExist, User.DoesNotExist):
        pass

    return None


# Helper function to get previous confirmed reading
def get_previous_reading(consumer):
    """Get the most recent confirmed meter reading for a consumer."""
    latest_reading = MeterReading.objects.filter(
        consumer=consumer,
        is_confirmed=True
    ).order_by('-reading_date', '-created_at').first()

    return latest_reading.reading_value if latest_reading else 0


# Helper function to calculate water bill
def calculate_water_bill(consumer, consumption):
    """
    Calculate water bill using TIERED rate structure from System Settings.

    Returns: (average_rate, total_amount, breakdown)
    - average_rate: Effective rate per cubic meter
    - total_amount: Total bill amount
    - breakdown: Dict with tier-by-tier calculation details
    """
    from ..utils import calculate_tiered_water_bill

    # Use tiered calculation from utils
    total_amount, average_rate, breakdown = calculate_tiered_water_bill(
        consumption=consumption,
        usage_type=consumer.usage_type
    )

    return float(average_rate), float(total_amount), breakdown



@login_required
@system_settings_permission_required
def system_settings_verification(request):
    """
    Admin verification for System Settings - requires password re-entry.
    Separate from user management verification for independent access control.
    """
    from ..decorators import get_client_ip
    from django.contrib.auth import authenticate

    if request.method == 'POST':
        password = request.POST.get('password', '')

        user = authenticate(username=request.user.username, password=password)

        if user is not None and user == request.user:
            request.session['system_settings_verified'] = True
            request.session['system_settings_verified_time'] = timezone.now().isoformat()

            UserLoginEvent.objects.create(
                user=request.user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                login_method='web',
                status='success',
                session_key=request.session.session_key
            )

            messages.success(request, "Admin verification successful!")
            return redirect('consumers:system_management')
        else:
            messages.error(request, "Incorrect password. Verification failed.")
            UserLoginEvent.objects.create(
                user=request.user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                login_method='web',
                status='failed'
            )

    return render(request, 'consumers/system_settings_verification.html')



@login_required
def backup_database(request):
    """
    Superadmin-only: Export the entire database as a ZIP file containing
    one JSON file per model/table. The ZIP is named with the current timestamp
    so staff can keep weekly archives on a flash drive.

    Included tables:
    - Consumers, Barangays, Puroks, MeterBrands
    - Bills, Payments, MeterReadings (Supports monthly filtering)
    - System Settings, System Setting Change Logs
    - Users (username, email, role — NO passwords)
    - User Login History, User Activities
    """
    import zipfile
    import io
    import json as _json
    from datetime import datetime as _dt
    from django.core import serializers as dj_serializers
    from django.http import HttpResponse

    # Superadmin-only guard
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Only the Superadmin can create system backups.")
        return redirect('consumers:system_management')

    if request.method != 'POST':
        return redirect('consumers:system_management')

    # Get optional month & year filter
    backup_month = request.POST.get('backup_month', 'all')
    backup_year = request.POST.get('backup_year', 'all')
    
    is_filtered = backup_month != 'all' and backup_year != 'all'

    # ---- Tables to export ----
    # Each tuple: (filename_in_zip, queryset)
    from ..models import (
        Consumer, Barangay, Purok, MeterBrand, Bill, Payment, MeterReading,
        SystemSetting, SystemSettingChangeLog, UserLoginEvent, UserActivity,
        StaffProfile
    )
    
    bills_qs = Bill.objects.select_related('consumer').all()
    payments_qs = Payment.objects.select_related('consumer', 'bill').all()
    readings_qs = MeterReading.objects.select_related('consumer').all()

    if is_filtered:
        bills_qs = bills_qs.filter(billing_period__month=backup_month, billing_period__year=backup_year)
        payments_qs = payments_qs.filter(payment_date__month=backup_month, payment_date__year=backup_year)
        readings_qs = readings_qs.filter(reading_date__month=backup_month, reading_date__year=backup_year)

    tables = [
        ('consumers.json', Consumer.objects.select_related('barangay', 'purok', 'meter_brand').all()),
        ('barangays.json', Barangay.objects.all()),
        ('puroks.json', Purok.objects.select_related('barangay').all()),
        ('meter_brands.json', MeterBrand.objects.all()),
        ('bills.json', bills_qs),
        ('payments.json', payments_qs),
        ('meter_readings.json', readings_qs),
        ('system_settings.json', SystemSetting.objects.all()),
        ('system_setting_changes.json', SystemSettingChangeLog.objects.select_related('changed_by').all()),
        ('user_login_history.json', UserLoginEvent.objects.select_related('user').all()),
        ('user_activities.json', UserActivity.objects.select_related('user').all()),
        ('staff_profiles.json', StaffProfile.objects.select_related('user', 'barangay').all()),
    ]

    # ---- Build ZIP in memory ----
    zip_buffer = io.BytesIO()
    timestamp = _dt.now().strftime('%Y-%m-%d_%H-%M')
    
    if is_filtered:
        filename = f'balilihan_backup_{backup_year}_{str(backup_month).zfill(2)}_{timestamp}.zip'
        period_text = f"Monthly ({backup_year}-{str(backup_month).zfill(2)})"
    else:
        filename = f'balilihan_backup_ALL_{timestamp}.zip'
        period_text = "All Time (Full Backup)"

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        total_records = 0

        for tbl_filename, queryset in tables:
            try:
                data = dj_serializers.serialize('json', queryset, indent=2)
                zf.writestr(f'data/{tbl_filename}', data)
                total_records += queryset.count()
            except Exception as e:
                # Write an error note for this table instead of failing the entire backup
                zf.writestr(f'data/{tbl_filename}.ERROR.txt', f"Error exporting table: {str(e)}")

        # ---- Write a human-readable README ----
        readme = f"""BALILIHAN WATERWORKS SYSTEM BACKUP
===================================
Backup Date  : {_dt.now().strftime('%B %d, %Y %I:%M %p')}
Generated By : {request.user.get_full_name() or request.user.username} ({request.user.username})
Backup Scope : {period_text}
Total Records: {total_records}

CONTENTS
--------
data/consumers.json            — All registered consumers
data/barangays.json            — Barangay Master List
data/puroks.json               — Purok Master List
data/meter_brands.json         — Meter Brand Master List
data/bills.json                — {"Selected month" if is_filtered else "All"} billing records
data/payments.json             — {"Selected month" if is_filtered else "All"} payment transactions
data/meter_readings.json       — {"Selected month" if is_filtered else "All"} meter reading records
data/system_settings.json      — Water rates, schedules, penalties
data/system_setting_changes.json — Audit log of settings changes
data/user_login_history.json   — Staff login/logout history
data/user_activities.json      — Staff activity audit trail
data/staff_profiles.json       — Staff user accounts and roles

HOW TO RESTORE
--------------
These .json files are Django "Fixtures". They contain structured database records.
Contact your system developer and provide this ZIP file.
The developer can use `python manage.py loaddata <filename.json>` to completely restore the database perfectly in case of a crash or data loss.

SECURITY NOTE
-------------
This file contains sensitive billing and personal data.
Store securely on an encrypted flash drive or offline storage.
Do NOT share this file over the internet.
"""
        zf.writestr('README.txt', readme)

    zip_buffer.seek(0)

    # ---- Log the backup action ----
    try:
        current_session = UserLoginEvent.objects.filter(
            user=request.user, logout_timestamp__isnull=True, status='success'
        ).order_by('-login_timestamp').first()

        UserActivity.objects.create(
            user=request.user,
            action='system_settings_updated',
            description=f'Created system backup ({period_text})',
            login_event=current_session,
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    except Exception:
        pass

    # ---- Stream ZIP as download response ----
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response




@login_required
@system_settings_permission_required
def system_management(request):

    """
    Manage system-wide settings: water rates, reading schedule, billing schedule, and penalties.
    RESTRICTED: Superuser only - Admins cannot access.

    All changes take effect IMMEDIATELY:
    - Reading schedule: Mobile app fetches via /api/settings/
    - Billing schedule: Affects newly generated bills
    - Tiered rates: Affects newly generated bills
    - Penalty settings: Affects penalty calculations on all overdue bills
    """
    # Check if admin verification is required and not expired
    admin_verified = request.session.get('system_settings_verified', False)
    admin_verified_time_str = request.session.get('system_settings_verified_time')

    verification_expired = False
    if admin_verified and admin_verified_time_str:
        try:
            from datetime import timedelta
            verified_time = timezone.datetime.fromisoformat(admin_verified_time_str)
            if timezone.is_naive(verified_time):
                verified_time = timezone.make_aware(verified_time)
            time_since_verification = timezone.now() - verified_time
            if time_since_verification > timedelta(minutes=15):
                verification_expired = True
                request.session.pop('system_settings_verified', None)
                request.session.pop('system_settings_verified_time', None)
        except (ValueError, TypeError):
            verification_expired = True

    if not admin_verified or verification_expired:
        if verification_expired:
            messages.warning(request, "Admin verification expired. Please verify again.")
        else:
            messages.warning(request, "Admin verification required to access System Settings.")
        return redirect('consumers:system_settings_verification')

    # Get the first (or only) SystemSetting instance (assumes singleton pattern)
    setting, created = SystemSetting.objects.get_or_create(id=1)

    # Get recent change logs for display
    recent_changes = SystemSettingChangeLog.objects.all()[:10]

    if request.method == "POST":
        try:
            # =====================================================
            # CAPTURE PREVIOUS VALUES FOR CHANGE LOG
            # =====================================================
            previous_values = {
                'reading_schedule': {
                    'start_day': setting.reading_start_day,
                    'end_day': setting.reading_end_day,
                },
                'billing_schedule': {
                    'billing_day': setting.billing_day_of_month,
                    'due_day': setting.due_day_of_month,
                },
                'residential_rates': {
                    'minimum_charge': str(setting.residential_minimum_charge),
                    'tier2_rate': str(setting.residential_tier2_rate),
                    'tier3_rate': str(setting.residential_tier3_rate),
                    'tier4_rate': str(setting.residential_tier4_rate),
                    'tier5_rate': str(setting.residential_tier5_rate),
                },
                'commercial_rates': {
                    'minimum_charge': str(setting.commercial_minimum_charge),
                    'tier2_rate': str(setting.commercial_tier2_rate),
                    'tier3_rate': str(setting.commercial_tier3_rate),
                    'tier4_rate': str(setting.commercial_tier4_rate),
                    'tier5_rate': str(setting.commercial_tier5_rate),
                },
                'penalty_settings': {
                    'enabled': setting.penalty_enabled,
                    'type': setting.penalty_type,
                    'rate': str(setting.penalty_rate),
                    'fixed_amount': str(setting.fixed_penalty_amount),
                    'grace_period': setting.penalty_grace_period_days,
                    'max_amount': str(setting.max_penalty_amount),
                },
            }

            # =====================================================
            # TIERED WATER RATES - Residential
            # =====================================================
            res_minimum = Decimal(request.POST.get("residential_minimum_charge", "75"))
            res_tier2 = Decimal(request.POST.get("residential_tier2_rate", "15"))
            res_tier3 = Decimal(request.POST.get("residential_tier3_rate", "16"))
            res_tier4 = Decimal(request.POST.get("residential_tier4_rate", "17"))
            res_tier5 = Decimal(request.POST.get("residential_tier5_rate", "18"))

            # =====================================================
            # TIERED WATER RATES - Commercial
            # =====================================================
            comm_minimum = Decimal(request.POST.get("commercial_minimum_charge", "100"))
            comm_tier2 = Decimal(request.POST.get("commercial_tier2_rate", "18"))
            comm_tier3 = Decimal(request.POST.get("commercial_tier3_rate", "20"))
            comm_tier4 = Decimal(request.POST.get("commercial_tier4_rate", "22"))
            comm_tier5 = Decimal(request.POST.get("commercial_tier5_rate", "24"))

            # =====================================================
            # READING SCHEDULE
            # =====================================================
            reading_start = int(request.POST.get("reading_start_day", "1"))
            reading_end = int(request.POST.get("reading_end_day", "10"))

            # =====================================================
            # BILLING SCHEDULE
            # =====================================================
            billing_day = int(request.POST.get("billing_day_of_month", "1"))
            due_day = int(request.POST.get("due_day_of_month", "20"))

            # =====================================================
            # PENALTY SETTINGS
            # =====================================================
            penalty_enabled = request.POST.get("penalty_enabled") == "on"
            penalty_type = request.POST.get("penalty_type", "percentage")
            penalty_rate = Decimal(request.POST.get("penalty_rate", "25"))
            fixed_penalty = Decimal(request.POST.get("fixed_penalty_amount", "50"))
            grace_period = int(request.POST.get("penalty_grace_period_days", "0"))
            max_penalty = Decimal(request.POST.get("max_penalty_amount", "0"))

            # =====================================================
            # VALIDATION
            # =====================================================
            # Validate tiered rates (all must be positive)
            tiered_rates = [
                (res_minimum, "Residential minimum charge"),
                (res_tier2, "Residential tier 2 rate"),
                (res_tier3, "Residential tier 3 rate"),
                (res_tier4, "Residential tier 4 rate"),
                (res_tier5, "Residential tier 5 rate"),
                (comm_minimum, "Commercial minimum charge"),
                (comm_tier2, "Commercial tier 2 rate"),
                (comm_tier3, "Commercial tier 3 rate"),
                (comm_tier4, "Commercial tier 4 rate"),
                (comm_tier5, "Commercial tier 5 rate"),
            ]
            for rate, name in tiered_rates:
                if rate < 0:
                    raise ValueError(f"{name} cannot be negative.")

            # Validate penalty settings
            if penalty_rate < 0 or penalty_rate > 100:
                raise ValueError("Penalty rate must be between 0 and 100 percent.")
            if fixed_penalty < 0:
                raise ValueError("Fixed penalty amount cannot be negative.")
            if grace_period < 0 or grace_period > 30:
                raise ValueError("Grace period must be between 0 and 30 days.")
            if max_penalty < 0:
                raise ValueError("Maximum penalty cannot be negative.")
            if penalty_type not in ['percentage', 'fixed']:
                raise ValueError("Invalid penalty type.")

            # Validate all schedule days are within 1-28
            for day, name in [(reading_start, "Reading start"), (reading_end, "Reading end"),
                              (billing_day, "Billing day"), (due_day, "Due day")]:
                if day < 1 or day > 28:
                    raise ValueError(f"{name} must be between 1 and 28.")

            # Validate reading period logic
            # Removed the reading_start > reading_end check to allow cross-month reading periods (e.g., 22nd to 8th)

            # =====================================================
            # UPDATE SETTINGS - All changes take effect immediately
            # =====================================================
            # Tiered Residential Rates
            setting.residential_minimum_charge = res_minimum
            setting.residential_tier2_rate = res_tier2
            setting.residential_tier3_rate = res_tier3
            setting.residential_tier4_rate = res_tier4
            setting.residential_tier5_rate = res_tier5

            # Tiered Commercial Rates
            setting.commercial_minimum_charge = comm_minimum
            setting.commercial_tier2_rate = comm_tier2
            setting.commercial_tier3_rate = comm_tier3
            setting.commercial_tier4_rate = comm_tier4
            setting.commercial_tier5_rate = comm_tier5

            # Reading Schedule (affects when mobile app shows reading period)
            setting.reading_start_day = reading_start
            setting.reading_end_day = reading_end

            # Billing Schedule (affects dates on newly generated bills)
            setting.billing_day_of_month = billing_day
            setting.due_day_of_month = due_day

            # Penalty Settings (affects penalty calculation on overdue bills)
            setting.penalty_enabled = penalty_enabled
            setting.penalty_type = penalty_type
            setting.penalty_rate = penalty_rate
            setting.fixed_penalty_amount = fixed_penalty
            setting.penalty_grace_period_days = grace_period
            setting.max_penalty_amount = max_penalty

            setting.save()

            # =====================================================
            # LOG THE CHANGE
            # =====================================================
            new_values = {
                'reading_schedule': {
                    'start_day': reading_start,
                    'end_day': reading_end,
                },
                'billing_schedule': {
                    'billing_day': billing_day,
                    'due_day': due_day,
                },
                'residential_rates': {
                    'minimum_charge': str(res_minimum),
                    'tier2_rate': str(res_tier2),
                    'tier3_rate': str(res_tier3),
                    'tier4_rate': str(res_tier4),
                    'tier5_rate': str(res_tier5),
                },
                'commercial_rates': {
                    'minimum_charge': str(comm_minimum),
                    'tier2_rate': str(comm_tier2),
                    'tier3_rate': str(comm_tier3),
                    'tier4_rate': str(comm_tier4),
                    'tier5_rate': str(comm_tier5),
                },
                'penalty_settings': {
                    'enabled': penalty_enabled,
                    'type': penalty_type,
                    'rate': str(penalty_rate),
                    'fixed_amount': str(fixed_penalty),
                    'grace_period': grace_period,
                    'max_amount': str(max_penalty),
                },
            }

            # Build change description - only include what actually changed
            changes_summary = []

            # Check residential rate changes
            prev_res = previous_values['residential_rates']
            res_changes = []
            if prev_res['minimum_charge'] != str(res_minimum):
                res_changes.append(f"Min: ₱{prev_res['minimum_charge']}→₱{res_minimum}")
            if prev_res['tier2_rate'] != str(res_tier2):
                res_changes.append(f"T2: ₱{prev_res['tier2_rate']}→₱{res_tier2}")
            if prev_res['tier3_rate'] != str(res_tier3):
                res_changes.append(f"T3: ₱{prev_res['tier3_rate']}→₱{res_tier3}")
            if prev_res['tier4_rate'] != str(res_tier4):
                res_changes.append(f"T4: ₱{prev_res['tier4_rate']}→₱{res_tier4}")
            if prev_res['tier5_rate'] != str(res_tier5):
                res_changes.append(f"T5: ₱{prev_res['tier5_rate']}→₱{res_tier5}")
            if res_changes:
                changes_summary.append(f"Residential rates: {', '.join(res_changes)}")

            # Check commercial rate changes
            prev_comm = previous_values['commercial_rates']
            comm_changes = []
            if prev_comm['minimum_charge'] != str(comm_minimum):
                comm_changes.append(f"Min: ₱{prev_comm['minimum_charge']}→₱{comm_minimum}")
            if prev_comm['tier2_rate'] != str(comm_tier2):
                comm_changes.append(f"T2: ₱{prev_comm['tier2_rate']}→₱{comm_tier2}")
            if prev_comm['tier3_rate'] != str(comm_tier3):
                comm_changes.append(f"T3: ₱{prev_comm['tier3_rate']}→₱{comm_tier3}")
            if prev_comm['tier4_rate'] != str(comm_tier4):
                comm_changes.append(f"T4: ₱{prev_comm['tier4_rate']}→₱{comm_tier4}")
            if prev_comm['tier5_rate'] != str(comm_tier5):
                comm_changes.append(f"T5: ₱{prev_comm['tier5_rate']}→₱{comm_tier5}")
            if comm_changes:
                changes_summary.append(f"Commercial rates: {', '.join(comm_changes)}")

            # Check reading schedule changes
            prev_sched = previous_values['reading_schedule']
            if prev_sched['start_day'] != reading_start or prev_sched['end_day'] != reading_end:
                changes_summary.append(f"Reading schedule: Day {prev_sched['start_day']}-{prev_sched['end_day']} → Day {reading_start}-{reading_end}")

            # Check billing schedule changes
            prev_bill = previous_values['billing_schedule']
            if prev_bill['billing_day'] != billing_day:
                changes_summary.append(f"Billing day: {prev_bill['billing_day']} → {billing_day}")
            if prev_bill['due_day'] != due_day:
                changes_summary.append(f"Due date: Day {prev_bill['due_day']} → Day {due_day}")

            # Check penalty changes
            prev_pen = previous_values['penalty_settings']
            if prev_pen['enabled'] != penalty_enabled:
                changes_summary.append(f"Penalty: {'Disabled' if prev_pen['enabled'] else 'Enabled'} → {'Enabled' if penalty_enabled else 'Disabled'}")
            if penalty_enabled and prev_pen['rate'] != str(penalty_rate):
                changes_summary.append(f"Penalty rate: {prev_pen['rate']}% → {penalty_rate}%")

            # Fallback if nothing detected as changed
            if not changes_summary:
                changes_summary.append("Settings saved (no changes detected)")

            change_description = "; ".join(changes_summary)

            # Create change log entry
            SystemSettingChangeLog.log_change(
                user=request.user,
                change_type='multiple',
                description=change_description,
                previous_values=previous_values,
                new_values=new_values,
                ip_address=get_client_ip(request)
            )

            # Log to UserActivity for backward compatibility
            if hasattr(request, 'login_event') and request.login_event:
                UserActivity.objects.create(
                    user=request.user,
                    action='system_settings_updated',
                    description=change_description,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    login_event=request.login_event
                )

            messages.success(request, "System settings updated successfully! Changes are now effective for all new bills and the mobile app.")
        except (InvalidOperation, ValueError, TypeError) as e:
            messages.error(request, f"Invalid input: {e}")
        except Exception as e:
            messages.error(request, f"Error updating settings: {e}")

        return redirect("consumers:system_management")

    # Serialize change log JSON data for the template modal
    change_data = {}
    for change in recent_changes:
        change_data[str(change.id)] = {
            'previous': change.previous_values or {},
            'new': change.new_values or {},
        }

    # For GET requests, pass the setting object to the template
    context = {
        "setting": setting,
        "recent_changes": recent_changes,
        "change_data_json": json.dumps(change_data),
    }
    return render(request, "consumers/system_management.html", context)



@login_required
def user_login_history(request):
    """
    Enhanced login history with filtering, search, and analytics.
    Restricted to superusers and admins for security.
    """
    from ..decorators import admin_or_superuser_required
    from django.db.models import Count, Q
    from datetime import timedelta
    from django.core.paginator import Paginator

    # Security check - only admins and superusers
    if not (request.user.is_superuser or (hasattr(request.user, 'staffprofile') and request.user.staffprofile.role == 'admin')):
        messages.error(request, "Access Denied: Administrative privileges required to view login history.")
        return render(request, 'consumers/403.html', status=403)

    # Get filter parameters
    search_query: str = request.GET.get('search', '').strip()
    status_filter: str = request.GET.get('status', '')
    method_filter: str = request.GET.get('method', '')
    date_from: str = request.GET.get('date_from', '')
    date_to: str = request.GET.get('date_to', '')
    barangay_filter: str = request.GET.get('barangay', '') # New barangay filter
    
    # Load barangays for the filter dropdown
    from ..models import Barangay
    barangays = Barangay.objects.all().order_by('name')

    # Get the latest event ID for each user using annotation and order_by
    # Avoid OuterRef and Subquery which can be buggy depending on DB version
    # SQLite has poor support for window functions and Subquery in typical ORMs
    
    # We grab all events first to keep the analytics math valid across the entire dataset
    
    from django.db.models import Max
    from django.db.models.functions import Coalesce

    # Show ALL login events (not just latest per user) so every login is tracked
    login_events = UserLoginEvent.objects.select_related('user').prefetch_related('activities')

    # Apply filters
    if search_query:
        login_events = login_events.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(ip_address__icontains=search_query)
        )

    if status_filter:
        login_events = login_events.filter(status=status_filter)

    if method_filter:
        login_events = login_events.filter(login_method=method_filter)

    if date_from:
        login_events = login_events.filter(login_timestamp__gte=date_from)

    if date_to:
        from datetime import datetime
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
        date_to_end = date_to_obj.replace(hour=23, minute=59, second=59)
        login_events = login_events.filter(login_timestamp__lte=date_to_end)

    if barangay_filter:
        # Filter logins where the user's staff profile is assigned to this barangay
        login_events = login_events.filter(user__staffprofile__assigned_barangay_id=barangay_filter)

    # Order by most recent
    login_events = login_events.order_by('-login_timestamp')

    # Annotate with the exact time of last activity (or login if no activities)
    login_events = login_events.annotate(
        last_activity_time=Coalesce(Max('activities__created_at'), 'login_timestamp')
    )
    # Calculate ALL Analytics in ONE query using conditional aggregation
    # Note: We calculate this across ALL login events, not just the filtered latest ones,
    # so the analytics cards remain accurate for the entire system history.
    last_24_hours = timezone.now() - timedelta(hours=24)
    idle_cutoff = timezone.now() - timedelta(hours=2) # 2 hours idle timeout
    
    all_events = UserLoginEvent.objects.all()
    stats = all_events.aggregate(
        total_logins=Count('id'),
        successful_logins=Sum(
            models.Case(
                models.When(status='success', then=1),
                default=0,
                output_field=models.IntegerField()
            )
        ),
        failed_logins=Sum(
            models.Case(
                models.When(status='failed', then=1),
                default=0,
                output_field=models.IntegerField()
            )
        ),
        active_sessions=Sum(
            models.Case(
                models.When(status='success', logout_timestamp__isnull=True, then=1),
                default=0,
                output_field=models.IntegerField()
            )
        ),
        recent_logins=Sum(
            models.Case(
                models.When(login_timestamp__gte=last_24_hours, then=1),
                default=0,
                output_field=models.IntegerField()
            )
        )
    )
    
    total_logins = stats['total_logins'] or 0
    successful_logins = stats['successful_logins'] or 0
    failed_logins = stats['failed_logins'] or 0
    active_sessions = stats['active_sessions'] or 0
    recent_logins = stats['recent_logins'] or 0

    # Top users
    top_users = User.objects.annotate(
        login_count=Count('userloginevent')
    ).filter(login_count__gt=0).order_by('-login_count')[:5]

    # Pagination
    paginator = Paginator(login_events, 25)  # 25 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'login_events': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'method_filter': method_filter,
        'date_from': date_from,
        'date_to': date_to,
        'barangays': barangays,
        'barangay_filter': barangay_filter,
        # Analytics
        'total_logins': total_logins,
        'successful_logins': successful_logins,
        'failed_logins': failed_logins,
        'active_sessions': active_sessions,
        'recent_logins': recent_logins,
        'top_users': top_users,
    }
    return render(request, 'consumers/user_login_history.html', context)



@login_required
def user_specific_login_history(request, user_id):
    """
    Detailed login history for a specific user.
    """
    from django.shortcuts import get_object_or_404
    from django.core.paginator import Paginator
    
    # Security check - only admins and superusers
    if not (request.user.is_superuser or (hasattr(request.user, 'staffprofile') and request.user.staffprofile.role == 'admin')):
        messages.error(request, "Access Denied: Administrative privileges required to view login history.")
        return render(request, 'consumers/403.html', status=403)

    target_user = get_object_or_404(User, id=user_id)
    
    # Base query - prefetch activities for session tracking
    login_events = UserLoginEvent.objects.filter(user=target_user).prefetch_related('activities').order_by('-login_timestamp')

    # Pagination
    paginator = Paginator(login_events, 25)  # 25 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'target_user': target_user,
        'login_events': page_obj,
    }
    return render(request, 'consumers/user_specific_login_history.html', context)



@login_required
def session_activities(request, session_id):
    """
    View detailed activities for a specific login session.
    Shows all meter readings and actions performed during the session.
    """
    # Security check - only admins and superusers
    if not (request.user.is_superuser or (hasattr(request.user, 'staffprofile') and request.user.staffprofile.role == 'admin')):
        messages.error(request, "Access Denied: Administrative privileges required.")
        return render(request, 'consumers/403.html', status=403)

    login_event = get_object_or_404(UserLoginEvent, id=session_id)
    activities = UserActivity.objects.filter(login_event=login_event).order_by('-created_at')

    # Calculate session stats
    total_readings = activities.filter(action='meter_reading_submitted').count()

    context = {
        'login_event': login_event,
        'activities': activities,
        'total_readings': total_readings,
    }
    return render(request, 'consumers/session_activities.html', context)


@login_required
def admin_verification(request):
    """
    Admin verification - requires password re-entry before accessing user management.
    Provides extra security layer for sensitive operations.
    """
    from ..decorators import get_client_ip
    from django.contrib.auth import authenticate

    # Only superusers and admins can access this page
    if not (request.user.is_superuser or (hasattr(request.user, 'staffprofile') and request.user.staffprofile.role == 'admin')):
        messages.error(request, "Access Denied: Administrative privileges required.")
        return render(request, 'consumers/403.html', status=403)

    if request.method == 'POST':
        password = request.POST.get('password', '')
        destination = request.POST.get('destination', 'user_management')

        # Verify the password
        user = authenticate(username=request.user.username, password=password)

        if user is not None and user == request.user:
            # Password verified - store verification in session with timestamp
            request.session['admin_verified'] = True
            request.session['admin_verified_time'] = timezone.now().isoformat()

            # Log the verification
            UserLoginEvent.objects.create(
                user=request.user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                login_method='web',
                status='success',
                session_key=request.session.session_key
            )

            messages.success(request, "Admin verification successful!")

            # Redirect to requested destination
            if destination == 'django_admin':
                return redirect('/admin/')
            else:
                return redirect('consumers:user_management')
        else:
            # Failed verification
            messages.error(request, "Incorrect password. Verification failed.")
            UserLoginEvent.objects.create(
                user=request.user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                login_method='web',
                status='failed'
            )

    return render(request, 'consumers/admin_verification.html')



@login_required
@user_management_permission_required
def user_management(request):
    """
    Custom user management interface with enhanced security.
    RESTRICTED: Superuser only - Admins cannot manage users.
    """
    from django.db.models import Count, Q
    from django.core.paginator import Paginator

    # Check if admin verification is required and not expired
    admin_verified = request.session.get('admin_verified', False)
    admin_verified_time_str = request.session.get('admin_verified_time')

    # Check if verification has expired (15 minutes = 900 seconds)
    verification_expired = False
    if admin_verified and admin_verified_time_str:
        try:
            from datetime import timedelta
            verified_time = timezone.datetime.fromisoformat(admin_verified_time_str)
            if timezone.is_naive(verified_time):
                verified_time = timezone.make_aware(verified_time)
            time_since_verification = timezone.now() - verified_time
            if time_since_verification > timedelta(minutes=15):
                verification_expired = True
                # Clear expired verification
                request.session.pop('admin_verified', None)
                request.session.pop('admin_verified_time', None)
        except (ValueError, TypeError):
            verification_expired = True

    if not admin_verified or verification_expired:
        # Redirect to verification page
        if verification_expired:
            messages.warning(request, "Admin verification expired. Please verify again.")
        else:
            messages.warning(request, "Admin verification required to access User Management.")
        return redirect('consumers:admin_verification')

    # Get filter parameters
    search_query = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')

    # Base query
    users = User.objects.all()

    # Apply filters
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    if role_filter:
        if role_filter == 'superuser':
            users = users.filter(is_superuser=True)
        elif role_filter == 'staff':
            users = users.filter(is_staff=True, is_superuser=False)
        elif role_filter == 'regular':
            users = users.filter(is_staff=False, is_superuser=False)

    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)

    # Annotate with login count
    users = users.annotate(
        login_count=Count('userloginevent')
    ).select_related('staffprofile').order_by('-date_joined')

    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    superusers = User.objects.filter(is_superuser=True).count()

    # Available barangays for assignment
    barangays = Barangay.objects.all()

    context = {
        'users': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'total_users': total_users,
        'active_users': active_users,
        'staff_users': staff_users,
        'superusers': superusers,
        'barangays': barangays,
    }
    return render(request, 'consumers/user_management.html', context)



@login_required
@user_management_permission_required
def create_user(request):
    """
    Create a new user with security validations.
    RESTRICTED: Superuser only - Admins cannot create users.
    """
    from ..decorators import check_password_strength
    from django.contrib.auth.hashers import make_password

    # Helper function for proper casing
    def proper_case(value):
        """Convert string to proper case (Title Case)."""
        if not value:
            return value
        return ' '.join(word.capitalize() for word in value.strip().split())

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        # Apply proper casing to first name and last name
        first_name = proper_case(request.POST.get('first_name', '').strip())
        last_name = proper_case(request.POST.get('last_name', '').strip())
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        assigned_barangay_id = request.POST.get('assigned_barangay')
        role = request.POST.get('role', 'field_staff')

        # Automatically set is_staff=True for all users (required for login)
        # Set is_superuser=True only for superadmin role
        is_staff = True
        is_superuser = role == 'superadmin'

        # Validation - require first name and last name
        if not first_name or not last_name:
            messages.error(request, "First name and last name are required.")
            return redirect('consumers:user_management')

        # Validation
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect('consumers:user_management')

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return redirect('consumers:user_management')

        # Check password strength
        is_strong, msg = check_password_strength(password)
        if not is_strong:
            messages.error(request, f"Weak password: {msg}")
            return redirect('consumers:user_management')

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
            return redirect('consumers:user_management')

        # Only superusers can create other superusers
        if is_superuser and not request.user.is_superuser:
            messages.error(request, "Access Denied: Only superusers can create other superusers.")
            return redirect('consumers:user_management')

        try:
            # Create user
            user = User.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_staff=is_staff,
                is_superuser=is_superuser,
                is_active=True
            )
            user.set_password(password)
            user.save()

            # Always create staff profile (required for login on both web and app)
            # Field staff requires barangay for mobile app access
            if role == 'field_staff' and not assigned_barangay_id:
                messages.warning(request, f"User '{username}' created but field staff should have an assigned barangay.")

            barangay = None
            if assigned_barangay_id:
                barangay = Barangay.objects.get(id=assigned_barangay_id)

            StaffProfile.objects.create(
                user=user,
                assigned_barangay=barangay,
                role=role
            )

            messages.success(request, f"User '{username}' created successfully!")
            return redirect('consumers:user_management')

        except Exception as e:
            messages.error(request, f"Error creating user: {str(e)}")
            return redirect('consumers:user_management')

    return redirect('consumers:user_management')



@login_required
@user_management_permission_required
def edit_user(request, user_id):
    """
    Edit user details with security checks.
    RESTRICTED: Superuser only - Admins cannot edit users.
    """
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.is_staff = request.POST.get('is_staff') == 'on'
        user.is_active = request.POST.get('is_active') == 'on'

        # Only allow changing superuser status if current user is superuser
        if request.user.is_superuser:
            user.is_superuser = request.POST.get('is_superuser') == 'on'

        user.save()

        # Update staff profile
        assigned_barangay_id = request.POST.get('assigned_barangay')
        role = request.POST.get('role', 'field_staff')

        barangay = None
        if assigned_barangay_id:
            barangay = Barangay.objects.get(id=assigned_barangay_id)
            
        profile, created = StaffProfile.objects.get_or_create(user=user)
        profile.assigned_barangay = barangay
        profile.role = role
        profile.save()

        messages.success(request, f"User '{user.username}' updated successfully!")
        return redirect('consumers:user_management')

    return redirect('consumers:user_management')



@login_required
@user_management_permission_required
def delete_user(request, user_id):
    """
    Delete a user.
    RESTRICTED: Superuser only - Admins cannot delete users.
    """
    user = get_object_or_404(User, id=user_id)

    # Prevent self-deletion
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('consumers:user_management')

    if request.method == 'POST':
        username = user.username

        # Delete the user
        user.delete()

        messages.success(request, f"User '{username}' has been deleted successfully!")
        return redirect('consumers:user_management')

    return redirect('consumers:user_management')



@login_required


def reset_user_password(request, user_id):
    """Reset user password (superuser and admin)."""
    from ..decorators import check_password_strength

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not (request.user.is_superuser or (hasattr(request.user, 'staffprofile') and request.user.staffprofile.role == 'admin')):
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Access denied: Administrative privileges required.'})
        messages.error(request, "Access Denied: Administrative privileges required to reset passwords.")
        return redirect('consumers:user_management')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if new_password != confirm_password:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'Passwords do not match.'})
            messages.error(request, "Passwords do not match.")
            return redirect('consumers:user_management')

        # Check password strength
        is_strong, msg = check_password_strength(new_password)
        if not is_strong:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': f'Weak password: {msg}'})
            messages.error(request, f"Weak password: {msg}")
            return redirect('consumers:user_management')

        user.set_password(new_password)
        user.save()
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': f"Password reset successfully for user '{user.username}'!"})
        messages.success(request, f"Password reset successfully for user '{user.username}'!")
        return redirect('consumers:user_management')

    return redirect('consumers:user_management')



# ===========================
# DATABASE DOCUMENTATION VIEW
# ===========================
@login_required
def database_documentation(request):
    """Display database schema, tables, and test data in a user-friendly UI."""

    # Get database statistics
    context = {
        # Table counts
        'total_consumers': Consumer.objects.count(),
        'total_barangays': Barangay.objects.count(),
        'total_puroks': Purok.objects.count(),
        'total_meter_brands': MeterBrand.objects.count(),
        'total_meter_readings': MeterReading.objects.count(),
        'total_bills': Bill.objects.count(),
        'total_payments': Payment.objects.count(),
        'total_users': User.objects.count(),

        # Sample data - Barangays
        'barangays': Barangay.objects.all().order_by('name')[:10],

        # Sample data - Puroks
        'puroks': Purok.objects.select_related('barangay').all()[:10],

        # Sample data - Meter Brands
        'meter_brands': MeterBrand.objects.all(),

        # Sample data - Consumers
        'consumers': Consumer.objects.select_related('barangay', 'purok', 'meter_brand').all()[:8],

        # Sample data - Meter Readings
        'meter_readings': MeterReading.objects.select_related('consumer').order_by('-reading_date')[:10],

        # Sample data - Bills
        'bills': Bill.objects.select_related('consumer', 'current_reading', 'previous_reading').order_by('-billing_period')[:10],

        # Sample data - Payments
        'payments': Payment.objects.select_related('bill', 'bill__consumer').order_by('-payment_date')[:10],

        # System Settings
        'system_settings': SystemSetting.objects.first(),
    }

    # Calculate sample billing amounts for display
    if context['system_settings']:
        settings = context['system_settings']
        # Residential example (15 m³)
        residential_consumption = 15
        residential_water_charge = settings.residential_rate_per_cubic * residential_consumption
        residential_total = residential_water_charge + settings.fixed_charge

        # Commercial example (30 m³)
        commercial_consumption = 30
        commercial_water_charge = settings.commercial_rate_per_cubic * commercial_consumption
        commercial_total = commercial_water_charge + settings.fixed_charge

        context.update({
            'residential_consumption': residential_consumption,
            'residential_water_charge': residential_water_charge,
            'residential_total': residential_total,
            'commercial_consumption': commercial_consumption,
            'commercial_water_charge': commercial_water_charge,
            'commercial_total': commercial_total,
        })

    # Database schema information
    context['database_tables'] = [
            {
                'name': 'Barangay',
                'model': 'consumers_barangay',
                'description': 'Stores barangay (village) information',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'name', 'type': 'VARCHAR(100)', 'constraints': 'UNIQUE, NOT NULL', 'description': 'Barangay name'},
                ]
            },
            {
                'name': 'Purok',
                'model': 'consumers_purok',
                'description': 'Stores purok (zone) information within barangays',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'name', 'type': 'VARCHAR(100)', 'constraints': 'NOT NULL', 'description': 'Purok name'},
                    {'name': 'barangay_id', 'type': 'INTEGER', 'constraints': 'FOREIGN KEY', 'description': 'Reference to Barangay'},
                ]
            },
            {
                'name': 'MeterBrand',
                'model': 'consumers_meterbrand',
                'description': 'Stores water meter brand information',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'name', 'type': 'VARCHAR(100)', 'constraints': 'UNIQUE, NOT NULL', 'description': 'Meter brand name'},
                ]
            },
            {
                'name': 'Consumer',
                'model': 'consumers_consumer',
                'description': 'Main consumer information table with personal, household, and meter details',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'id_number', 'type': 'VARCHAR(20)', 'constraints': 'UNIQUE, AUTO', 'description': 'Format: YYYYMMXXXX'},
                    {'name': 'first_name', 'type': 'VARCHAR(50)', 'constraints': 'NOT NULL', 'description': 'First name'},
                    {'name': 'middle_name', 'type': 'VARCHAR(50)', 'constraints': 'NULL', 'description': 'Middle name'},
                    {'name': 'last_name', 'type': 'VARCHAR(50)', 'constraints': 'NOT NULL', 'description': 'Last name'},
                    {'name': 'birth_date', 'type': 'DATE', 'constraints': 'NOT NULL', 'description': 'Date of birth'},
                    {'name': 'gender', 'type': 'VARCHAR(10)', 'constraints': 'NOT NULL', 'description': 'Male/Female/Other'},
                    {'name': 'phone_number', 'type': 'VARCHAR(15)', 'constraints': 'NOT NULL', 'description': 'Contact number'},
                    {'name': 'status', 'type': 'VARCHAR(20)', 'constraints': "DEFAULT 'active'", 'description': 'active/disconnected'},
                ]
            },
            {
                'name': 'MeterReading',
                'model': 'consumers_meterreading',
                'description': 'Stores meter reading records with confirmation status',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'consumer_id', 'type': 'INTEGER', 'constraints': 'FOREIGN KEY', 'description': 'Reference to Consumer'},
                    {'name': 'reading_date', 'type': 'DATE', 'constraints': 'NOT NULL', 'description': 'Date of reading'},
                    {'name': 'reading_value', 'type': 'INTEGER', 'constraints': 'NOT NULL', 'description': 'Cumulative meter value'},
                    {'name': 'is_confirmed', 'type': 'BOOLEAN', 'constraints': 'DEFAULT FALSE', 'description': 'Confirmation status'},
                ]
            },
            {
                'name': 'Bill',
                'model': 'consumers_bill',
                'description': 'Stores billing information with consumption and payment status',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'consumer_id', 'type': 'INTEGER', 'constraints': 'FOREIGN KEY', 'description': 'Reference to Consumer'},
                    {'name': 'billing_period', 'type': 'DATE', 'constraints': 'NOT NULL', 'description': 'First day of billing month'},
                    {'name': 'consumption', 'type': 'INTEGER', 'constraints': 'NOT NULL', 'description': 'Water consumption (m³)'},
                    {'name': 'total_amount', 'type': 'DECIMAL(10,2)', 'constraints': 'NOT NULL', 'description': 'Total bill amount'},
                    {'name': 'status', 'type': 'VARCHAR(20)', 'constraints': "DEFAULT 'Pending'", 'description': 'Pending/Paid/Overdue'},
                ]
            },
            {
                'name': 'Payment',
                'model': 'consumers_payment',
                'description': 'Records all payment transactions with OR numbers',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'bill_id', 'type': 'INTEGER', 'constraints': 'FOREIGN KEY', 'description': 'Reference to Bill'},
                    {'name': 'amount_paid', 'type': 'DECIMAL(10,2)', 'constraints': 'NOT NULL', 'description': 'Bill amount'},
                    {'name': 'or_number', 'type': 'VARCHAR(50)', 'constraints': 'UNIQUE, AUTO', 'description': 'Official Receipt number'},
                    {'name': 'payment_date', 'type': 'DATETIME', 'constraints': 'AUTO', 'description': 'Payment timestamp'},
                ]
            },
            {
                'name': 'SystemSetting',
                'model': 'consumers_systemsetting',
                'description': 'System-wide configuration settings for billing rates',
                'fields': [
                    {'name': 'id', 'type': 'INTEGER', 'constraints': 'PRIMARY KEY', 'description': 'Auto-increment ID'},
                    {'name': 'residential_rate_per_cubic', 'type': 'DECIMAL(10,2)', 'constraints': 'DEFAULT 22.50', 'description': 'Residential rate (₱/m³)'},
                    {'name': 'commercial_rate_per_cubic', 'type': 'DECIMAL(10,2)', 'constraints': 'DEFAULT 25.00', 'description': 'Commercial rate (₱/m³)'},
                    {'name': 'fixed_charge', 'type': 'DECIMAL(10,2)', 'constraints': 'DEFAULT 50.00', 'description': 'Fixed monthly charge'},
                ]
            },
        ]

    return render(request, 'consumers/database_documentation.html', context)


@login_required
def test_email(request):
    """
    Test email configuration - only accessible by superusers.
    Provides detailed debugging information for SMTP issues.
    """
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Superuser access required'}, status=403)

    import smtplib
    import logging
    from django.core.mail import send_mail, get_connection
    from django.http import JsonResponse

    logger = logging.getLogger(__name__)

    # Collect configuration info (without password)
    config_info = {
        'EMAIL_BACKEND': settings.EMAIL_BACKEND,
        'EMAIL_HOST': settings.EMAIL_HOST,
        'EMAIL_PORT': settings.EMAIL_PORT,
        'EMAIL_USE_TLS': settings.EMAIL_USE_TLS,
        'EMAIL_USE_SSL': getattr(settings, 'EMAIL_USE_SSL', False),
        'EMAIL_HOST_USER': settings.EMAIL_HOST_USER or '(not set)',
        'EMAIL_HOST_PASSWORD': '***SET***' if settings.EMAIL_HOST_PASSWORD else '(not set)',
        'DEFAULT_FROM_EMAIL': settings.DEFAULT_FROM_EMAIL,
        'EMAIL_TIMEOUT': getattr(settings, 'EMAIL_TIMEOUT', 'default'),
    }

    result = {
        'config': config_info,
        'tests': [],
        'success': False,
        'error': None
    }

    # Test 1: Check if credentials are set
    if not settings.EMAIL_HOST_USER:
        result['tests'].append({
            'name': 'Check EMAIL_HOST_USER',
            'status': 'FAIL',
            'message': 'EMAIL_HOST_USER is empty. Set it in Vercel environment variables.'
        })
        result['error'] = 'EMAIL_HOST_USER not configured'
        return JsonResponse(result)
    else:
        result['tests'].append({
            'name': 'Check EMAIL_HOST_USER',
            'status': 'PASS',
            'message': f'Set to: {settings.EMAIL_HOST_USER}'
        })

    if not settings.EMAIL_HOST_PASSWORD:
        result['tests'].append({
            'name': 'Check EMAIL_HOST_PASSWORD',
            'status': 'FAIL',
            'message': 'EMAIL_HOST_PASSWORD is empty. Set it in Vercel environment variables.'
        })
        result['error'] = 'EMAIL_HOST_PASSWORD not configured'
        return JsonResponse(result)
    else:
        result['tests'].append({
            'name': 'Check EMAIL_HOST_PASSWORD',
            'status': 'PASS',
            'message': f'Set (length: {len(settings.EMAIL_HOST_PASSWORD)} chars)'
        })

    # Test 2: Try SMTP connection
    try:
        result['tests'].append({
            'name': 'SMTP Connection Test',
            'status': 'TESTING',
            'message': f'Connecting to {settings.EMAIL_HOST}:{settings.EMAIL_PORT}...'
        })

        # Create SMTP connection
        if settings.EMAIL_USE_TLS:
            server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10)

        result['tests'][-1]['status'] = 'PASS'
        result['tests'][-1]['message'] = 'Connected to Gmail SMTP server'

        # Test 3: Try authentication
        result['tests'].append({
            'name': 'SMTP Authentication',
            'status': 'TESTING',
            'message': 'Authenticating...'
        })

        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)

        result['tests'][-1]['status'] = 'PASS'
        result['tests'][-1]['message'] = 'Authentication successful!'

        server.quit()

        # Test 4: Try sending a test email
        if request.GET.get('send') == 'true':
            to_email = request.GET.get('to', request.user.email)
            result['tests'].append({
                'name': 'Send Test Email',
                'status': 'TESTING',
                'message': f'Sending to {to_email}...'
            })

            try:
                send_mail(
                    subject='Test Email - Balilihan Waterworks',
                    message='This is a test email from Balilihan Waterworks. If you received this, email is working correctly!',
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[to_email],
                    fail_silently=False,
                )
                result['tests'][-1]['status'] = 'PASS'
                result['tests'][-1]['message'] = f'Email sent successfully to {to_email}'
                result['success'] = True
            except Exception as e:
                result['tests'][-1]['status'] = 'FAIL'
                result['tests'][-1]['message'] = f'Send failed: {str(e)}'
                result['error'] = str(e)
        else:
            result['success'] = True
            result['tests'].append({
                'name': 'Ready to Send',
                'status': 'INFO',
                'message': 'Add ?send=true&to=email@example.com to send a test email'
            })

    except smtplib.SMTPAuthenticationError as e:
        result['tests'][-1]['status'] = 'FAIL'
        result['tests'][-1]['message'] = f'Authentication failed: {str(e)}'
        result['error'] = 'Gmail authentication failed. Make sure you are using an App Password, not your regular Gmail password.'
        result['help'] = [
            '1. Go to https://myaccount.google.com/security',
            '2. Enable 2-Step Verification if not already enabled',
            '3. Go to App passwords (https://myaccount.google.com/apppasswords)',
            '4. Generate a new App Password for "Mail"',
            '5. Use that 16-character password (without spaces) as EMAIL_HOST_PASSWORD'
        ]
    except smtplib.SMTPConnectError as e:
        result['tests'][-1]['status'] = 'FAIL'
        result['tests'][-1]['message'] = f'Connection failed: {str(e)}'
        result['error'] = 'Could not connect to Gmail SMTP server'
    except Exception as e:
        if result['tests']:
            result['tests'][-1]['status'] = 'FAIL'
            result['tests'][-1]['message'] = f'Error: {str(e)}'
        result['error'] = str(e)
        logger.error(f"Email test error: {e}", exc_info=True)

    return JsonResponse(result, json_dumps_params={'indent': 2})


@login_required
@user_management_permission_required
def area_management(request):
    """
    Dedicated view for managing Barangays and Puroks natively.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # --- BARANGAY ACTIONS ---
        if action == 'add_barangay':
            name = request.POST.get('barangay_name', '').strip()
            if name:
                if Barangay.objects.filter(name__iexact=name).exists():
                    messages.error(request, f"Barangay '{name}' already exists.")
                else:
                    Barangay.objects.create(name=name)
                    messages.success(request, f"Barangay '{name}' added successfully.")
            return redirect('consumers:area_management')
            
        elif action == 'edit_barangay':
            barangay_id = request.POST.get('barangay_id')
            new_name = request.POST.get('barangay_name', '').strip()
            if barangay_id and new_name:
                barangay = get_object_or_404(Barangay, id=barangay_id)
                if Barangay.objects.filter(name__iexact=new_name).exclude(id=barangay_id).exists():
                    messages.error(request, f"Barangay '{new_name}' already exists.")
                else:
                    barangay.name = new_name
                    barangay.save()
                    messages.success(request, "Barangay updated successfully.")
            return redirect('consumers:area_management')
            
        elif action == 'delete_barangay':
            barangay_id = request.POST.get('barangay_id')
            if barangay_id:
                barangay = get_object_or_404(Barangay, id=barangay_id)
                # Check if it has consumers assigned
                if Consumer.objects.filter(barangay=barangay).exists():
                    messages.error(request, f"Cannot delete '{barangay.name}' because consumers are assigned to it.")
                else:
                    name = barangay.name
                    barangay.delete()
                    messages.success(request, f"Barangay '{name}' deleted successfully.")
            return redirect('consumers:area_management')
            
        # --- PUROK ACTIONS ---
        elif action == 'add_purok':
            barangay_id = request.POST.get('barangay_id')
            name = request.POST.get('purok_name', '').strip()
            if barangay_id and name:
                barangay = get_object_or_404(Barangay, id=barangay_id)
                if Purok.objects.filter(name__iexact=name, barangay=barangay).exists():
                    messages.error(request, f"Purok '{name}' already exists in this barangay.")
                else:
                    Purok.objects.create(name=name, barangay=barangay)
                    messages.success(request, f"Purok '{name}' added successfully.")
            return redirect(f"{reverse('consumers:area_management')}?barangay={barangay_id}")
            
        elif action == 'edit_purok':
            purok_id = request.POST.get('purok_id')
            new_name = request.POST.get('purok_name', '').strip()
            if purok_id and new_name:
                purok = get_object_or_404(Purok, id=purok_id)
                if Purok.objects.filter(name__iexact=new_name, barangay=purok.barangay).exclude(id=purok_id).exists():
                    messages.error(request, f"Purok '{new_name}' already exists in this barangay.")
                else:
                    purok.name = new_name
                    purok.save()
                    messages.success(request, "Purok updated successfully.")
            # Redirect back to the selected barangay
            purok = get_object_or_404(Purok, id=request.POST.get('purok_id'))
            return redirect(f"{reverse('consumers:area_management')}?barangay={purok.barangay.id}")
            
        elif action == 'delete_purok':
            purok_id = request.POST.get('purok_id')
            if purok_id:
                purok = get_object_or_404(Purok, id=purok_id)
                barangay_id = purok.barangay.id
                # Check if it has consumers assigned
                if Consumer.objects.filter(purok=purok).exists():
                    messages.error(request, f"Cannot delete '{purok.name}' because consumers are assigned to it.")
                else:
                    name = purok.name
                    purok.delete()
                    messages.success(request, f"Purok '{name}' deleted successfully.")
                return redirect(f"{reverse('consumers:area_management')}?barangay={barangay_id}")

    # GET request handler
    barangays = Barangay.objects.all().order_by('name')
    selected_barangay = None
    puroks = []
    
    barangay_id = request.GET.get('barangay')
    if barangay_id:
        selected_barangay = get_object_or_404(Barangay, id=barangay_id)
        puroks = selected_barangay.puroks.all().order_by('name')

    context = {
        'barangays': barangays,
        'selected_barangay': selected_barangay,
        'puroks': puroks,
    }
    return render(request, 'consumers/area_management.html', context)
