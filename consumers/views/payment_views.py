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


# ============================================================================
# INQUIRE / PAYMENT VIEW - BILL INQUIRY AND PAYMENT PROCESSING
# ============================================================================
# This is the FINAL step in the billing flow where payments are processed.
#
# COMPLETE FLOW (for testing):
# 1. Mobile app submits reading → MeterReading (is_confirmed=False)
# 2. Admin confirms reading → Bill created (status='Pending')
# 3. Admin comes HERE → Selects consumer → Sees pending bill
# 4. Admin enters received amount → Payment processed → Bill status='Paid'
# 5. Receipt generated with OR number
#
# HOW TO TEST:
# 1. Submit reading from app (or create manually)
# 2. Go to Meter Readings → Barangay → Click "Confirm"
# 3. Come to this Inquire page → Select barangay → Select consumer
# 4. You'll see the pending bill → Enter payment amount → Submit
# ============================================================================
@login_required
def inquire(request):
    """
    Water Bill Inquiry page.

    Displays consumers with pending bills and shows a water bill for the selected consumer.
    Users can uncheck newer months to issue a partial bill (oldest months first).
    """
    from ..utils import calculate_penalty, update_bill_penalty, get_payment_breakdown

    # Get system settings for penalty calculation
    system_settings = SystemSetting.objects.first()

    # ===== GET REQUEST - Show only consumers with pending bills =====
    selected_consumer_id = request.GET.get('consumer')
    selected_barangay = request.GET.get('barangay', '')

    # Load all active consumers
    consumers = Consumer.objects.filter(status='active').select_related('barangay', 'purok').order_by('last_name', 'first_name')

    # Apply barangay filter
    if selected_barangay:
        consumers = consumers.filter(barangay_id=selected_barangay)

    # Build consumer bills dictionary - only pending bills
    consumer_bills = {}
    for c in consumers:
        bill = c.bills.filter(status='Pending').order_by('-billing_period').first()
        if bill:
            update_bill_penalty(bill, system_settings, save=True)
            consumer_bills[c.id] = bill

    # Show only consumers with pending bills
    consumers = [c for c in consumers if c.id in consumer_bills]

    # Load barangays for filter dropdown
    barangays = Barangay.objects.all().order_by('name')

    selected_consumer = None
    latest_bill = None
    payment_breakdown = None

    if selected_consumer_id:
        selected_consumer = get_object_or_404(Consumer, id=selected_consumer_id)
        latest_bill = selected_consumer.bills.filter(status='Pending').order_by('-billing_period').first()

        if latest_bill:
            payment_breakdown = get_payment_breakdown(latest_bill, system_settings)

        # Get all pending bills for ledger-style water bill display
        pending_bills = selected_consumer.bills.filter(status='Pending').order_by('billing_period')
        for bill in pending_bills:
            update_bill_penalty(bill, system_settings, save=True)

    # Count total pending bills
    total_pending_bills = Bill.objects.filter(status='Pending').count()

    # Check if user can waive penalties
    can_waive_penalty = request.user.is_superuser or (
        hasattr(request.user, 'staffprofile') and request.user.staffprofile.role == 'admin'
    )

    context = {
        'consumers': consumers,
        'consumer_bills': consumer_bills,
        'selected_consumer': selected_consumer,
        'latest_bill': latest_bill,
        'pending_bills': pending_bills if selected_consumer_id else [],
        'payment_breakdown': payment_breakdown,
        'total_pending_bills': total_pending_bills,
        'system_settings': system_settings,
        'can_waive_penalty': can_waive_penalty,
        'barangays': barangays,
        'selected_barangay': selected_barangay,
    }
    return render(request, 'consumers/inquire.html', context)



