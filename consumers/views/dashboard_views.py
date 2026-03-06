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
    from .utils import calculate_tiered_water_bill

    # Use tiered calculation from utils
    total_amount, average_rate, breakdown = calculate_tiered_water_bill(
        consumption=consumption,
        usage_type=consumer.usage_type
    )

    return float(average_rate), float(total_amount), breakdown



@login_required
def home(request):
    """Staff dashboard - unified landing page for all roles with role-based metric widgets."""
    from .models import Notification



    # Auto-cleanup: Delete notifications older than 1 month
    one_month_ago = datetime.now() - timedelta(days=30)
    Notification.objects.filter(created_at__lt=one_month_ago).delete()

    current_month = datetime.now().month
    current_year = datetime.now().year
    today = datetime.now().date()

    # Get counts
    connected_count = Consumer.objects.filter(status='active').count()
    disconnected_count = Consumer.objects.filter(status='disconnected').count()

    # Delinquent count (consumers with pending bills older than today)
    delinquent_count = Consumer.objects.filter(
        bills__status='Pending',
        bills__billing_period__lt=datetime.now().date()
    ).distinct().count()

    # ==========================================
    # REVENUE CALCULATIONS
    # ==========================================
    # Today's Revenue
    today_revenue = Payment.objects.filter(
        payment_date=today
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    # This Month's Revenue
    monthly_revenue = Payment.objects.filter(
        payment_date__month=current_month,
        payment_date__year=current_year
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    # Annual Revenue (Current Year)
    annual_revenue = Payment.objects.filter(
        payment_date__year=current_year
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    # Total Revenue (All Time)
    total_revenue = Payment.objects.aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0.00')

    # Today's payment count
    today_payment_count = Payment.objects.filter(payment_date=today).count()

    # Handle report filter - support both month_year and separate month/year
    month_year = request.GET.get('month_year')
    if month_year:
        try:
            selected_year, selected_month = month_year.split('-')
            selected_year = int(selected_year)
            selected_month = int(selected_month)
        except:
            selected_month = current_month
            selected_year = current_year
    else:
        selected_month = int(request.GET.get('month', current_month))
        selected_year = int(request.GET.get('year', current_year))

    # Get delinquent bills for the selected month/year
    delinquent_bills = Bill.objects.filter(
        status='Pending',
        billing_period__month=selected_month,
        billing_period__year=selected_year
    ).select_related('consumer', 'consumer__barangay').order_by('-billing_period')

    # Calculate total delinquent amount
    total_delinquent_amount = delinquent_bills.aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')

    # Chart Data: Monthly Revenue Trend (Last 6 months)
    end_date = datetime.now().date()
    start_date = end_date - relativedelta(months=5)

    monthly_payments = Payment.objects.filter(
        payment_date__gte=start_date,
        payment_date__lte=end_date
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month').annotate(
        total=Sum('amount_paid')
    ).order_by('month')

    revenue_labels = []
    revenue_data = []
    revenue_list = []  # For template iteration
    for item in monthly_payments:
        label = item['month'].strftime('%b %Y')
        amount = float(item['total'] or 0)
        revenue_labels.append(label)
        revenue_data.append(amount)
        revenue_list.append((label, amount))

    # Chart Data: Payment Status Distribution
    total_bills = Bill.objects.filter(status__in=['Pending', 'Unpaid', 'Overdue']).count()  # Outstanding bills only
    paid_bills = Bill.objects.filter(status='Paid').count()
    pending_bills = Bill.objects.filter(status='Pending').count()

    # Get all barangays for filter dropdown
    all_barangays = Barangay.objects.all().order_by('name')

    # Consumer Bill Status Data - Get latest bill for each consumer
    latest_bill_subquery = Bill.objects.filter(
        consumer=OuterRef('pk')
    ).order_by('-billing_period').values('id')[:1]

    consumers_with_bills = Consumer.objects.all().annotate(
        latest_bill_id=Subquery(latest_bill_subquery)
    ).select_related('barangay').order_by('barangay__name', 'last_name', 'first_name')

    consumer_bill_status = []
    for consumer in consumers_with_bills:
        if consumer.latest_bill_id:
            try:
                latest_bill = Bill.objects.get(id=consumer.latest_bill_id)
                consumer_bill_status.append({
                    'id_number': consumer.id_number,
                    'consumer_name': consumer.full_name,
                    'barangay': consumer.barangay.name if consumer.barangay else 'N/A',
                    'barangay_id': consumer.barangay.id if consumer.barangay else None,
                    'latest_bill_date': latest_bill.billing_period,
                    'latest_bill_amount': float(latest_bill.total_amount),
                    'payment_status': latest_bill.status,
                })
            except Bill.DoesNotExist:
                pass
        else:
            consumer_bill_status.append({
                'id_number': consumer.id_number,
                'consumer_name': consumer.full_name,
                'barangay': consumer.barangay.name if consumer.barangay else 'N/A',
                'barangay_id': consumer.barangay.id if consumer.barangay else None,
                'latest_bill_date': None,
                'latest_bill_amount': 0,
                'payment_status': 'No Bill',
            })

    # Chart Data: Barangay Consumer Distribution
    barangay_data = Consumer.objects.values('barangay__name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    barangay_labels = [item['barangay__name'] or 'Unassigned' for item in barangay_data]
    barangay_counts = [item['count'] for item in barangay_data]

    # Chart Data: Monthly Consumption Trend
    monthly_consumption = Bill.objects.filter(
        billing_period__gte=start_date
    ).annotate(
        month=TruncMonth('billing_period')
    ).values('month').annotate(
        total_consumption=Sum('consumption')
    ).order_by('month')

    consumption_labels = []
    consumption_data = []
    for item in monthly_consumption:
        consumption_labels.append(item['month'].strftime('%b %Y'))
        consumption_data.append(float(item['total_consumption'] or 0))

    # Create a date object for proper month/year formatting in template
    selected_date = date(selected_year, selected_month, 1)

    context = {
        'connected_count': connected_count,
        'disconnected_count': disconnected_count,
        'delinquent_count': delinquent_count,
        'delinquent_bills': delinquent_bills,
        'total_delinquent_amount': total_delinquent_amount,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'selected_date': selected_date,
        'current_date': datetime.now(),
        # Revenue data
        'today_revenue': today_revenue,
        'monthly_revenue': monthly_revenue,
        'annual_revenue': annual_revenue,
        'total_revenue': total_revenue,
        'today_payment_count': today_payment_count,
        # Chart data
        'revenue_labels': json.dumps(revenue_labels),
        'revenue_data': json.dumps(revenue_data),
        'revenue_list': revenue_list,
        'paid_bills': paid_bills,
        'pending_bills': pending_bills,
        'barangay_labels': json.dumps(barangay_labels),
        'barangay_counts': json.dumps(barangay_counts),
        'consumption_labels': json.dumps(consumption_labels),
        'consumption_data': json.dumps(consumption_data),
        'total_bills': total_bills,
        'all_barangays': all_barangays,
        'consumer_bill_status': json.dumps(consumer_bill_status, default=str),
    }
    return render(request, 'consumers/home.html', context)
