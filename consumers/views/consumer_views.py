from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
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
from django.db.models import (
    Q, Max, Count, Sum, OuterRef, Subquery, Value, F,
    Case, When, CharField
)
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
def export_delinquent_consumers(request):
    month = request.GET.get('month')
    year = request.GET.get('year')

    # Use billing_period (not billing_date)
    bills = Bill.objects.filter(status='Pending')
    if month and year:
        bills = bills.filter(billing_period__month=month, billing_period__year=year)

    consumers = Consumer.objects.filter(bills__in=bills).distinct()

    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="delinquent_consumers_{month or "all"}_{year or "all"}.csv"'},
    )

    writer = csv.writer(response)
    writer.writerow(['First Name', 'Middle Name', 'Last Name', 'Phone', 'Barangay', 'Serial', 'Pending Bills'])

    for consumer in consumers:
        pending_bills = consumer.bills.filter(status='Pending')
        total_pending = sum(b.total_amount for b in pending_bills)  # Use total_amount
        writer.writerow([
            consumer.first_name,
            consumer.middle_name or "",
            consumer.last_name,
            consumer.phone_number,
            consumer.barangay.name if consumer.barangay else "",
            consumer.serial_number,
            total_pending
        ])

    return response


@login_required
def connected_consumers(request):
    # Optimize query with select_related
    consumers = Consumer.objects.filter(status='active').select_related('barangay', 'purok')

    # Count by usage type from the full queryset
    residential_count = consumers.filter(usage_type='Residential').count()
    commercial_count = consumers.filter(usage_type='Commercial').count()

    # Pagination
    paginator = Paginator(consumers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'consumers/consumer_list_filtered.html', {
        'title': 'Connected Consumers',
        'consumers': page_obj,
        'residential_count': residential_count,
        'commercial_count': commercial_count,
    })



# 1. LIST VIEW: Show all disconnected consumers (no ID needed)
@login_required
def disconnected_consumers_list(request):
    # Optimize query with select_related
    consumers = Consumer.objects.filter(status='disconnected').select_related('barangay', 'purok')
    
    # Count by usage type from the full queryset
    residential_count = consumers.filter(usage_type='Residential').count()
    commercial_count = consumers.filter(usage_type='Commercial').count()
    
    # Pagination
    paginator = Paginator(consumers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'consumers/consumer_list_filtered.html', {
        'title': 'Disconnected Consumers',
        'consumers': page_obj,
        'residential_count': residential_count,
        'commercial_count': commercial_count,
    })


# 2. ACTION VIEW: Disconnect a specific consumer (requires ID)
@login_required
@disconnect_permission_required
def disconnect_consumer(request, consumer_id):
    """RESTRICTED: Superuser only - Admins cannot disconnect consumers."""
    consumer = get_object_or_404(Consumer, id=consumer_id)
    if request.method == 'POST':
        consumer.status = 'disconnected'
        consumer.disconnect_reason = request.POST.get('reason', '')
        consumer.save()

        # Track activity
        try:
            current_session = UserLoginEvent.objects.filter(
                user=request.user,
                logout_timestamp__isnull=True,
                status='success'
            ).order_by('-login_timestamp').first()

            UserActivity.objects.create(
                user=request.user,
                action='consumer_disconnected',
                description=f"Disconnected consumer: {consumer.first_name} {consumer.last_name} ({consumer.id_number}). Reason: {consumer.disconnect_reason or 'Not specified'}",
                login_event=current_session
            )
        except Exception:
            pass

        messages.success(request, f"{consumer.full_name} has been disconnected.")
        return redirect('consumers:disconnected_consumers')
    return render(request, 'consumers/confirm_disconnect.html', {'consumer': consumer})