@login_required
def process_payment(request):
    """
    Cashier payment processing page.
    GET  (no consumer): consumer selection list
    GET  (?consumer=X): show pending bills + cash/change form
    POST (?consumer=X): create Payment, mark bill Paid, redirect to receipt
    """
    from ..utils import update_bill_penalty, get_payment_breakdown
    from ..models import Notification

    system_settings = SystemSetting.objects.first()

    selected_consumer_id = request.GET.get('consumer')
    selected_barangay = request.GET.get('barangay', '')
    barangays = Barangay.objects.all().order_by('name')

    # ---------- POST: process the payment ----------
    if request.method == 'POST':
        selected_consumer_id = request.POST.get('consumer_id')
        bill_ids_raw = request.POST.get('bill_ids', '')
        received_amount_raw = request.POST.get('received_amount', '0')
        remarks = request.POST.get('remarks', '').strip()

        try:
            received_amount = Decimal(received_amount_raw)
        except Exception:
            messages.error(request, "Invalid cash amount entered.")
            return redirect(f"{request.path}?consumer={selected_consumer_id}")

        consumer = get_object_or_404(Consumer, id=selected_consumer_id)

        # Resolve selected bill IDs
        if bill_ids_raw:
            bill_id_list = [int(b) for b in bill_ids_raw.split(',') if b.strip()]
            bills = consumer.bills.filter(id__in=bill_id_list, status='Pending').order_by('billing_period')
        else:
            bills = consumer.bills.filter(status='Pending').order_by('billing_period')

        if not bills.exists():
            messages.error(request, "No pending bills found for this consumer.")
            return redirect(f"{request.path}?consumer={selected_consumer_id}")

        # Calculate total amount due across selected bills
        total_due = Decimal('0.00')
        for bill in bills:
            update_bill_penalty(bill, system_settings, save=True)
            total_due += bill.total_amount_due

        if received_amount < total_due:
            messages.error(request, f"Cash received (₱{received_amount:.2f}) is less than the amount due (₱{total_due:.2f}).")
            return redirect(f"{request.path}?consumer={selected_consumer_id}")

        # Create one payment per bill (split received proportionally if multiple bills)
        last_payment = None
        for i, bill in enumerate(bills):
            update_bill_penalty(bill, system_settings, save=True)
            bill_total = bill.total_amount_due

            if i == len(list(bills)) - 1:
                # Last bill gets the remainder of received amount
                bill_received = received_amount - sum(
                    b.total_amount_due for j, b in enumerate(bills) if j < i
                )
            else:
                bill_received = bill_total

            payment = Payment(
                bill=bill,
                original_bill_amount=bill.total_amount,
                penalty_amount=bill.effective_penalty,
                penalty_waived=bill.penalty_waived,
                days_overdue_at_payment=bill.days_overdue,
                senior_citizen_discount=bill.senior_citizen_discount,
                amount_paid=bill_total,
                received_amount=bill_received if i == len(list(bills)) - 1 else bill_total,
                processed_by=request.user,
                remarks=remarks,
            )
            payment.save()

            # Mark bill as paid
            bill.status = 'Paid'
            bill.queued_for_payment = False
            bill.save()

            last_payment = payment

        # --- Log the payment activity ---
        if last_payment:
            try:
                current_session = UserLoginEvent.objects.filter(
                    user=request.user,
                    session_key=request.session.session_key,
                    logout_timestamp__isnull=True
                ).first()
                UserActivity.objects.create(
                    user=request.user,
                    action='payment_processed',
                    description=f'Processed payment for consumer {consumer.full_name} ({consumer.id_number}) – OR#{last_payment.or_number}',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    login_event=current_session
                )
            except Exception:
                pass  # Never block payment for logging failures

        # Create notification for superadmin
        Notification.objects.create(
            notification_type='payment',
            title='Payment Processed',
            message=f"Payment of ₱{total_due:.2f} received from {consumer.full_name} (ID: {consumer.id_number}) — processed by {request.user.get_full_name() or request.user.username}.",
            redirect_url=f"/payment/receipt/{last_payment.id}/",
        )

        messages.success(request, f"Payment of ₱{total_due:.2f} processed successfully. OR#: {last_payment.or_number}")
        return redirect('consumers:payment_receipt', payment_id=last_payment.id)

    # ---------- GET: show consumer list or bill+payment form ----------
    # Only show consumers who have been through the Inquire office
    # (i.e., have at least one bill marked queued_for_payment=True)
    queued_consumer_ids = set(
        Bill.objects.filter(
            status='Pending',
            queued_for_payment=True
        ).values_list('consumer_id', flat=True)
    )

    consumers = Consumer.objects.filter(
        status='active',
        id__in=queued_consumer_ids
    ).select_related('barangay', 'purok').order_by('last_name', 'first_name')

    if selected_barangay:
        consumers = consumers.filter(barangay_id=selected_barangay)

    # Build consumer → pending bill map (only queued bills)
    consumer_bills = {}
    for c in consumers:
        bill = c.bills.filter(status='Pending', queued_for_payment=True).order_by('-billing_period').first()
        if bill:
            update_bill_penalty(bill, system_settings, save=True)
            consumer_bills[c.id] = bill

    consumers = [c for c in consumers if c.id in consumer_bills]

    selected_consumer = None
    pending_bills = []
    total_due = Decimal('0.00')
    locked_bill_ids = ''

    if selected_consumer_id:
        selected_consumer = get_object_or_404(Consumer, id=selected_consumer_id)
        pending_bills = list(selected_consumer.bills.filter(status='Pending').order_by('billing_period'))
        
        # Read queued bills from database
        queued_bills = selected_consumer.bills.filter(status='Pending', queued_for_payment=True)
        locked_id_list = list(queued_bills.values_list('id', flat=True))
        if locked_id_list:
            locked_bill_ids = ','.join(map(str, locked_id_list))

        for bill in pending_bills:
            update_bill_penalty(bill, system_settings, save=True)
            # If locked bills are specified, only sum those for the initial total_due
            if not locked_id_list or bill.id in locked_id_list:
                total_due += bill.total_amount_due

    context = {
        'consumers': consumers,
        'consumer_bills': consumer_bills,
        'selected_consumer': selected_consumer,
        'pending_bills': pending_bills,
        'total_due': total_due,
        'barangays': barangays,
        'selected_barangay': selected_barangay,
        'locked_bill_ids': locked_bill_ids,
    }
    return render(request, 'consumers/process_payment.html', context)



