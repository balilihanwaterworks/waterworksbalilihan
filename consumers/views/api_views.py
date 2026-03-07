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
# API VIEW: MOBILE APP METER READING SUBMISSION
# ============================================================================
# FLOW OVERVIEW:
# 1. Mobile app (field staff) submits meter reading anytime
# 2. Reading is saved with is_confirmed=TRUE (auto-confirmed)
# 3. Bill is automatically generated with status='Pending'
# 4. Bill appears in Inquire/Payment page for payment processing
#
# NOTE: Manual confirmation has been removed as it was redundant.
# Bills are now generated immediately upon meter reading submission.
# ============================================================================
@csrf_exempt  # Be careful with CSRF in production, consider using proper tokens for mobile apps
def api_submit_reading(request):
    """
    API endpoint for Android app to submit meter readings.

    IMPORTANT: Readings are AUTO-CONFIRMED and bills are generated immediately.

    FLOW:
    1. App submits reading → MeterReading created (is_confirmed=True)
    2. Bill is automatically generated with status='Pending'
    3. Admin processes payment → Bill status='Paid'

    Returns bill details:
    - status, message
    - consumer_name, id_number, reading_date
    - previous_reading, current_reading, consumption
    - rate, total_amount, field_staff_name
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        # Authenticate using token if not already authenticated
        api_user = None
        if not request.user.is_authenticated:
            api_user = authenticate_api_request(request)

        # Parse JSON data from the request body
        data = json.loads(request.body.decode('utf-8'))

        # Extract data from the request - MATCHING ANDROID APP FORMAT
        consumer_id = data.get('consumer_id') # Expecting consumer ID from app
        reading_value = data.get('reading')   # Expecting 'reading' key from app
        # Optional: Check if reading_date is sent, otherwise default to today
        reading_date_str = data.get('reading_date') # Expecting 'reading_date' key from app, can be None initially

        # Validate required fields (assuming reading_date is sent by the app now, or use today's date)
        if consumer_id is None or reading_value is None:
            return JsonResponse({'error': 'Missing required fields: consumer_id or reading'}, status=400)

        # Get the consumer based on ID (as sent by the app)
        try:
            consumer = Consumer.objects.get(id=consumer_id) # Use id instead of account_number
        except Consumer.DoesNotExist:
            return JsonResponse({'error': 'Consumer not found'}, status=404)

        # Check if consumer is disconnected - reject meter reading submission
        if consumer.status == 'disconnected':
            return JsonResponse({
                'error': 'Consumer is disconnected',
                'message': f'{consumer.first_name} {consumer.last_name} is currently disconnected. Meter reading not allowed.',
                'consumer_status': 'disconnected'
            }, status=403)

        # Determine the reading date
        if reading_date_str:
            # Parse the date string if provided by the app
            try:
                reading_date = timezone.datetime.strptime(reading_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        else:
            # Use the current date if no date is provided by the app
            reading_date = timezone.now().date()

        # Validate reading value (should be a positive number, handle potential float from app)
        try:
            # Convert to int, assuming the app sends an integer or a float that represents an integer
            # If the app sends a float representing a non-integer reading, this might need adjustment
            current_reading = int(reading_value) # Convert float to int
            if current_reading < 0:
                raise ValueError("Reading value cannot be negative")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid reading value. Must be a non-negative number.'}, status=400)

        # Get previous reading
        previous_reading = get_previous_reading(consumer)

        # Calculate consumption
        consumption = current_reading - previous_reading

        # Validate consumption (current should be >= previous)
        if consumption < 0:
            return JsonResponse({
                'error': 'Invalid reading',
                'message': f'Current reading ({current_reading}) cannot be less than previous reading ({previous_reading})'
            }, status=400)

        # Calculate bill using tiered rates
        rate, total_amount, breakdown = calculate_water_bill(consumer, consumption)

        # Determine the authenticated user (from session or token)
        current_user = request.user if request.user.is_authenticated else api_user

        # Get field staff name
        field_staff_name = "System"  # Default
        if current_user:
            field_staff_name = current_user.get_full_name() or current_user.username

        # --- NEW LOGIC: Check for existing unconfirmed reading on the same date ---
        try:
            existing_reading = MeterReading.objects.get(
                consumer=consumer,
                reading_date=reading_date
            )
            # If an existing reading is found for the same date
            if existing_reading.is_confirmed:
                # If it's already confirmed, don't allow updates
                error_msg = f"Reading for {consumer.id_number} on {reading_date} is already confirmed and cannot be updated via API."
                return JsonResponse({'error': error_msg}, status=400)
            else:
                # If it's unconfirmed, update the existing record
                existing_reading.reading_value = current_reading
                existing_reading.source = 'app_scanned' # OCR scan from Smart Meter Reader app
                existing_reading.save()

        except MeterReading.DoesNotExist:
            # If no existing reading for the date, create a new one
            # AUTO-CONFIRM: Reading is confirmed immediately and bill is generated
            reading = MeterReading.objects.create(
                consumer=consumer,
                reading_date=reading_date,
                reading_value=current_reading,
                source='app_scanned',  # OCR scan from Smart Meter Reader app
                is_confirmed=True  # Auto-confirm - no manual confirmation needed
            )

            # ================================================================
            # AUTO-GENERATE BILL
            # ================================================================
            # Get previous confirmed reading for bill reference
            prev_reading_obj = MeterReading.objects.filter(
                consumer=consumer,
                is_confirmed=True,
                reading_date__lt=reading_date
            ).order_by('-reading_date').first()

            # Get system settings for billing schedule
            setting = SystemSetting.objects.first()
            if setting:
                billing_day = setting.billing_day_of_month
                due_day = setting.due_day_of_month
            else:
                billing_day = 1
                due_day = 20

            # Compute senior citizen water bill discount
            # 5% of total bill if consumer is SC AND consumption <= 30 m³
            sc_discount = Decimal('0.00')
            if consumer.is_senior_citizen and consumption <= 30:
                sc_discount = (Decimal(str(total_amount)) * Decimal('5') / Decimal('100')).quantize(Decimal('0.01'))

            # Create Bill automatically with ACTUAL tier breakdown (not averages)
            Bill.objects.create(
                consumer=consumer,
                previous_reading=prev_reading_obj,
                current_reading=reading,
                billing_period=reading_date.replace(day=billing_day),
                due_date=reading_date.replace(day=due_day),
                consumption=consumption,
                # Store ACTUAL tier breakdown
                tier1_consumption=breakdown['tier1_units'],
                tier1_amount=breakdown['tier1_amount'],
                tier2_consumption=breakdown['tier2_units'],
                tier2_rate=breakdown['tier2_rate'],
                tier2_amount=breakdown['tier2_amount'],
                tier3_consumption=breakdown['tier3_units'],
                tier3_rate=breakdown['tier3_rate'],
                tier3_amount=breakdown['tier3_amount'],
                tier4_consumption=breakdown['tier4_units'],
                tier4_rate=breakdown['tier4_rate'],
                tier4_amount=breakdown['tier4_amount'],
                tier5_consumption=breakdown['tier5_units'],
                tier5_rate=breakdown['tier5_rate'],
                tier5_amount=breakdown['tier5_amount'],
                rate_per_cubic=Decimal(str(rate)),
                fixed_charge=Decimal('0.00'),
                total_amount=Decimal(str(total_amount)),
                senior_citizen_discount=sc_discount,
                status='Pending'
            )

            # Create notification for new meter reading
            from ..models import Notification
            from django.urls import reverse
            Notification.objects.create(
                user=None,  # Notify all admins
                notification_type='meter_reading',
                title='New Meter Reading Submitted',
                message=f'{consumer.first_name} {consumer.last_name} ({consumer.id_number}) - {consumer.barangay.name} | Bill: ₱{total_amount:.2f}',
                related_object_id=reading.id,
                redirect_url=reverse('consumers:consumer_bill', args=[consumer.id])
            )

        # Track activity for login session (using current_user from session or token)
        if current_user:
            try:
                # Find current login session
                current_session = UserLoginEvent.objects.filter(
                    user=current_user,
                    logout_timestamp__isnull=True,
                    status='success'
                ).order_by('-login_timestamp').first()

                # Log the meter reading activity
                UserActivity.objects.create(
                    user=current_user,
                    action='meter_reading_submitted',
                    description=f"Meter reading submitted for {consumer.first_name} {consumer.last_name} ({consumer.id_number}). Reading: {current_reading}, Consumption: {consumption} m³",
                    login_event=current_session
                )
            except Exception:
                pass  # Don't fail the reading submission if activity logging fails

        # Return complete bill details (ALL 11 REQUIRED FIELDS)
        return JsonResponse({
            'status': 'success',
            'message': 'Reading submitted successfully',
            'consumer_name': f"{consumer.first_name} {consumer.last_name}",
            'id_number': consumer.id_number,
            'reading_date': str(reading_date),
            'previous_reading': int(previous_reading),
            'current_reading': int(current_reading),
            'consumption': int(consumption),
            'rate': rate,
            'total_amount': total_amount,
            'field_staff_name': field_staff_name
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        # Log unexpected errors (Railway will capture this in logs)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error submitting reading: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: SUBMIT MANUAL READING WITH PROOF IMAGE
# ============================================================================
@csrf_exempt
def api_submit_manual_reading(request):
    """
    API endpoint for Android app to submit manual reading with proof photo.

    This reading requires admin confirmation before bill is generated.

    POST data:
    {
        "consumer_id": 1,
        "reading": 1275,
        "reading_date": "2025-12-01",
        "proof_image": "base64_encoded_image_string",
        "token": "session_token_from_login"
    }

    Flow:
    1. Save reading with is_confirmed=False
    2. Upload proof image to Cloudinary
    3. Create notification for admin
    4. Admin reviews and confirms/rejects
    5. Bill generated only after confirmation
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        # Authenticate using token if not already authenticated
        api_user = None
        if not request.user.is_authenticated:
            api_user = authenticate_api_request(request)

        # Determine the authenticated user (from session or token)
        current_user = request.user if request.user.is_authenticated else api_user

        data = json.loads(request.body.decode('utf-8'))

        # Extract data
        consumer_id = data.get('consumer_id')
        reading_value = data.get('reading')
        reading_date_str = data.get('reading_date')
        proof_image_base64 = data.get('proof_image')

        # Validate required fields
        if not consumer_id or reading_value is None:
            return JsonResponse({'error': 'Missing required fields: consumer_id or reading'}, status=400)

        # Get consumer
        try:
            consumer = Consumer.objects.get(id=consumer_id)
        except Consumer.DoesNotExist:
            return JsonResponse({'error': 'Consumer not found'}, status=404)

        # Check if consumer is disconnected
        if consumer.status == 'disconnected':
            return JsonResponse({
                'error': 'Consumer is disconnected',
                'message': f'{consumer.first_name} {consumer.last_name} is currently disconnected.'
            }, status=403)

        # Parse reading date
        if reading_date_str:
            try:
                reading_date = timezone.datetime.strptime(reading_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        else:
            reading_date = timezone.now().date()

        # Check for duplicate reading (same consumer, same month)
        existing_reading = MeterReading.objects.filter(
            consumer=consumer,
            reading_date__year=reading_date.year,
            reading_date__month=reading_date.month
        ).first()

        if existing_reading:
            return JsonResponse({
                'error': 'Duplicate reading',
                'message': f'Reading for {consumer.first_name} {consumer.last_name} already exists for {reading_date.strftime("%B %Y")}.'
            }, status=400)

        # Validate reading value
        try:
            current_reading = int(reading_value)
            if current_reading < 0:
                raise ValueError("Reading value cannot be negative")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid reading value.'}, status=400)

        # Get previous reading for validation
        previous_reading = get_previous_reading(consumer)
        if current_reading < previous_reading:
            return JsonResponse({
                'error': 'Invalid reading',
                'message': f'Current reading ({current_reading}) cannot be less than previous ({previous_reading})'
            }, status=400)

        consumption = current_reading - previous_reading

        # Upload proof image to Cloudinary (if provided)
        proof_image_url = None
        if proof_image_base64:
            try:
                # Check if Cloudinary is configured and available
                if not CLOUDINARY_AVAILABLE or cloudinary_uploader is None:
                    import logging
                    logging.warning("Cloudinary not configured. Skipping image upload for reading.")
                else:
                    # Upload to Cloudinary
                    upload_result = cloudinary_uploader.upload(
                        f"data:image/jpeg;base64,{proof_image_base64}",
                        folder="waterworks/meter_proofs",
                        public_id=f"reading_{consumer.id_number}_{reading_date}",
                        overwrite=True,
                        resource_type="image"
                    )
                    proof_image_url = upload_result.get('secure_url')
            except Exception as e:
                import logging
                logging.error(f"Cloudinary upload error: {e}")
                # We do NOT return a 500 here anymore.
                # If the image fails, we still want to save the actual reading numbers.
                proof_image_url = None

        # Create meter reading (NOT confirmed - needs admin review)
        reading = MeterReading.objects.create(
            consumer=consumer,
            reading_date=reading_date,
            reading_value=current_reading,
            source='app_manual',  # Manual entry from Smart Meter Reader app
            is_confirmed=False,  # Needs admin confirmation
            proof_image_url=proof_image_url,
            submitted_by=current_user  # Use current_user (from session or token)
        )

        # Create notification for admin - redirect to pending readings page
        from django.urls import reverse
        Notification.objects.create(
            user=None,  # Notify all admins
            notification_type='reading_pending_confirmation',
            title='Manual Reading - Needs Confirmation',
            message=f'{consumer.first_name} {consumer.last_name} ({consumer.id_number}) - {consumption} m³ | Proof image attached',
            related_object_id=reading.id,
            redirect_url=reverse('consumers:pending_readings')
        )

        # Get field staff name and log activity
        field_staff_name = "Field Staff"
        if current_user:
            field_staff_name = current_user.get_full_name() or current_user.username

            # Log the manual meter reading submission to UserActivity
            try:
                # Get the current login session
                current_session = UserLoginEvent.objects.filter(
                    user=current_user,
                    status='success'
                ).order_by('-login_timestamp').first()

                # Log the meter reading activity
                UserActivity.objects.create(
                    user=current_user,
                    action='meter_reading_submitted',
                    description=f"Manual reading with proof submitted for {consumer.first_name} {consumer.last_name} ({consumer.id_number}). Reading: {current_reading}, Consumption: {consumption} m³. Status: Pending confirmation.",
                    login_event=current_session
                )
            except Exception:
                pass  # Don't fail if activity logging fails

        return JsonResponse({
            'status': 'success',
            'message': 'Reading submitted for review. Awaiting admin confirmation.',
            'reading_id': reading.id,
            'consumer_id': consumer.id,
            'consumer_name': f"{consumer.first_name} {consumer.last_name}",
            'id_number': consumer.id_number,
            'reading_date': str(reading_date),
            'previous_reading': previous_reading,
            'current_reading': current_reading,
            'consumption': consumption,
            'proof_image_url': proof_image_url,
            'status': 'pending_confirmation',
            'field_staff_name': field_staff_name
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        import logging
        logging.error(f"Error submitting manual reading: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: CONFIRM MANUAL READING
# ============================================================================
@csrf_exempt
@login_required
def api_confirm_reading(request, reading_id):
    """
    API endpoint for admin to confirm a manual reading.

    POST /api/readings/<reading_id>/confirm/

    On confirm:
    1. Set is_confirmed=True
    2. Generate bill with current rates
    3. Mark notification as read
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        reading = MeterReading.objects.select_related('consumer').get(id=reading_id)

        if reading.is_confirmed:
            return JsonResponse({'error': 'Reading already confirmed'}, status=400)

        if reading.is_rejected:
            return JsonResponse({'error': 'Cannot confirm a rejected reading'}, status=400)

        consumer = reading.consumer

        # Get previous reading for consumption calculation
        prev = MeterReading.objects.filter(
            consumer=consumer,
            is_confirmed=True,
            reading_date__lt=reading.reading_date
        ).order_by('-reading_date').first()

        if prev:
            consumption = reading.reading_value - prev.reading_value
        else:
            baseline = consumer.first_reading if consumer.first_reading else 0
            consumption = reading.reading_value - baseline

        if consumption < 0:
            return JsonResponse({'error': 'Invalid consumption calculation'}, status=400)

        # Calculate bill using tiered rates
        from ..utils import calculate_tiered_water_bill
        setting = SystemSetting.objects.first()

        if setting:
            billing_day = setting.billing_day_of_month
            due_day = setting.due_day_of_month
        else:
            billing_day = 1
            due_day = 20

        total, average_rate, breakdown = calculate_tiered_water_bill(
            consumption=consumption,
            usage_type=consumer.usage_type,
            settings=setting
        )

        # Compute senior citizen water bill discount
        # 5% of total bill if consumer is SC AND consumption <= 30 m³
        sc_discount = Decimal('0.00')
        if consumer.is_senior_citizen and consumption <= 30:
            sc_discount = (total * Decimal('5') / Decimal('100')).quantize(Decimal('0.01'))

        # Create bill
        Bill.objects.create(
            consumer=consumer,
            previous_reading=prev,
            current_reading=reading,
            billing_period=reading.reading_date.replace(day=billing_day),
            due_date=reading.reading_date.replace(day=due_day),
            consumption=consumption,
            tier1_consumption=breakdown['tier1_units'],
            tier1_amount=breakdown['tier1_amount'],
            tier2_consumption=breakdown['tier2_units'],
            tier2_rate=breakdown['tier2_rate'],
            tier2_amount=breakdown['tier2_amount'],
            tier3_consumption=breakdown['tier3_units'],
            tier3_rate=breakdown['tier3_rate'],
            tier3_amount=breakdown['tier3_amount'],
            tier4_consumption=breakdown['tier4_units'],
            tier4_rate=breakdown['tier4_rate'],
            tier4_amount=breakdown['tier4_amount'],
            tier5_consumption=breakdown['tier5_units'],
            tier5_rate=breakdown['tier5_rate'],
            tier5_amount=breakdown['tier5_amount'],
            rate_per_cubic=average_rate,
            fixed_charge=Decimal('0.00'),
            total_amount=total,
            senior_citizen_discount=sc_discount,
            status='Pending'
        )

        # Update reading status
        reading.is_confirmed = True
        reading.confirmed_by = request.user
        reading.confirmed_at = timezone.now()
        reading.save()

        # Mark related notification as read
        Notification.objects.filter(
            related_object_id=reading.id,
            notification_type='meter_reading'
        ).update(is_read=True, read_at=timezone.now())

        return JsonResponse({
            'status': 'success',
            'message': 'Reading confirmed and bill generated',
            'reading_id': reading.id,
            'bill_amount': float(total),
            'consumption': consumption
        })

    except MeterReading.DoesNotExist:
        return JsonResponse({'error': 'Reading not found'}, status=404)
    except Exception as e:
        import logging
        logging.error(f"Error confirming reading: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: REJECT MANUAL READING
# ============================================================================
@csrf_exempt
@login_required
def api_reject_reading(request, reading_id):
    """
    API endpoint for admin to reject a manual reading.

    POST /api/readings/<reading_id>/reject/
    {
        "reason": "Image is blurry, please resubmit"
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        reason = data.get('reason', '').strip()

        if not reason:
            return JsonResponse({'error': 'Rejection reason is required'}, status=400)

        reading = MeterReading.objects.select_related('consumer').get(id=reading_id)

        if reading.is_confirmed:
            return JsonResponse({'error': 'Cannot reject a confirmed reading'}, status=400)

        if reading.is_rejected:
            return JsonResponse({'error': 'Reading already rejected'}, status=400)

        # Update reading status
        reading.is_rejected = True
        reading.rejected_by = request.user
        reading.rejected_at = timezone.now()
        reading.rejection_reason = reason
        reading.save()

        # Mark related notification as read
        Notification.objects.filter(
            related_object_id=reading.id,
            notification_type='meter_reading'
        ).update(is_read=True, read_at=timezone.now())

        # Create notification for field staff about rejection
        if reading.submitted_by:
            Notification.objects.create(
                user=reading.submitted_by,
                notification_type='system_alert',
                title='Reading Rejected',
                message=f'Your reading for {reading.consumer.first_name} {reading.consumer.last_name} was rejected. Reason: {reason}',
                related_object_id=reading.id,
                redirect_url=reverse('consumers:consumer_bill', args=[reading.consumer.id])
            )

        return JsonResponse({
            'status': 'success',
            'message': 'Reading rejected',
            'reading_id': reading.id,
            'reason': reason
        })

    except MeterReading.DoesNotExist:
        return JsonResponse({'error': 'Reading not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import logging
        logging.error(f"Error rejecting reading: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: GET NOTIFICATIONS LIST
# ============================================================================
@csrf_exempt
@login_required
def api_get_notifications(request):
    """
    API endpoint to get notifications for the current user.

    GET /api/notifications/
    GET /api/notifications/?unread_only=true

    Returns list of notifications (newest first).
    """
    try:
        unread_only = request.GET.get('unread_only', 'false').lower() == 'true'

        # Get notifications for this user or all admins (user=None)
        notifications = Notification.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_archived=False
        ).order_by('-created_at')

        if unread_only:
            notifications = notifications.filter(is_read=False)

        # Limit to last 50
        notifications = notifications[:50]

        data = []
        for n in notifications:
            data.append({
                'id': n.id,
                'type': n.notification_type,
                'title': n.title,
                'message': n.message,
                'is_read': n.is_read,
                'redirect_url': n.redirect_url,
                'related_object_id': n.related_object_id,
                'created_at': n.created_at.isoformat(),
                'read_at': n.read_at.isoformat() if n.read_at else None,
            })

        return JsonResponse({
            'status': 'success',
            'notifications': data,
            'total': len(data)
        })

    except Exception as e:
        import logging
        logging.error(f"Error fetching notifications: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: GET UNREAD NOTIFICATION COUNT
# ============================================================================
@csrf_exempt
@login_required
def api_get_notification_count(request):
    """
    API endpoint to get unread notification count.

    GET /api/notifications/count/

    Returns: { "unread_count": 5 }
    """
    try:
        count = Notification.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_read=False,
            is_archived=False
        ).count()

        return JsonResponse({
            'status': 'success',
            'unread_count': count
        })

    except Exception as e:
        import logging
        logging.error(f"Error fetching notification count: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: MARK NOTIFICATION AS READ
# ============================================================================
@csrf_exempt
@login_required
def api_mark_notification_read(request, notification_id):
    """
    API endpoint to mark a notification as read.

    POST /api/notifications/<id>/mark-read/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        notification = Notification.objects.get(id=notification_id)

        # Check if user can access this notification
        if notification.user and notification.user != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)

        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Notification marked as read'
        })

    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)
    except Exception as e:
        import logging
        logging.error(f"Error marking notification as read: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: GET PENDING READINGS (for admin review)
# ============================================================================
@csrf_exempt
@login_required
def api_get_pending_readings(request):
    """
    API endpoint to get all readings pending confirmation.

    GET /api/readings/pending/

    Returns list of readings that need admin review.
    """
    try:
        readings = MeterReading.objects.filter(
            is_confirmed=False,
            is_rejected=False,
            source='app_manual'  # Manual entry from Smart Meter Reader app
        ).select_related('consumer', 'consumer__barangay', 'submitted_by').order_by('-created_at')

        data = []
        for r in readings:
            # Calculate consumption
            prev = MeterReading.objects.filter(
                consumer=r.consumer,
                is_confirmed=True,
                reading_date__lt=r.reading_date
            ).order_by('-reading_date').first()

            if prev:
                consumption = r.reading_value - prev.reading_value
            else:
                baseline = r.consumer.first_reading if r.consumer.first_reading else 0
                consumption = r.reading_value - baseline

            data.append({
                'reading_id': r.id,
                'consumer_id': r.consumer.id,
                'consumer_name': f"{r.consumer.first_name} {r.consumer.last_name}",
                'id_number': r.consumer.id_number,
                'barangay': r.consumer.barangay.name if r.consumer.barangay else '',
                'reading_date': r.reading_date.isoformat(),
                'reading_value': r.reading_value,
                'consumption': consumption,
                'proof_image_url': r.proof_image_url,
                'submitted_by': r.submitted_by.get_full_name() if r.submitted_by else 'Unknown',
                'submitted_at': r.created_at.isoformat(),
            })

        return JsonResponse({
            'status': 'success',
            'pending_readings': data,
            'total': len(data)
        })

    except Exception as e:
        import logging
        logging.error(f"Error fetching pending readings: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



@csrf_exempt
def api_login(request):
    """Enhanced API login for Android app with security tracking."""
    from ..decorators import get_client_ip, get_user_agent

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        # Get security information
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            # Check if user is Field Staff - only Field Staff can use mobile app
            try:
                profile = StaffProfile.objects.get(user=user)

                # Only allow field_staff role to login to mobile app
                if profile.role != 'field_staff':
                    UserLoginEvent.objects.create(
                        user=user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        login_method='mobile',
                        status='failed'
                    )
                    return JsonResponse({
                        'error': 'Access denied. Only Field Staff accounts can use this app.',
                        'message': 'Superadmin and Cashier accounts should use the web portal.'
                    }, status=403)

                # Check if Field Staff has assigned barangay
                if not profile.assigned_barangay:
                    return JsonResponse({
                        'error': 'No assigned barangay',
                        'message': 'Please contact your administrator to assign a barangay.'
                    }, status=403)

                login(request, user)

                # Ensure session is created (for API requests)
                if not request.session.session_key:
                    request.session.create()

                session_key = request.session.session_key

                # Record successful mobile login event
                UserLoginEvent.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    login_method='mobile',
                    status='success',
                    session_key=session_key
                )

                return JsonResponse({
                    'status': 'success',
                    'token': session_key,
                    'barangay_id': profile.assigned_barangay.id,
                    'barangay': profile.assigned_barangay.name,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'full_name': user.get_full_name(),
                        'role': profile.role
                    }
                })
            except StaffProfile.DoesNotExist:
                # No profile means not a valid staff account
                UserLoginEvent.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    login_method='mobile',
                    status='failed'
                )
                return JsonResponse({'error': 'Account not configured. Please contact administrator.'}, status=403)
        else:
            # Record failed login attempt
            if user:
                UserLoginEvent.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    login_method='mobile',
                    status='failed'
                )
            return JsonResponse({'error': 'Invalid credentials'}, status=401)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        # Log unexpected errors (Railway will capture this in logs)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error during API login: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



@csrf_exempt
def api_logout(request):
    """API logout for Android app with session tracking."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        # Get token from request body or Authorization header
        token = None
        if request.body:
            try:
                data = json.loads(request.body)
                token = data.get('token')
            except json.JSONDecodeError:
                pass

        if not token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]

        if token:
            # Find and update the session
            latest_session = UserLoginEvent.objects.filter(
                session_key=token,
                logout_timestamp__isnull=True
            ).first()

            if latest_session:
                latest_session.logout_timestamp = timezone.now()
                latest_session.save()

                # Also logout from Django session if authenticated
                if request.user.is_authenticated:
                    logout(request)

                return JsonResponse({
                    'status': 'success',
                    'message': 'Logged out successfully',
                    'logout_time': timezone.now().isoformat()
                })
            else:
                # Session not found, might already be logged out
                return JsonResponse({
                    'status': 'success',
                    'message': 'Session already logged out or not found',
                    'logout_time': timezone.now().isoformat()
                })
        else:
            return JsonResponse({
                'error': 'No token provided',
                'message': 'Please provide token in request body or Authorization header'
            }, status=400)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error during API logout: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def api_consumers(request):
    """
    Get consumers for the staff's assigned barangay.
    OPTIMIZED: Uses prefetch_related and annotations to avoid N+1 queries.
    """
    try:
        from django.db.models import Prefetch, Exists, OuterRef

        profile = StaffProfile.objects.select_related('assigned_barangay').get(user=request.user)

        # PERFORMANCE FIX: Prefetch latest reading and annotate bill counts
        # This reduces 300+ queries to just 3 queries for 100 consumers
        consumers = Consumer.objects.filter(
            barangay=profile.assigned_barangay
        ).select_related(
            'barangay', 'purok'
        ).prefetch_related(
            # Prefetch only the latest confirmed reading per consumer
            Prefetch(
                'meter_readings',
                queryset=MeterReading.objects.filter(
                    is_confirmed=True
                ).order_by('-reading_date', '-created_at'),
                to_attr='latest_readings_list'
            )
        ).annotate(
            # Annotate pending bills count (1 query for all consumers)
            pending_bills_count_db=Count(
                'bills',
                filter=Q(bills__status='Pending')
            ),
            # Annotate delinquent status (no separate query needed)
            has_overdue_db=Exists(
                Bill.objects.filter(
                    consumer=OuterRef('pk'),
                    status='Pending',
                    due_date__lt=timezone.now().date()
                )
            )
        )

        data = []
        for consumer in consumers:
            # Get latest reading from prefetched data
            latest_reading_value = 0
            if consumer.latest_readings_list:
                latest_reading_value = consumer.latest_readings_list[0].reading_value

            # Append consumer data using annotated fields
            data.append({
                'id': consumer.id,
                'id_number': consumer.id_number,  # Numeric ID format: 2025110001
                'name': f"{consumer.first_name} {consumer.last_name}",
                'first_name': consumer.first_name,
                'last_name': consumer.last_name,
                'serial_number': consumer.serial_number,
                'household_number': consumer.household_number,
                'barangay': consumer.barangay.name if consumer.barangay else '',
                'purok': consumer.purok.name if consumer.purok else '',
                'address': f"{consumer.purok.name if consumer.purok else ''}, {consumer.barangay.name if consumer.barangay else ''}",
                'phone_number': consumer.phone_number,
                'status': consumer.status,  # 'active' or 'disconnected'
                'is_active': consumer.status == 'active',
                'usage_type': consumer.usage_type,  # 'Residential' or 'Commercial' - needed for accurate rate calculation
                'latest_confirmed_reading': latest_reading_value,
                'previous_reading': latest_reading_value,  # Alias for Android app compatibility
                # Delinquent status from annotated field (no extra query!)
                'is_delinquent': consumer.has_overdue_db,
                'pending_bills_count': consumer.pending_bills_count_db
            })

        return JsonResponse(data, safe=False)
    except StaffProfile.DoesNotExist:
        return JsonResponse({'error': 'No assigned barangay'}, status=403)



@csrf_exempt
@login_required
def api_get_previous_reading(request, consumer_id):
    """
    API endpoint to get the previous confirmed reading for a specific consumer.

    This provides a dedicated endpoint for the Android app to fetch just the
    previous reading without needing to load all consumers.

    URL: /api/consumers/<consumer_id>/previous-reading/
    Method: GET

    Returns:
        - consumer_id: int
        - id_number: str
        - consumer_name: str
        - previous_reading: int (0 if no confirmed reading exists)
        - last_reading_date: str or null
    """
    try:
        consumer = Consumer.objects.get(id=consumer_id)

        # Get previous reading using the same logic as get_previous_reading()
        latest_reading = MeterReading.objects.filter(
            consumer=consumer,
            is_confirmed=True
        ).order_by('-reading_date', '-created_at').first()

        previous_reading_value = latest_reading.reading_value if latest_reading else 0
        last_reading_date = latest_reading.reading_date.isoformat() if latest_reading else None

        return JsonResponse({
            'consumer_id': consumer.id,
            'id_number': consumer.id_number,
            'consumer_name': f"{consumer.first_name} {consumer.last_name}",
            'usage_type': consumer.usage_type,  # 'Residential' or 'Commercial' - needed for accurate rate calculation
            'previous_reading': previous_reading_value,
            'last_reading_date': last_reading_date
        })
    except Consumer.DoesNotExist:
        return JsonResponse({'error': 'Consumer not found'}, status=404)


# NEW: API View for fetching the current water rates (Residential & Commercial)
@csrf_exempt
@login_required
def api_get_current_rates(request):
    """
    API endpoint for the Android app to fetch all tiered water rates.

    Returns complete tiered rate structure for both Residential and Commercial.
    """
    try:
        # Get the first (or only) SystemSetting object (singleton pattern)
        setting = SystemSetting.objects.first()
        if not setting:
            # Handle the case where no SystemSetting exists
            return JsonResponse({'error': 'System settings not configured.'}, status=500)

        # Return all tiered rates as JSON
        return JsonResponse({
            'status': 'success',
            # Residential Tiered Rates
            'residential': {
                'minimum_charge': float(setting.residential_minimum_charge),  # Tier 1: 1-5 m³
                'tier2_rate': float(setting.residential_tier2_rate),  # 6-10 m³
                'tier3_rate': float(setting.residential_tier3_rate),  # 11-20 m³
                'tier4_rate': float(setting.residential_tier4_rate),  # 21-50 m³
                'tier5_rate': float(setting.residential_tier5_rate),  # 51+ m³
            },
            # Commercial Tiered Rates
            'commercial': {
                'minimum_charge': float(setting.commercial_minimum_charge),  # Tier 1: 1-5 m³
                'tier2_rate': float(setting.commercial_tier2_rate),  # 6-10 m³
                'tier3_rate': float(setting.commercial_tier3_rate),  # 11-20 m³
                'tier4_rate': float(setting.commercial_tier4_rate),  # 21-50 m³
                'tier5_rate': float(setting.commercial_tier5_rate),  # 51+ m³
            },
            # Tier brackets info for reference
            'tier_brackets': {
                'tier1': '1-5 m³ (minimum charge)',
                'tier2': '6-10 m³',
                'tier3': '11-20 m³',
                'tier4': '21-50 m³',
                'tier5': '51+ m³'
            },
            # Legacy rates (for backward compatibility)
            'residential_rate_per_cubic': float(setting.residential_rate_per_cubic),
            'commercial_rate_per_cubic': float(setting.commercial_rate_per_cubic),
            'updated_at': setting.updated_at.isoformat()
        })

    except Exception as e:
        # Log unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching rates: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: GET BILL DETAILS FOR A CONSUMER
# ============================================================================
@csrf_exempt
def api_get_consumer_bill(request, consumer_id):
    """
    API endpoint for Android app to get bill details for a specific consumer.

    URL: /api/consumers/<consumer_id>/bill/

    Returns the latest pending bill for the consumer with all details needed
    for the Bill Details screen in the mobile app.
    """
    try:
        # Get the consumer
        consumer = Consumer.objects.select_related('barangay', 'purok').get(id=consumer_id)

        # Get the latest bill for this consumer
        bill = Bill.objects.filter(
            consumer=consumer
        ).select_related(
            'current_reading', 'previous_reading'
        ).order_by('-billing_period', '-created_at').first()

        if not bill:
            return JsonResponse({
                'status': 'no_bill',
                'message': 'No bill found for this consumer',
                'consumer_id': consumer.id,
                'consumer_name': f"{consumer.first_name} {consumer.last_name}",
                'id_number': consumer.id_number,
            }, status=404)

        # Get reader name from the meter reading source
        reader_name = "System"
        if bill.current_reading:
            if bill.current_reading.source in ['app_scanned', 'app_manual']:
                reader_name = "Field Staff (Mobile)"
            elif bill.current_reading.source == 'manual':
                reader_name = "Office Staff (Manual)"

        return JsonResponse({
            'status': 'success',

            # Consumer Info
            'consumer_id': consumer.id,
            'id_number': consumer.id_number,
            'consumer_name': f"{consumer.first_name} {consumer.last_name}",
            'address': f"{consumer.purok.name if consumer.purok else ''}, {consumer.barangay.name if consumer.barangay else ''}",
            'account_type': consumer.usage_type,  # Residential or Commercial
            'serial_number': consumer.serial_number,

            # Bill Info
            'bill_id': bill.id,
            'billing_date': bill.billing_period.isoformat(),
            'due_date': bill.due_date.isoformat(),
            'bill_status': bill.status,

            # Meter Readings
            'previous_reading': bill.previous_reading.reading_value if bill.previous_reading else consumer.first_reading or 0,
            'current_reading': bill.current_reading.reading_value if bill.current_reading else 0,
            'reading_date': bill.current_reading.reading_date.isoformat() if bill.current_reading else None,
            'consumption': bill.consumption,

            # Tiered Rate Breakdown
            'tier_breakdown': {
                'tier1': {
                    'range': '1-5 m³',
                    'consumption': bill.tier1_consumption,
                    'amount': float(bill.tier1_amount),
                    'description': 'Minimum Charge'
                },
                'tier2': {
                    'range': '6-10 m³',
                    'consumption': bill.tier2_consumption,
                    'rate': float(bill.tier2_rate),
                    'amount': float(bill.tier2_amount)
                },
                'tier3': {
                    'range': '11-20 m³',
                    'consumption': bill.tier3_consumption,
                    'rate': float(bill.tier3_rate),
                    'amount': float(bill.tier3_amount)
                },
                'tier4': {
                    'range': '21-50 m³',
                    'consumption': bill.tier4_consumption,
                    'rate': float(bill.tier4_rate),
                    'amount': float(bill.tier4_amount)
                },
                'tier5': {
                    'range': '51+ m³',
                    'consumption': bill.tier5_consumption,
                    'rate': float(bill.tier5_rate),
                    'amount': float(bill.tier5_amount)
                }
            },

            # Totals
            'rate_per_cubic': float(bill.rate_per_cubic),  # Average rate
            'total_amount': float(bill.total_amount),

            # Penalty Info
            'penalty_amount': float(bill.penalty_amount),
            'penalty_waived': bill.penalty_waived,
            'total_amount_due': float(bill.total_amount + bill.penalty_amount) if not bill.penalty_waived else float(bill.total_amount),

            # Metadata
            'reader_name': reader_name,
            'printed_at': timezone.now().isoformat(),
            'created_at': bill.created_at.isoformat(),
        })

    except Consumer.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Consumer not found'
        }, status=404)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching bill for consumer {consumer_id}: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: GET ALL BILLS FOR A CONSUMER (History)
# ============================================================================
@csrf_exempt
def api_get_consumer_bills(request, consumer_id):
    """
    API endpoint for Android app to get all bills for a specific consumer.

    URL: /api/consumers/<consumer_id>/bills/

    Returns list of all bills (history) for the consumer.
    """
    try:
        consumer = Consumer.objects.get(id=consumer_id)

        bills = Bill.objects.filter(
            consumer=consumer
        ).select_related(
            'current_reading', 'previous_reading'
        ).order_by('-billing_period', '-created_at')

        bills_list = []
        for bill in bills:
            bills_list.append({
                'bill_id': bill.id,
                'billing_date': bill.billing_period.isoformat(),
                'due_date': bill.due_date.isoformat(),
                'consumption': bill.consumption,
                'total_amount': float(bill.total_amount),
                'penalty_amount': float(bill.penalty_amount),
                'status': bill.status,
                'previous_reading': bill.previous_reading.reading_value if bill.previous_reading else 0,
                'current_reading': bill.current_reading.reading_value if bill.current_reading else 0,
            })

        return JsonResponse({
            'status': 'success',
            'consumer_id': consumer.id,
            'consumer_name': f"{consumer.first_name} {consumer.last_name}",
            'id_number': consumer.id_number,
            'total_bills': len(bills_list),
            'bills': bills_list
        })

    except Consumer.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Consumer not found'
        }, status=404)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching bills for consumer {consumer_id}: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



# ============================================================================
# API VIEW: GET SYSTEM SETTINGS FOR MOBILE APP
# ============================================================================
@csrf_exempt
def api_get_system_settings(request):
    """
    API endpoint for Android app to fetch all system settings.

    Returns:
    - Reading schedule (start/end days)
    - Billing schedule (billing day, due day)
    - Penalty settings (enabled, rate, type)
    - All tiered water rates
    - Last updated timestamp

    This allows the mobile app to:
    1. Show field staff the current reading period
    2. Display billing information to users
    3. Calculate estimated bills with current rates
    """
    try:
        setting = SystemSetting.objects.first()
        if not setting:
            return JsonResponse({'error': 'System settings not configured.'}, status=500)

        return JsonResponse({
            'status': 'success',

            # Reading Schedule - Controls when field staff should submit readings
            'reading_schedule': {
                'start_day': setting.reading_start_day,
                'end_day': setting.reading_end_day,
                'description': f'Day {setting.reading_start_day} to Day {setting.reading_end_day} of each month'
            },

            # Billing Schedule - Controls dates shown on bills
            'billing_schedule': {
                'billing_day': setting.billing_day_of_month,
                'due_day': setting.due_day_of_month,
                'description': f'Bills dated Day {setting.billing_day_of_month}, Due Day {setting.due_day_of_month}'
            },

            # Penalty Settings
            'penalty': {
                'enabled': setting.penalty_enabled,
                'type': setting.penalty_type,
                'rate': float(setting.penalty_rate) if setting.penalty_type == 'percentage' else None,
                'fixed_amount': float(setting.fixed_penalty_amount) if setting.penalty_type == 'fixed' else None,
                'grace_period_days': setting.penalty_grace_period_days,
                'max_amount': float(setting.max_penalty_amount) if setting.max_penalty_amount > 0 else None,
                'description': f'{setting.penalty_rate}% penalty applied after Day {setting.due_day_of_month}' if setting.penalty_enabled else 'Penalties disabled'
            },

            # Residential Tiered Rates
            'residential_rates': {
                'minimum_charge': float(setting.residential_minimum_charge),
                'tier2_rate': float(setting.residential_tier2_rate),
                'tier3_rate': float(setting.residential_tier3_rate),
                'tier4_rate': float(setting.residential_tier4_rate),
                'tier5_rate': float(setting.residential_tier5_rate),
            },

            # Commercial Tiered Rates
            'commercial_rates': {
                'minimum_charge': float(setting.commercial_minimum_charge),
                'tier2_rate': float(setting.commercial_tier2_rate),
                'tier3_rate': float(setting.commercial_tier3_rate),
                'tier4_rate': float(setting.commercial_tier4_rate),
                'tier5_rate': float(setting.commercial_tier5_rate),
            },

            # Tier brackets info
            'tier_brackets': {
                'tier1': '1-5 m³ (minimum charge)',
                'tier2': '6-10 m³',
                'tier3': '11-20 m³',
                'tier4': '21-50 m³',
                'tier5': '51+ m³'
            },

            # Metadata
            'updated_at': setting.updated_at.isoformat(),
        })

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching system settings: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)



@csrf_exempt
def api_check_settings_version(request):
    """
    Lightweight API endpoint for Android app to check if settings have been updated.

    The app should poll this endpoint periodically (e.g., every 5 minutes or on app resume)
    to check if settings have changed since last sync.

    Request (optional):
    {
        "last_updated": "2025-01-08T10:30:00Z"  # ISO format timestamp from app's last sync
    }

    Response:
    {
        "status": "success",
        "settings_changed": true/false,
        "current_version": "2025-01-08T14:25:30.123456+00:00",
        "message": "Settings have been updated. Please sync."
    }

    Usage in Android:
    1. App stores last_updated timestamp from /api/settings/ response
    2. Periodically calls this endpoint with last_updated
    3. If settings_changed = true, fetches full settings from /api/settings/
    """
    try:
        setting = SystemSetting.objects.first()
        if not setting:
            return JsonResponse({
                'status': 'error',
                'message': 'System settings not configured'
            }, status=500)

        # Get last_updated timestamp from request (if provided)
        last_updated_str = None
        if request.method == 'POST':
            try:
                data = json.loads(request.body.decode('utf-8'))
                last_updated_str = data.get('last_updated')
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        elif request.method == 'GET':
            last_updated_str = request.GET.get('last_updated')

        # Compare timestamps
        settings_changed = False
        if last_updated_str:
            try:
                from datetime import datetime as dt
                # Parse ISO format timestamp from app
                last_updated = dt.fromisoformat(last_updated_str.replace('Z', '+00:00'))

                # Make timezone-aware if needed
                if timezone.is_naive(last_updated):
                    last_updated = timezone.make_aware(last_updated)

                # Check if settings were updated after last sync
                settings_changed = setting.updated_at > last_updated
            except (ValueError, AttributeError):
                # If parsing fails, assume settings changed (force sync)
                settings_changed = True
        else:
            # No last_updated provided, assume first sync
            settings_changed = True

        return JsonResponse({
            'status': 'success',
            'settings_changed': settings_changed,
            'current_version': setting.updated_at.isoformat(),
            'message': 'Settings have been updated. Please sync.' if settings_changed else 'Settings are up to date.',
            'last_change': {
                'date': setting.updated_at.strftime('%Y-%m-%d'),
                'time': setting.updated_at.strftime('%I:%M %p')
            }
        })

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error checking settings version: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


@csrf_exempt
def smart_meter_webhook(request):
    """
    Webhook endpoint for IoT smart meters to submit readings.
    Requires API key authentication via X-API-Key header.
    Set SMART_METER_API_KEY in .env file.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    # Authenticate using API key from header
    from decouple import config
    expected_api_key = config('SMART_METER_API_KEY', default='')
    provided_api_key = request.META.get('HTTP_X_API_KEY', '')

    if not expected_api_key:
        # API key not configured - reject all requests for security
        return JsonResponse({'error': 'Webhook not configured'}, status=503)

    if provided_api_key != expected_api_key:
        # Invalid or missing API key
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    # Process the webhook data
    try:
        data = json.loads(request.body)

        # Validate required fields
        required_fields = ['consumer_id', 'reading', 'date']
        if not all(field in data for field in required_fields):
            return JsonResponse({
                'error': 'Missing required fields',
                'required': required_fields
            }, status=400)

        # Get consumer
        consumer = get_object_or_404(Consumer, id=data['consumer_id'])

        # Validate reading value
        reading_value = int(data['reading'])
        if reading_value < 0:
            return JsonResponse({'error': 'Reading value cannot be negative'}, status=400)

        # Create meter reading
        MeterReading.objects.create(
            consumer=consumer,
            reading_value=reading_value,
            reading_date=data['date'],
            source='app_scanned'  # Auto-confirmed reading (webhook/IoT)
        )
        return JsonResponse({'status': 'success', 'message': 'Reading recorded'})

    except Consumer.DoesNotExist:
        return JsonResponse({'error': 'Consumer not found'}, status=404)
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': 'Invalid data format'}, status=400)
    except Exception as e:
        # Log error but don't expose details
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Smart meter webhook error: {e}", exc_info=True)
        return JsonResponse({'error': 'Processing failed'}, status=500)