@login_required
@disconnect_permission_required
def reconnect_consumer(request, consumer_id):
    """RESTRICTED: Superuser only - Admins cannot reconnect consumers."""
    consumer = get_object_or_404(Consumer, id=consumer_id)
    if request.method == 'POST':
        consumer.status = 'active'
        consumer.disconnect_reason = ''  # Optional: clear reason
        consumer.save()

        # Track activity
        try:
            current_session = UserLoginEvent.objects.filter(
                user=request.user,
                logout_timestamp__isnull=True,
                status='success'
            ).order_by('-login_timestamp').first()

            UserActivity.objects.create(
                user=request.user,
                action='consumer_reconnected',
                description=f"Reconnected consumer: {consumer.first_name} {consumer.last_name} ({consumer.id_number})",
                login_event=current_session
            )
        except Exception:
            pass

        messages.success(request, f"{consumer.full_name} has been reconnected.")
        return redirect('consumers:consumer_detail', consumer.id)
    # Optional: handle GET with confirmation, but POST-only is simpler
    return redirect('consumers:consumer_detail', consumer.id)



@login_required
def delinquent_consumers(request):
    month = request.GET.get('month')
    year = request.GET.get('year')

    bills = Bill.objects.filter(status='Pending')
    if month and year:
        bills = bills.filter(billing_period__month=month, billing_period__year=year)

    # Optimize query with select_related
    consumers = Consumer.objects.filter(bills__in=bills).select_related('barangay', 'purok').distinct()

    # Count by usage type from the full queryset
    residential_count = consumers.filter(usage_type='Residential').count()
    commercial_count = consumers.filter(usage_type='Commercial').count()

    # Pagination
    paginator = Paginator(consumers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'consumers/consumer_list_filtered.html', {
        'title': 'Delinquent Consumers',
        'consumers': page_obj,
        'selected_month': month,
        'selected_year': year,
        'residential_count': residential_count,
        'commercial_count': commercial_count,
    })



@login_required
def delinquent_report_printable(request):
    """Printable delinquent report with receipt-style header"""
    from calendar import month_name

    month = request.GET.get('month')
    year = request.GET.get('year')

    if not month or not year:
        messages.error(request, 'Month and year are required')
        return redirect('consumers:home')

    # Get all pending bills for the specified month/year
    bills = Bill.objects.filter(
        status='Pending',
        billing_period__month=month,
        billing_period__year=year
    ).select_related(
        'consumer__barangay',
        'consumer__purok',
        'previous_reading',
        'current_reading'
    ).order_by('consumer__id_number')

    # Calculate totals
    total_amount = sum(bill.total_amount for bill in bills)
    total_consumers = bills.count()

    # Format month display
    month_display = f"{month_name[int(month)]} {year}"

    context = {
        'bills': bills,
        'total_amount': total_amount,
        'total_consumers': total_consumers,
        'month_display': month_display,
        'month': month,
        'year': year,
        'generated_date': timezone.now()
    }

    return render(request, 'consumers/delinquent_report_print.html', context)



@login_required
def consumer_management(request):
    """Display consumer list with filters and modal form"""
    search_query = request.GET.get('search', '').strip()
    barangay_filter = request.GET.get('barangay', '').strip()

    # Optimize query with select_related to avoid N+1 queries
    consumers = Consumer.objects.select_related('barangay', 'purok', 'meter_brand').all()
    if search_query:
        # Search by name, ID number, or serial number
        consumers = consumers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(id_number__icontains=search_query) |
            Q(serial_number__icontains=search_query)
        )
    if barangay_filter:
        consumers = consumers.filter(barangay__id=barangay_filter)

    # Always pass a fresh form for the modal
    form = ConsumerForm()

    # Pagination
    paginator = Paginator(consumers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'consumers': page_obj,
        'form': form,
        'search_query': search_query,
        'barangays': Barangay.objects.all(),
        'barangay_filter': barangay_filter,
    }
    return render(request, 'consumers/consumer_management.html', context)



