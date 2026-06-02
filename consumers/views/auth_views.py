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


@rate_limit_login
def staff_login(request):
    """Enhanced staff login with security tracking and rate limiting."""
    from ..decorators import get_client_ip, get_user_agent

    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        # Get security information
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        if user is not None and user.is_staff:
            # Check if user is Field Staff - they can only login via mobile app
            if hasattr(user, 'staffprofile') and user.staffprofile.role == 'field_staff':
                # Record blocked login attempt
                UserLoginEvent.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    login_method='web',
                    status='failed'
                )
                messages.error(request, "Field Staff accounts can only access the system through the Smart Meter Reader mobile application.")
                return render(request, 'consumers/login.html')

            # Successful login for Superadmin and Cashier
            login(request, user)

            # Record login event
            UserLoginEvent.objects.create(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                login_method='web',
                status='success',
                session_key=request.session.session_key
            )

            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            # Cashier goes directly to payment processing page
            if hasattr(user, 'staffprofile') and user.staffprofile.role == 'cashier':
                return redirect('consumers:process_payment')
            return redirect('consumers:home')
        else:
            # Failed login attempt
            if user:
                # User exists but not staff - record failed attempt
                UserLoginEvent.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    login_method='web',
                    status='failed'
                )
            messages.error(request, "Invalid credentials or not staff member.")

    return render(request, 'consumers/login.html')



@login_required
def staff_logout(request):
    """Enhanced logout with session tracking."""
    # Update the latest active session for this user
    try:
        latest_session = UserLoginEvent.objects.filter(
            user=request.user,
            session_key=request.session.session_key,
            logout_timestamp__isnull=True
        ).first()

        if latest_session:
            latest_session.logout_timestamp = timezone.now()
            latest_session.save()
    except Exception as e:
        # Log error but don't prevent logout
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error updating logout timestamp: {e}")

    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("consumers:staff_login")