@login_required
def water_bill_print(request, consumer_id):
    """
    Display a printable water bill for a consumer matching the official paper form.
    Shows all pending bills or a subset if ?bills=id1,id2 is passed (partial bill).
    """
    from ..utils import update_bill_penalty

    system_settings = SystemSetting.objects.first()
    consumer = get_object_or_404(Consumer.objects.select_related('barangay', 'purok'), id=consumer_id)

    # Support partial bill: ?bills=id1,id2,id3
    bills_param = request.GET.get('bills', '')
    if bills_param:
        bill_id_list = [int(bid.strip()) for bid in bills_param.split(',') if bid.strip()]
        pending_bills = consumer.bills.filter(id__in=bill_id_list, status='Pending').order_by('billing_period')
        
        # Mark selected bills as queued for payment in Cashier view, unmark others
        consumer.bills.filter(status='Pending').update(queued_for_payment=False)
        pending_bills.update(queued_for_payment=True)
    else:
        pending_bills = consumer.bills.filter(status='Pending').order_by('billing_period')
        # Mark all pending as queued for payment
        pending_bills.update(queued_for_payment=True)

    for bill in pending_bills:
        update_bill_penalty(bill, system_settings, save=True)

    # --- Log the inquire/print activity ---
    try:
        current_session = UserLoginEvent.objects.filter(
            user=request.user,
            session_key=request.session.session_key,
            logout_timestamp__isnull=True
        ).first()
        UserActivity.objects.create(
            user=request.user,
            action='bill_generated',
            description=f'Inquired/printed bill for consumer {consumer.full_name} ({consumer.id_number}) – {pending_bills.count()} month(s)',
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            login_event=current_session
        )
    except Exception:
        pass  # Never block print for logging failures

    total_amount = sum(bill.total_amount for bill in pending_bills)
    total_penalty = sum(bill.effective_penalty for bill in pending_bills)
    grand_total = sum(bill.total_amount_due for bill in pending_bills)

    return render(request, 'consumers/receipt.html', {
        'consumer': consumer,
        'pending_bills': pending_bills,
        'total_amount': total_amount,
        'total_penalty': total_penalty,
        'grand_total': grand_total,
        'issued_by': request.user,
    })