@login_required
@consumer_edit_permission_required
def download_consumer_template(request):
    """
    Returns a downloadable CSV file that serves as a template for bulk consumer import.
    The file contains the required column headers and one example row.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="consumer_import_template.csv"'

    writer = csv.writer(response)
    # Header row
    writer.writerow([
        'first_name', 'middle_name', 'last_name', 'suffix',
        'birth_date', 'gender', 'phone_number',
        'civil_status', 'spouse_name',
        'barangay', 'purok', 'household_number',
        'usage_type', 'meter_brand', 'serial_number',
        'first_reading', 'registration_date', 'status'
    ])
    # Example row
    writer.writerow([
        'Juan', 'Santos', 'Dela Cruz', '',
        '1985-06-15', 'Male', '09171234567',
        'Married', 'Maria Dela Cruz',
        'Poblacion', 'Purok 1', 'HH-001',
        'Residential', 'Actaris', 'SN-12345678',
        '100', '2025-01-01', 'active'
    ])
    return response


@login_required
def export_consumers_by_barangay(request):
    """
    Exports consumer data filtered by barangay as a CSV file.
    The columns match exactly the consumer import template format so the file
    can be re-imported after edits.

    GET params:
        barangay_id  – (optional) ID of the Barangay to filter by.
                       If empty / 0, exports ALL consumers.
    """
    import csv as _csv
    from django.http import HttpResponse as _HR

    barangay_id = request.GET.get('barangay_id', '').strip()

    consumers_qs = Consumer.objects.select_related(
        'barangay', 'purok', 'meter_brand'
    ).order_by('barangay__name', 'last_name', 'first_name')

    if barangay_id:
        consumers_qs = consumers_qs.filter(barangay__id=barangay_id)
        try:
            brgy_name = Barangay.objects.get(id=barangay_id).name
            filename = f"consumers_{brgy_name.replace(' ', '_')}.csv"
        except Barangay.DoesNotExist:
            filename = "consumers_export.csv"
    else:
        filename = "consumers_all_barangays.csv"

    response = _HR(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = _csv.writer(response)
    # ---- Header row (same columns as the import template) ----
    writer.writerow([
        'first_name', 'middle_name', 'last_name', 'suffix',
        'birth_date', 'gender', 'phone_number',
        'civil_status', 'spouse_name',
        'barangay', 'purok', 'household_number',
        'usage_type', 'meter_brand', 'serial_number',
        'first_reading', 'registration_date', 'status'
    ])

    # Normalize maps so exported values are guaranteed to pass re-import validation
    GENDER_NORM = {'male': 'Male', 'female': 'Female', 'other': 'Other'}
    CIVIL_NORM  = {'single': 'Single', 'married': 'Married', 'widowed': 'Widowed', 'divorced': 'Divorced'}
    USAGE_NORM  = {'residential': 'Residential', 'commercial': 'Commercial'}
    SUFFIX_NORM = {'jr.': 'Jr.', 'sr.': 'Sr.', 'ii': 'II', 'iii': 'III', 'iv': 'IV', 'v': 'V'}
    STATUS_NORM = {'active': 'active', 'disconnected': 'disconnected'}

    for c in consumers_qs:
        raw_gender  = (c.gender or '').strip()
        raw_civil   = (c.civil_status or '').strip()
        raw_usage   = (c.usage_type or '').strip()
        raw_suffix  = (c.suffix or '').strip()
        raw_status  = (c.status or 'active').strip().lower()

        writer.writerow([
            c.first_name or '',
            c.middle_name or '',
            c.last_name or '',
            SUFFIX_NORM.get(raw_suffix.lower(), raw_suffix),
            c.birth_date.strftime('%Y-%m-%d') if c.birth_date else '',
            GENDER_NORM.get(raw_gender.lower(), raw_gender),
            c.phone_number or '',
            CIVIL_NORM.get(raw_civil.lower(), raw_civil),
            c.spouse_name or '',
            c.barangay.name if c.barangay else '',
            c.purok.name if c.purok else '',
            c.household_number or '',
            USAGE_NORM.get(raw_usage.lower(), raw_usage),
            c.meter_brand.name if c.meter_brand else '',
            c.serial_number or '',
            c.first_reading if c.first_reading is not None else '0',
            c.registration_date.strftime('%Y-%m-%d') if c.registration_date else '',
            STATUS_NORM.get(raw_status, 'active'),
        ])

    return response



@login_required
@consumer_edit_permission_required
def import_consumers_csv(request):
    """
    Bulk import consumers from an uploaded CSV file.
    Optimized for high performance on Render (avoids 502 timeouts).
    """
    import csv
    import io
    from datetime import datetime as _dt
    from django.db import transaction

    if request.method != 'POST':
        return redirect('consumers:consumer_management')

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.error(request, 'Please upload a CSV file.')
        return redirect('consumers:consumer_management')

    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'Only .csv files are accepted.')
        return redirect('consumers:consumer_management')

    try:
        raw = csv_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            csv_file.seek(0)
            raw = csv_file.read().decode('latin-1')
        except Exception:
            messages.error(request, 'Could not read the file. Please ensure it is saved as UTF-8 CSV.')
            return redirect('consumers:consumer_management')

    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        messages.error(request, 'The CSV file appears to be empty or has no headers.')
        return redirect('consumers:consumer_management')

    # Standardize column names
    col_map = {f.strip().lower(): f.strip() for f in reader.fieldnames}
    required_keys = [
        'first_name', 'last_name', 'birth_date', 'gender', 'phone_number',
        'civil_status', 'barangay', 'purok', 'household_number',
        'usage_type', 'meter_brand', 'serial_number', 'first_reading', 'registration_date'
    ]
    missing_cols = [k for k in required_keys if k not in col_map]
    if missing_cols:
        messages.error(request, f"Missing required columns: {', '.join(missing_cols)}. Please use the template.")
        return redirect('consumers:consumer_management')

    all_rows = list(reader)
    if not all_rows:
        messages.error(request, 'The CSV file appears to have no data rows.')
        return redirect('consumers:consumer_management')

    # --- Pre-fetching & Normalization ---
    def clean_val(val, default=''):
        """Clean 'N/A', 'n/a', 'None' strings from user input."""
        if not val: return default
        v = str(val).strip()
        if v.lower() in ('n/a', 'none', 'null', '-' , '.'):
            return default
        return v

    # 1. Pre-fetch existing serials and names for deduplication
    existing_serials = set(Consumer.objects.values_list('serial_number', flat=True))
    # Simple list of (first, last) tuples for memory check
    existing_names = set(Consumer.objects.values_list('first_name', 'last_name'))
    existing_names = {(fn.lower().strip(), ln.lower().strip()) for fn, ln in existing_names if fn and ln}

    # 2. Pre-fetch related objects
    barangays = {b.name.lower(): b for b in Barangay.objects.all()}
    meter_brands = {m.name.lower(): m for m in MeterBrand.objects.all()}
    # Puroks nested by barangay name
    puroks = {} # { 'barangay_name': { 'purok_name': obj } }
    for p in Purok.objects.select_related('barangay').all():
        b_name = p.barangay.name.lower()
        if b_name not in puroks: puroks[b_name] = {}
        puroks[b_name][p.name.lower()] = p

    VALID_GENDER       = {'male', 'female', 'other'}
    VALID_CIVIL_STATUS = {'single', 'married', 'widowed', 'divorced'}
    VALID_USAGE        = {'residential', 'commercial'}
    VALID_STATUS       = {'active', 'disconnected'}
    SUFFIX_MAP         = {'jr.': 'Jr.', 'sr.': 'Sr.', 'ii': 'II', 'iii': 'III', 'iv': 'IV', 'v': 'V', '': ''}

    # --- Pass 1: Validation in memory ---
    rows_data    = []
    hard_errors  = []
    skipped_rows = []
    seen_serials_in_file = set()

    for row_num, row in enumerate(all_rows, start=2):
        # Normalize row keys
        d = {k: clean_val(row.get(col_map[k])) for k in required_keys}
        d['middle_name'] = clean_val(row.get(col_map.get('middle_name', '')))
        d['suffix'] = clean_val(row.get(col_map.get('suffix', '')))
        d['status'] = clean_val(row.get(col_map.get('status', '')), 'active').lower()
        d['spouse_name'] = clean_val(row.get(col_map.get('spouse_name', '')))

        # Proper casing for names
        first_name  = ' '.join(w.capitalize() for w in d['first_name'].split())
        last_name   = ' '.join(w.capitalize() for w in d['last_name'].split())
        middle_name = ' '.join(w.capitalize() for w in d['middle_name'].split()) if d['middle_name'] else None
        
        # Missing fields check
        missing = [k for k in required_keys if not d[k]]
        if missing:
            hard_errors.append(f"Row {row_num}: Missing fields: {', '.join(missing)}")
            continue

        # Choice checks
        gender = d['gender'].capitalize()
        if gender.lower() not in VALID_GENDER:
            hard_errors.append(f"Row {row_num}: Invalid gender '{d['gender']}'")
            continue
        
        civil_status = d['civil_status'].capitalize()
        if civil_status.lower() not in VALID_CIVIL_STATUS:
            hard_errors.append(f"Row {row_num}: Invalid civil status '{d['civil_status']}'")
            continue

        usage_type = d['usage_type'].capitalize()
        if usage_type.lower() not in VALID_USAGE:
            hard_errors.append(f"Row {row_num}: Invalid usage type '{d['usage_type']}'")
            continue

        # Date parsing
        def parse_date(s):
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y'):
                try: return _dt.strptime(s, fmt).date()
                except: continue
            return None

        birth_date = parse_date(d['birth_date'])
        if not birth_date:
            hard_errors.append(f"Row {row_num}: Invalid birth_date '{d['birth_date']}'")
            continue
        
        reg_date = parse_date(d['registration_date'])
        if not reg_date:
            hard_errors.append(f"Row {row_num}: Invalid registration_date '{d['registration_date']}'")
            continue

        # Duplicate checks (In memory)
        sn = d['serial_number']
        if sn in existing_serials:
            skipped_rows.append(f"Row {row_num}: Serial '{sn}' already in DB — skipped.")
            continue
        if sn in seen_serials_in_file:
            skipped_rows.append(f"Row {row_num}: Serial '{sn}' duplicate in file — skipped.")
            continue
        seen_serials_in_file.add(sn)

        if (first_name.lower(), last_name.lower()) in existing_names:
            skipped_rows.append(f"Row {row_num}: '{first_name} {last_name}' already exists — skipped.")
            continue

        # Validated data
        rows_data.append({
            'first_name': first_name, 'middle_name': middle_name, 'last_name': last_name,
            'suffix': SUFFIX_MAP.get(d['suffix'].lower(), ''),
            'birth_date': birth_date, 'gender': gender, 'phone_number': d['phone_number'],
            'civil_status': civil_status, 'spouse_name': d['spouse_name'],
            'barangay': d['barangay'], 'purok': d['purok'], 'household_number': d['household_number'],
            'usage_type': usage_type, 'meter_brand': d['meter_brand'], 'serial_number': sn,
            'first_reading': int(float(d['first_reading'] or 0)),
            'registration_date': reg_date, 'status': d['status'] if d['status'] in VALID_STATUS else 'active'
        })

    if hard_errors:
        messages.error(request, f"❌ Import aborted! {len(hard_errors)} format errors found.")
        request.session['import_errors'] = hard_errors[:50]
        return redirect('consumers:consumer_management')

    if not rows_data:
        messages.warning(request, "⚠️ No new consumers to import. All rows were duplicates.")
        if skipped_rows: request.session['import_errors'] = skipped_rows[:50]
        return redirect('consumers:consumer_management')

    # --- Pass 2: High speed write ---
    current_session = UserLoginEvent.objects.filter(
        user=request.user, logout_timestamp__isnull=True, status='success'
    ).order_by('-login_timestamp').first()
    
    created_count = 0
    with transaction.atomic():
        # Optimization: Pre-calculate the starting ID number to avoid calling save()'s lock repeatedly
        # We handle this by using the Model's logic efficiently
        year_month = _dt.now().strftime('%Y%m')
        
        for data in rows_data:
            # 1. Get/Create related objects using memory cache
            bn_low = data['barangay'].lower()
            if bn_low not in barangays:
                barangays[bn_low] = Barangay.objects.create(name=data['barangay'].title())
            brgy_obj = barangays[bn_low]

            pk_low = data['purok'].lower()
            if bn_low not in puroks: puroks[bn_low] = {}
            if pk_low not in puroks[bn_low]:
                puroks[bn_low][pk_low] = Purok.objects.create(name=data['purok'].title(), barangay=brgy_obj)
            purok_obj = puroks[bn_low][pk_low]

            mb_low = data['meter_brand'].lower()
            if mb_low not in meter_brands:
                meter_brands[mb_low] = MeterBrand.objects.create(name=data['meter_brand'].title())
            brand_obj = meter_brands[mb_low]

            # 2. Create the consumer. 
            # Note: We let the model handle id_number inside the atomic block.
            # Since we optimized the model logic, this is now very fast.
            consumer = Consumer.objects.create(
                first_name=data['first_name'], middle_name=data['middle_name'],
                last_name=data['last_name'], suffix=data['suffix'],
                birth_date=data['birth_date'], gender=data['gender'],
                phone_number=data['phone_number'], civil_status=data['civil_status'],
                spouse_name=data['spouse_name'], barangay=brgy_obj, purok=purok_obj,
                household_number=data['household_number'], usage_type=data['usage_type'],
                meter_brand=brand_obj, serial_number=data['serial_number'],
                first_reading=data['first_reading'], registration_date=data['registration_date'],
                status=data['status']
            )
            
            # Simple activity creation (no heavy lookups)
            try:
                UserActivity.objects.create(
                    user=request.user, action='consumer_created',
                    description=f"[Import] {consumer.full_name} ({consumer.id_number})",
                    login_event=current_session, ip_address=request.META.get('REMOTE_ADDR')
                )
            except: pass
            created_count += 1

    request.session.pop('import_errors', None)
    messages.success(request, f"✅ Successfully imported {created_count} consumer(s).")
    if skipped_rows:
        messages.warning(request, f"⚠️ {len(skipped_rows)} duplicates were skipped.")
        request.session['import_errors'] = skipped_rows[:50]
    
    return redirect('consumers:consumer_management')


@login_required
@consumer_edit_permission_required
def add_consumer(request):


    """
    Handle adding a new consumer via full page form.
    RESTRICTED: Superuser only - Admins cannot create consumers.
    Includes duplicate detection to prevent accidental double-submission.
    """
    if request.method == "POST":
        form = ConsumerForm(request.POST)
        if form.is_valid():
            # ============================================================
            # DUPLICATE DETECTION - Prevent accidental double submission
            # ============================================================
            # Check if a consumer with same name, birth date, and barangay already exists
            # This catches duplicates from double-clicking the submit button
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            birth_date = form.cleaned_data.get('birth_date')
            barangay = form.cleaned_data.get('barangay')

            # Check for duplicate within the last 2 minutes (likely double-click)
            from datetime import timedelta
            from django.utils import timezone
            two_minutes_ago = timezone.now() - timedelta(minutes=2)

            duplicate = Consumer.objects.filter(
                first_name=first_name,
                last_name=last_name,
                birth_date=birth_date,
                barangay=barangay,
                created_at__gte=two_minutes_ago
            ).first()

            if duplicate:
                messages.warning(
                    request,
                    f"Consumer '{duplicate.first_name} {duplicate.last_name}' was already added (ID #: {duplicate.id_number}). "
                    "This may be a duplicate submission."
                )
                return redirect('consumers:consumer_management')

            # No duplicate found, proceed with creation
            consumer = form.save()

            # Track activity
            try:
                current_session = UserLoginEvent.objects.filter(
                    user=request.user,
                    logout_timestamp__isnull=True,
                    status='success'
                ).order_by('-login_timestamp').first()

                UserActivity.objects.create(
                    user=request.user,
                    action='consumer_created',
                    description=f"Created new consumer: {consumer.first_name} {consumer.last_name} ({consumer.id_number}) in {consumer.barangay.name}",
                    login_event=current_session
                )
            except Exception:
                pass  # Don't fail consumer creation if activity logging fails

            messages.success(request, f"Consumer added successfully! ID Number: {consumer.id_number}")
            return redirect('consumers:consumer_management')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ConsumerForm()

    return render(request, 'consumers/add_consumer.html', {'form': form})



@login_required
@consumer_edit_permission_required
def edit_consumer(request, consumer_id):
    """
    Edit consumer information.
    RESTRICTED: Superuser only - Admins cannot edit consumers.
    """
    consumer = get_object_or_404(Consumer, id=consumer_id)
    if request.method == 'POST':
        form = ConsumerForm(request.POST, instance=consumer)
        if form.is_valid():
            old_birth_date = consumer.birth_date
            form.save()

            # Recalculate senior citizen discount on pending bills if birth_date changed
            if form.cleaned_data.get('birth_date') != old_birth_date:
                from ..utils import update_bill_penalty
                pending_bills = consumer.bills.filter(status='Pending')
                for bill in pending_bills:
                    update_bill_penalty(bill, save=True)

            # Track activity
            try:
                current_session = UserLoginEvent.objects.filter(
                    user=request.user,
                    logout_timestamp__isnull=True,
                    status='success'
                ).order_by('-login_timestamp').first()

                UserActivity.objects.create(
                    user=request.user,
                    action='consumer_updated',
                    description=f"Updated consumer: {consumer.first_name} {consumer.last_name} ({consumer.id_number})",
                    login_event=current_session
                )
            except Exception:
                pass

            messages.success(request, "Consumer updated successfully!")
            return redirect('consumers:consumer_management')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ConsumerForm(instance=consumer)

    return render(request, 'consumers/edit_consumer.html', {'form': form, 'consumer': consumer})



class ConsumerListView(LoginRequiredMixin, ListView):
    """
    Class-based view for the consumer list, replacing the old consumer_list function.
    """
    model = Consumer
    template_name = 'consumers/consumer_list.html'
    context_object_name = 'consumers'
    paginate_by = 20
    
    def get_queryset(self):
        # Base queryset with optimized queries
        queryset = Consumer.objects.select_related('barangay', 'purok', 'meter_brand').order_by('-created_at')

        # Apply filters
        query = self.request.GET.get('q')
        barangay_filter = self.request.GET.get('barangay')
        status_filter = self.request.GET.get('status')

        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(id_number__icontains=query) |
                Q(phone_number__icontains=query)
            )

        if barangay_filter:
            queryset = queryset.filter(barangay_id=barangay_filter)

        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all barangays for filter dropdown
        context['barangays'] = Barangay.objects.all().order_by('name')
        
        # Calculate statistics
        context['total_consumers'] = Consumer.objects.count()
        context['connected_count'] = Consumer.objects.filter(status='active').count()
        context['disconnected_count'] = Consumer.objects.filter(status='disconnected').count()

        # Consumers registered this month
        now = datetime.now()
        context['this_month_count'] = Consumer.objects.filter(
            registration_date__month=now.month,
            registration_date__year=now.year
        ).count()
        
        return context

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['consumers/partials/consumer_table_only.html']
        return [self.template_name]


class ConsumerDetailView(LoginRequiredMixin, DetailView):
    model = Consumer
    template_name = 'consumers/consumer_detail.html'
    context_object_name = 'consumer'
    pk_url_kwarg = 'consumer_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['latest_bills'] = self.object.bills.filter(status='Pending').order_by('-billing_period')[:3]
        return context


@login_required
def load_puroks(request):
    barangay_id = request.GET.get('barangay_id')
    puroks = Purok.objects.filter(barangay_id=barangay_id).order_by('name')
    purok_list = [{'id': p.id, 'name': p.name} for p in puroks]
    return JsonResponse(purok_list, safe=False)



@login_required
def consumer_bill(request, consumer_id):
    """
    Display bills in a yearly ledger card format (Jan-Dec grid per year).
    Each month row shows billing, payment, and connection status.
    """
    from django.db.models import Sum, Prefetch
    from datetime import datetime, date
    from collections import OrderedDict

    consumer = get_object_or_404(Consumer, id=consumer_id)
    all_bills = consumer.bills.select_related(
        'current_reading__consumer',
        'previous_reading__consumer'
    ).prefetch_related(
        Prefetch('payments', queryset=Payment.objects.select_related('processed_by').order_by('-payment_date'))
    ).order_by('billing_period')

    # Get available years for filter
    current_year = timezone.now().year
    bill_years = list(all_bills.dates('billing_period', 'year', order='DESC'))
    existing_years = [d.year for d in bill_years]
    
    # Define range for dropdown: earliest bill or past year, up to next year
    min_year = min(existing_years) if existing_years else current_year
    min_year = min(min_year, current_year - 1)
    max_year = current_year + 1
    
    available_years = list(range(max_year, min_year - 1, -1))

    # Apply year filter - default to latest year if available
    selected_year = request.GET.get('year', '')
    if selected_year:
        filtered_bills = all_bills.filter(billing_period__year=int(selected_year))
    else:
        filtered_bills = all_bills

    # Get service history events for this consumer
    consumer_name = f"{consumer.first_name} {consumer.last_name}"
    from django.db.models import Q
    
    # We must match either the id_number explicitly in parentheses, or their exact name
    # We use Q objects to ensure both conditions are searched independently
    query = Q(action__in=['consumer_disconnected', 'consumer_reconnected'])
    
    if consumer.id_number:
        query &= (Q(description__icontains=consumer.id_number) | Q(description__icontains=consumer_name))
    else:
        query &= Q(description__icontains=consumer_name)
        
    service_events = UserActivity.objects.filter(query).order_by('created_at')

    # Build a timeline of connection status changes
    # Each event marks a status change at a point in time
    status_changes = []
    for event in service_events:
        status_changes.append({
            'date': event.created_at.date(),
            'status': 'disconnected' if event.action == 'consumer_disconnected' else 'active',
            'user': event.user,
            'description': event.description,
            'created_at': event.created_at,
        })

    def get_month_status(year, month):
        """Determine connection status and the latest event details for a given month."""
        check_date = date(year, month, 1)
        current_status = 'active'
        current_event = None
        for change in status_changes:
            if change['date'] <= check_date:
                current_status = change['status']
                current_event = change
            else:
                break
        return current_status, current_event

    # Build ledger data: group bills by year, create 12-month grid
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    # Index bills by (year, month) for quick lookup
    bill_map = {}
    for bill in filtered_bills:
        key = (bill.billing_period.year, bill.billing_period.month)
        bill_map[key] = bill

    # Determine which years to show. Always ensure at least the current year shows for empty states.
    if selected_year:
        years_to_show = [int(selected_year)]
    elif existing_years:
        years_to_show = sorted(existing_years, reverse=True)
    else:
        years_to_show = [current_year]

    # Build ledger cards
    ledger_cards = []
    for year in years_to_show:
        months = []
        for month_num in range(1, 13):
            bill = bill_map.get((year, month_num))
            payment = None
            if bill:
                payments = list(bill.payments.all())
                payment = payments[0] if payments else None

            connection_status, conn_event = get_month_status(year, month_num)

            reading_value = None
            reading_details = None
            if bill and bill.current_reading:
                r = bill.current_reading
                reading_value = r.reading_value
                reading_details = {
                    'reading_value': r.reading_value,
                    'reading_date': r.reading_date,
                    'source': r.get_source_display(),
                    'submitted_by': r.submitted_by,
                    'is_confirmed': r.is_confirmed,
                    'confirmed_by': r.confirmed_by,
                    'confirmed_at': r.confirmed_at,
                }

            conn_details = None
            if conn_event:
                evt_user = conn_event['user']
                conn_details = {
                    'date': conn_event['created_at'],
                    'by': f"{evt_user.first_name} {evt_user.last_name}" if evt_user else 'System',
                    'description': conn_event['description'],
                    'type': 'disconnected' if conn_event['status'] == 'disconnected' else 'reconnected'
                }

            months.append({
                'month_name': month_names[month_num - 1],
                'month_num': month_num,
                'bill': bill,
                'reading_value': reading_value,
                'reading_details': reading_details,
                'consumption': bill.consumption if bill else None,
                'amount_due': bill.total_amount if bill else None,
                'penalty': bill.effective_penalty if bill else None,
                'amount_paid': payment.amount_paid if payment else None,
                'receipt_number': payment.or_number if payment else None,
                'date_issued': payment.payment_date if payment else None,
                'processed_by': payment.processed_by if payment else None,
                'status': bill.status if bill else None,
                'connection_status': connection_status,
                'conn_details': conn_details,
            })

        ledger_cards.append({
            'year': year,
            'months': months,
        })

    # Calculate summary statistics
    total_bills = filtered_bills.count()
    total_billed = filtered_bills.aggregate(total=Sum('total_amount'))['total'] or 0
    outstanding_balance = filtered_bills.filter(
        status__in=['Pending', 'Overdue']
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    return render(request, 'consumers/consumer_bill.html', {
        'consumer': consumer,
        'ledger_cards': ledger_cards,
        'total_bills': total_bills,
        'total_billed': total_billed,
        'outstanding_balance': outstanding_balance,
        'today': datetime.now(),
        'available_years': available_years,
        'selected_year': selected_year,
        'service_events': service_events,
    })