def send_email_notification(subject, html_message, plain_message, to_emails):
    """
    Sends an email using Resend API if configured, otherwise falls back to Django's SMTP backend.
    This handles Render's free tier which blocks outbound SMTP ports.
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    import logging
    logger = logging.getLogger(__name__)

    # Ensure to_emails is a list
    if isinstance(to_emails, str):
        to_emails = [to_emails]

    resend_key = getattr(settings, 'RESEND_API_KEY', None)
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key
            params = {
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": to_emails,
                "subject": subject,
                "html": html_message,
                "text": plain_message,
            }
            resend.Emails.send(params)
            return True
        except Exception as e:
            logger.error(f"Resend API error sending email to {to_emails}: {e}", exc_info=True)
            raise e
    else:
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=to_emails,
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send(fail_silently=False)
            return True
        except Exception as e:
            logger.error(f"Gmail SMTP error sending email to {to_emails}: {e}", exc_info=True)
            raise e


def forgot_password_request(request):
    """
    Password reset request page for superuser/admin accounts.
    Sends secure reset token via email to the user's registered account.
    Automatically handles Resend API for production (Render) and SMTP for local.
    """
    import logging
    from ..decorators import get_client_ip, get_user_agent
    from django.template.loader import render_to_string

    logger = logging.getLogger(__name__)

    # Check if we have either Resend or SMTP configured
    if not getattr(settings, 'RESEND_API_KEY', None) and (not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD):
        logger.warning("Forgot Password: No email backend configured (neither RESEND_API_KEY nor EMAIL_HOST_USER is set).")
        return render(request, 'consumers/forgot_password.html', {'email_disabled': True})

    if request.method == "POST":
        email = request.POST.get('email', '').strip()

        try:
            # Only allow password reset for superuser/superadmin accounts
            user = User.objects.filter(email__iexact=email, is_superuser=True).first()
            if not user:
                raise User.DoesNotExist

            # Check if user already has a valid token
            existing_token = PasswordResetToken.objects.filter(
                user=user,
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()

            if existing_token:
                # Reuse existing valid token
                token = existing_token
            else:
                # Create a new password reset token
                token = PasswordResetToken.objects.create(
                    user=user,
                    ip_address=get_client_ip(request)
                )

            # Build reset URL
            reset_url = request.build_absolute_uri(
                reverse('consumers:password_reset_confirm', kwargs={'token': token.token})
            )

            # Prepare email context
            email_context = {
                'username': user.username,
                'reset_url': reset_url,
                'request_time': token.created_at.strftime('%B %d, %Y at %I:%M %p'),
                'expiration_time': token.expires_at.strftime('%B %d, %Y at %I:%M %p'),
                'ip_address': get_client_ip(request) or 'Unknown',
            }

            # Render email templates
            html_message = render_to_string('consumers/emails/password_reset_email.html', email_context)
            plain_message = render_to_string('consumers/emails/password_reset_email.txt', email_context)

            # Send email using unified helper
            try:
                send_email_notification(
                    subject='Password Reset Request - Balilihan Waterworks',
                    html_message=html_message,
                    plain_message=plain_message,
                    to_emails=[user.email]
                )

                # Log the activity
                UserActivity.objects.create(
                    user=user,
                    action='password_reset_requested',
                    description=f'Password reset email sent to {user.email}',
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )

                masked_email = f"{user.email[:3]}***@{user.email.split('@')[1]}"
                messages.success(request, f"Password reset link has been sent to your email: {masked_email}")
                return redirect('consumers:forgot_password')

            except Exception as e:
                error_msg = str(e)
                messages.error(request, f"Failed to send password reset email. Please contact your administrator. ({error_msg[:100]})")
                return redirect('consumers:forgot_password')

        except User.DoesNotExist:
            # For security, don't reveal whether an account exists
            messages.success(request, "If a Superadmin account with that email exists, a password reset link has been sent.")
            return redirect('consumers:forgot_password')

    return render(request, 'consumers/forgot_password.html')



def forgot_username(request):
    """
    Username recovery page — allows users to recover their username via email.
    """
    import logging
    from django.template.loader import render_to_string

    logger = logging.getLogger(__name__)
    recovered_username = None

    if request.method == "POST":
        email = request.POST.get('email', '').strip()

        if email:
            # For security, always claim success to prevent email enumeration
            messages.success(request, "If a Superadmin account matches that email, a recovery message has been sent.")

            # Only recover username for superuser accounts
            users = User.objects.filter(email__iexact=email, is_superuser=True)
            if users.exists():
                usernames = [u.username for u in users]
                recovered_usernames_str = ", ".join(usernames)

                # Send recovery email using unified helper
                try:
                    email_context = {'username': recovered_usernames_str}
                    html_message = render_to_string('consumers/emails/username_recovery_email.html', email_context)
                    plain_message = render_to_string('consumers/emails/username_recovery_email.txt', email_context)

                    send_email_notification(
                        subject='Username Recovery - Balilihan Waterworks',
                        html_message=html_message,
                        plain_message=plain_message,
                        to_emails=[email]
                    )

                except Exception as e:
                    # Error is already logged in send_email_notification
                    pass
        else:
            messages.error(request, "Please provide the registered email address.")

    return render(request, 'consumers/forgot_username.html', {
        'recovered_username': recovered_username
    })



def account_recovery(request):
    """
    Unified account recovery — recovers username and generates a password reset link.
    """
    import logging
    from ..decorators import get_client_ip
    from django.template.loader import render_to_string

    logger = logging.getLogger(__name__)
    recovery_result = None

    if request.method == "POST":
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        user = None

        # Only allow recovery for superuser accounts
        if email:
            user = User.objects.filter(email__iexact=email, is_superuser=True).first()
            if not user:
                messages.error(request, "No Superadmin account found with that email address.")

        # Try by full name if email not provided or not found
        elif first_name and last_name:
            user = User.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                is_superuser=True
            ).first()
            if not user:
                messages.error(request, "No Superadmin account found with that name.")
        else:
            messages.error(request, "Please enter your email or full name.")

        if user and user.is_superuser:
            # Generate (or reuse existing) password reset token
            existing_token = PasswordResetToken.objects.filter(
                user=user,
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()

            if existing_token:
                token = existing_token
            else:
                token = PasswordResetToken.objects.create(
                    user=user,
                    ip_address=get_client_ip(request)
                )

            reset_url = request.build_absolute_uri(
                reverse('consumers:password_reset_confirm', kwargs={'token': token.token})
            )

            # Send recovery email using unified helper
            try:
                email_context = {
                    'username': user.username,
                    'reset_url': reset_url,
                    'request_time': token.created_at.strftime('%B %d, %Y at %I:%M %p'),
                    'expiration_time': token.expires_at.strftime('%B %d, %Y at %I:%M %p'),
                    'ip_address': get_client_ip(request) or 'Unknown',
                }
                html_message = render_to_string('consumers/emails/password_reset_email.html', email_context)
                plain_message = render_to_string('consumers/emails/password_reset_email.txt', email_context)

                send_email_notification(
                    subject='Account Recovery & Password Reset - Balilihan Waterworks',
                    html_message=html_message,
                    plain_message=plain_message,
                    to_emails=[user.email]
                )

                # Log activity
                UserActivity.objects.create(
                    user=user,
                    action='password_reset_requested',
                    description=f'Account recovery email sent for {user.username}',
                    ip_address=get_client_ip(request)
                )

            except Exception as e:
                # Error is already logged in send_email_notification
                pass

        # Always show a generic success message to prevent enumeration
        messages.success(request, "If an account was found, a recovery email has been sent with further instructions.")
        recovery_result = {'email_sent': True}

    return render(request, 'consumers/account_recovery.html', {
        'recovery_result': recovery_result
    })



def password_reset_confirm(request, token):
    """
    Confirm password reset with token and set new password.
    """
    from ..decorators import get_client_ip, get_user_agent

    try:
        reset_token = PasswordResetToken.objects.get(token=token)

        # Check if token is valid
        if not reset_token.is_valid():
            messages.error(request, "This password reset link has expired or has already been used.")
            return redirect('consumers:staff_login')

        if request.method == "POST":
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            # Validate passwords match
            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return render(request, 'consumers/reset_password.html', {
                    'token': token,
                    'username': reset_token.user.username
                })

            # Validate password strength
            if len(new_password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
                return render(request, 'consumers/reset_password.html', {
                    'token': token,
                    'username': reset_token.user.username
                })

            # Set new password
            user = reset_token.user
            user.set_password(new_password)
            user.save()

            # Mark token as used
            reset_token.is_used = True
            reset_token.save()

            # Log the activity
            UserActivity.objects.create(
                user=user,
                action='password_reset_completed',
                description=f'Password reset completed for {user.username}',
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                target_user=user
            )

            messages.success(request, "Your password has been reset successfully! You can now login with your new password.")
            return redirect('consumers:password_reset_complete')

        return render(request, 'consumers/reset_password.html', {
            'token': token,
            'username': reset_token.user.username
        })

    except PasswordResetToken.DoesNotExist:
        messages.error(request, "Invalid password reset link.")
        return redirect('consumers:staff_login')



def password_reset_complete(request):
    """
    Password reset success confirmation page.
    """
    return render(request, 'consumers/reset_complete.html')