@login_required
def payment_receipt(request, payment_id):
    """
    Display a printable official receipt for a payment.
    Ensures the payment exists and belongs to a valid bill/consumer.
    Includes tiered rate breakdown for transparent billing.
    """
    from ..utils import calculate_tiered_water_bill

    payment = get_object_or_404(
        Payment.objects.select_related('bill__consumer', 'bill__previous_reading', 'bill__current_reading'),
        id=payment_id
    )

    # Calculate previous reading value: use stored value or compute from current - consumption
    if payment.bill.previous_reading:
        previous_reading_value = payment.bill.previous_reading.reading_value
    else:
        previous_reading_value = payment.bill.current_reading.reading_value - payment.bill.consumption

    # Calculate tiered breakdown for receipt display
    _, _, breakdown = calculate_tiered_water_bill(
        consumption=payment.bill.consumption,
        usage_type=payment.bill.consumer.usage_type
    )

    return render(request, 'consumers/official_receipt.html', {
        'payment': payment,
        'previous_reading_value': previous_reading_value,
        'breakdown': breakdown
    })



@login_required
@role_required('cashier', 'admin', 'superadmin') # Give access to admin/superadmin as well as cashier
def payment_history(request):
    """
    Payment History view showing all payments with penalty tracking.
    Allows filtering by date range, consumer, and penalty status.
    Optimized to handle 30,000+ consumers efficiently.
    """
    from django.core.paginator import Paginator
    from django.db.models import Sum, Q, Count
    
    # Load barangays for the filter dropdown
    barangays = Barangay.objects.all().order_by('name')

    # Get filter parameters
    search_query = request.GET.get('search', '').strip()
    penalty_filter = request.GET.get('penalty', '')  # 'with_penalty', 'waived', 'no_penalty'
    barangay_filter = request.GET.get('barangay', '') # New barangay filter
    
    # Default date range: 1 month (today back to 1 month ago)
    today = timezone.now().date()
    default_to = today.strftime('%Y-%m-%d')
    # Go back 1 month, handling month boundaries
    if today.month == 1:
        default_from = today.replace(year=today.year - 1, month=12).strftime('%Y-%m-%d')
    else:
        try:
            default_from = today.replace(month=today.month - 1).strftime('%Y-%m-%d')
        except ValueError:
            # Handle cases like March 31 -> Feb 28
            import calendar
            last_day = calendar.monthrange(today.year, today.month - 1)[1]
            default_from = today.replace(month=today.month - 1, day=last_day).strftime('%Y-%m-%d')

    date_from = request.GET.get('date_from', default_from)
    date_to = request.GET.get('date_to', default_to)

    # Base query with related data
    payments = Payment.objects.select_related(
        'bill__consumer__barangay',
        'processed_by'
    ).order_by('-payment_date')

    # Apply filters
    if search_query:
        payments = payments.filter(
            Q(bill__consumer__first_name__icontains=search_query) |
            Q(bill__consumer__last_name__icontains=search_query) |
            Q(bill__consumer__id_number__icontains=search_query) |
            Q(or_number__icontains=search_query)
        )
        
    if barangay_filter:
        payments = payments.filter(bill__consumer__barangay_id=barangay_filter)

    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)

    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)

    if penalty_filter == 'with_penalty':
        payments = payments.filter(penalty_amount__gt=0, penalty_waived=False)
    elif penalty_filter == 'waived':
        payments = payments.filter(penalty_waived=True)
    elif penalty_filter == 'no_penalty':
        payments = payments.filter(penalty_amount=0)

    # Calculate ALL statistics in a SINGLE optimized database query
    stats = payments.aggregate(
        total_collected=Sum('amount_paid'),
        total_penalties=Sum('penalty_amount'),
        total_bills=Sum('original_bill_amount'),
        # Use conditional aggregation to count penalty statuses in the same query
        count_with_penalty=Count('id', filter=Q(penalty_amount__gt=0, penalty_waived=False)),
        count_waived=Count('id', filter=Q(penalty_waived=True)),
        count_no_penalty=Count('id', filter=Q(penalty_amount=0)),
        total_records=Count('id')
    )

    penalty_counts = {
        'with_penalty': stats['count_with_penalty'] or 0,
        'waived': stats['count_waived'] or 0,
        'no_penalty': stats['count_no_penalty'] or 0,
    }

    # Pagination
    paginator = Paginator(payments, 25)  # 25 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'payments': page_obj,
        'search_query': search_query,
        'barangays': barangays,          # Pass down to template
        'barangay_filter': barangay_filter, # Pass down to template
        'date_from': date_from,
        'date_to': date_to,
        'penalty_filter': penalty_filter,
        'total_stats': stats,
        'penalty_counts': penalty_counts,
        'total_count': stats['total_records'] or 0,
    }

    return render(request, 'consumers/payment_history.html', context)
