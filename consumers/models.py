# consumers/models.py
from django.db import models
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
from django.contrib.auth.models import User



# Enhanced Model to track user login events with security features
class UserLoginEvent(models.Model):
    """
    Stores comprehensive information about user login attempts and sessions.
    Includes security tracking features for audit and monitoring purposes.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="The user who logged in.")
    login_timestamp = models.DateTimeField(default=timezone.now, help_text="The date and time the user logged in.", db_index=True)

    # Security tracking fields
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of the login attempt")
    user_agent = models.TextField(blank=True, help_text="Browser/device information")
    login_method = models.CharField(max_length=20, default='web', choices=[
        ('web', 'Web Portal'),
        ('mobile', 'Mobile App'),
        ('api', 'API')
    ], help_text="Method used to login")
    status = models.CharField(max_length=20, default='success', choices=[
        ('success', 'Successful'),
        ('failed', 'Failed'),
        ('locked', 'Account Locked')
    ], help_text="Login attempt status")

    # Session tracking
    session_key = models.CharField(max_length=40, blank=True, null=True, help_text="Django session key")
    logout_timestamp = models.DateTimeField(null=True, blank=True, help_text="When the user logged out")

    class Meta:
        ordering = ['-login_timestamp']
        indexes = [
            models.Index(fields=['login_timestamp']),
            models.Index(fields=['user', 'login_timestamp']),
            models.Index(fields=['status']),
        ]
        verbose_name = "User Login Event"
        verbose_name_plural = "User Login Events"

    def __str__(self):
        return f"{self.user.username} - {self.status} - {self.login_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    @property
    def effective_end_time(self):
        """Returns logout_timestamp, or last activity time if idle, or None if still active"""
        if self.logout_timestamp:
            return self.logout_timestamp

        if self.status != 'success':
            return self.login_timestamp

        from datetime import timedelta
        cutoff_time = timezone.now() - timedelta(hours=2) # 2 hours idle timeout
        
        # Use pre-fetched activities
        activities = list(self.activities.all())
        last_time = activities[0].created_at if activities else self.login_timestamp
        
        if last_time < cutoff_time:
            return last_time # Session went idle organically
            
        return None

    @property
    def session_duration(self):
        """Calculate session duration"""
        end_time = self.effective_end_time or timezone.now()
        return end_time - self.login_timestamp

    @property
    def session_duration_formatted(self):
        """Return formatted session duration string"""
        end_time = self.effective_end_time
        
        if end_time:
            duration = end_time - self.login_timestamp
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return None

    @property
    def is_active_session(self):
        """Check if session is still active (recent activity within 2h and no logout)"""
        return self.status == 'success' and self.effective_end_time is None

    @property
    def activities_count(self):
        """Get count of activities during this session"""
        return self.activities.count() if hasattr(self, 'activities') else 0

    def get_session_activities(self):
        """Get all activities that occurred during this login session"""
        if hasattr(self, 'activities'):
            return self.activities.all()
        return []


class LoginAttemptTracker(models.Model):
    """
    Tracks login attempts for rate limiting and account lockout.
    Implements brute-force protection.
    """
    ip_address = models.GenericIPAddressField(db_index=True)
    username = models.CharField(max_length=150, db_index=True)
    attempt_time = models.DateTimeField(default=timezone.now, db_index=True)
    was_successful = models.BooleanField(default=False)

    class Meta:
        ordering = ['-attempt_time']
        indexes = [
            models.Index(fields=['ip_address', 'attempt_time']),
            models.Index(fields=['username', 'attempt_time']),
        ]
        verbose_name = "Login Attempt"
        verbose_name_plural = "Login Attempts"

    def __str__(self):
        status = "Success" if self.was_successful else "Failed"
        return f"{self.username} from {self.ip_address} - {status} at {self.attempt_time}"

    @classmethod
    def get_recent_failed_attempts(cls, ip_address=None, username=None, minutes=15):
        """Get count of failed attempts in the last N minutes."""
        cutoff_time = timezone.now() - timezone.timedelta(minutes=minutes)
        queryset = cls.objects.filter(
            attempt_time__gte=cutoff_time,
            was_successful=False
        )
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        if username:
            queryset = queryset.filter(username=username)
        return queryset.count()

    @classmethod
    def cleanup_old_attempts(cls, hours=24):
        """Remove attempts older than N hours."""
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        deleted, _ = cls.objects.filter(attempt_time__lt=cutoff_time).delete()
        return deleted


class AccountLockout(models.Model):
    """
    Tracks account lockouts after too many failed login attempts.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    username = models.CharField(max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    locked_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField()
    reason = models.CharField(max_length=255, default="Too many failed login attempts")
    failed_attempts = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Is this lockout still in effect?")

    class Meta:
        ordering = ['-locked_at']
        indexes = [
            models.Index(fields=['username', 'is_active']),
            models.Index(fields=['ip_address', 'is_active']),
        ]
        verbose_name = "Account Lockout"
        verbose_name_plural = "Account Lockouts"

    def __str__(self):
        return f"{self.username} locked until {self.locked_until}"

    @property
    def is_locked(self):
        """Check if lockout is still in effect."""
        if not self.is_active:
            return False
        if timezone.now() >= self.locked_until:
            self.is_active = False
            self.save(update_fields=['is_active'])
            return False
        return True

    @property
    def time_remaining(self):
        """Get remaining lockout time in seconds."""
        if not self.is_locked:
            return 0
        return max(0, int((self.locked_until - timezone.now()).total_seconds()))

    @property
    def time_remaining_formatted(self):
        """Get human-readable remaining time."""
        seconds = self.time_remaining
        if seconds <= 0:
            return "Unlocked"
        minutes, secs = divmod(seconds, 60)
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    @classmethod
    def is_account_locked(cls, username=None, ip_address=None):
        """Check if account or IP is currently locked."""
        now = timezone.now()
        queryset = cls.objects.filter(is_active=True, locked_until__gt=now)

        if username:
            lockout = queryset.filter(username=username).first()
            if lockout:
                return True, lockout

        if ip_address:
            lockout = queryset.filter(ip_address=ip_address).first()
            if lockout:
                return True, lockout

        return False, None

    @classmethod
    def create_lockout(cls, username, ip_address, failed_attempts, lockout_minutes=15):
        """Create a new lockout record."""
        user = None
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            pass

        lockout = cls.objects.create(
            user=user,
            username=username,
            ip_address=ip_address,
            locked_until=timezone.now() + timezone.timedelta(minutes=lockout_minutes),
            failed_attempts=failed_attempts
        )
        return lockout


class TwoFactorAuth(models.Model):
    """
    Two-Factor Authentication settings for admin accounts.
    Uses TOTP (Time-based One-Time Password).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='two_factor')
    secret_key = models.CharField(max_length=32, help_text="Base32 encoded secret key")
    is_enabled = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, help_text="Has the user verified their 2FA setup?")
    backup_codes = models.TextField(blank=True, help_text="JSON list of backup codes")
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Two-Factor Authentication"
        verbose_name_plural = "Two-Factor Authentications"

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.user.username} - 2FA {status}"

    def generate_secret(self):
        """Generate a new secret key."""
        import secrets
        import base64
        # Generate 20 random bytes and encode as base32
        random_bytes = secrets.token_bytes(20)
        self.secret_key = base64.b32encode(random_bytes).decode('utf-8')
        return self.secret_key

    def get_totp_uri(self):
        """Generate TOTP URI for QR code."""
        return f"otpauth://totp/Waterworks:{self.user.username}?secret={self.secret_key}&issuer=Balilihan%20Waterworks"

    def verify_token(self, token):
        """Verify a TOTP token."""
        import hmac
        import struct
        import time
        import base64
        import hashlib

        try:
            token = int(token)
        except (ValueError, TypeError):
            return False

        # Get current time step (30-second intervals)
        current_time = int(time.time())

        # Check current and adjacent time windows for clock drift
        for time_offset in [-1, 0, 1]:
            time_step = (current_time // 30) + time_offset
            expected_token = self._generate_totp(time_step)
            if token == expected_token:
                self.last_used_at = timezone.now()
                self.save(update_fields=['last_used_at'])
                return True
        return False

    def _generate_totp(self, time_step):
        """Generate TOTP for a given time step."""
        import hmac
        import struct
        import base64
        import hashlib

        key = base64.b32decode(self.secret_key, casefold=True)
        msg = struct.pack('>Q', time_step)
        hmac_hash = hmac.new(key, msg, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0f
        code = struct.unpack('>I', hmac_hash[offset:offset + 4])[0]
        code = (code & 0x7fffffff) % 1000000
        return code

    def generate_backup_codes(self, count=8):
        """Generate backup codes for account recovery."""
        import secrets
        import json
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        self.backup_codes = json.dumps(codes)
        self.save(update_fields=['backup_codes'])
        return codes

    def verify_backup_code(self, code):
        """Verify and consume a backup code."""
        import json
        if not self.backup_codes:
            return False

        codes = json.loads(self.backup_codes)
        code = code.upper().replace('-', '').replace(' ', '')

        if code in codes:
            codes.remove(code)
            self.backup_codes = json.dumps(codes)
            self.save(update_fields=['backup_codes'])
            return True
        return False

    @property
    def remaining_backup_codes(self):
        """Get count of remaining backup codes."""
        import json
        if not self.backup_codes:
            return 0
        return len(json.loads(self.backup_codes))


class PasswordResetToken(models.Model):
    """
    Stores password reset tokens for secure password recovery.
    Tokens expire after 24 hours for security.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"

    def __str__(self):
        return f"{self.user.username} - {self.token[:10]}... - {'Used' if self.is_used else 'Active'}"

    def is_valid(self):
        """Check if token is still valid (not expired and not used)"""
        return not self.is_used and timezone.now() < self.expires_at

    def save(self, *args, **kwargs):
        if not self.pk:  # Only set expires_at on creation
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        if not self.token:
            self.token = uuid.uuid4().hex
        super().save(*args, **kwargs)


class UserActivity(models.Model):
    """
    Tracks important user activities for audit and security purposes.
    """
    ACTION_CHOICES = [
        ('password_reset_requested', 'Password Reset Requested'),
        ('password_reset_completed', 'Password Reset Completed'),
        ('password_changed', 'Password Changed'),
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('bill_created', 'Bill Created'),
        ('payment_processed', 'Payment Processed'),
        ('meter_reading_confirmed', 'Meter Reading Confirmed'),
        ('meter_reading_submitted', 'Meter Reading Submitted'),
        ('consumer_created', 'Consumer Created'),
        ('consumer_updated', 'Consumer Updated'),
        ('consumer_disconnected', 'Consumer Disconnected'),
        ('consumer_reconnected', 'Consumer Reconnected'),
        ('system_settings_updated', 'System Settings Updated'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='targeted_activities')
    login_event = models.ForeignKey('UserLoginEvent', on_delete=models.SET_NULL, null=True, blank=True, related_name='activities', help_text="The login session during which this activity occurred")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"

    def __str__(self):
        return f"{self.user.username if self.user else 'System'} - {self.get_action_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class StaffProfile(models.Model):
    """
    Staff Profile with Role-Based Access Control
    Supports 3 distinct roles: Superadmin, Cashier, Field Staff

    Access Levels:
    - Superadmin: Full access to all features
    - Cashier: Dashboard, Consumers, Bill Inquiry, Payment History, Meter Readings, Reports
    - Field Staff: Assigned barangay meter readings only
    """
    ROLE_CHOICES = [
        ('superadmin', 'Superadmin'),
        ('admin', 'Admin'),
        ('cashier', 'Cashier'),
        ('field_staff', 'Field Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    assigned_barangay = models.ForeignKey(
        'Barangay',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Required for Field Staff only"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='field_staff',
        help_text="User role determines dashboard access and permissions"
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        null=True,
        blank=True,
        help_text="Profile photo for admin users"
    )

    def __str__(self):
        if self.assigned_barangay:
            return f"{self.user.username} ({self.get_role_display()}) - {self.assigned_barangay.name}"
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def role_display(self):
        """Return a short display name for the role"""
        role_map = {
            'superadmin': 'Superadmin',
            'admin': 'Admin',
            'cashier': 'Cashier',
            'field_staff': 'Field Staff',
        }
        return role_map.get(self.role, 'Staff')

    @property
    def is_superadmin(self):
        """Check if user is superadmin"""
        return self.role == 'superadmin'

    @property
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'

    @property
    def is_cashier(self):
        """Check if user is cashier"""
        return self.role == 'cashier'

    @property
    def is_field_staff(self):
        """Check if user is field staff"""
        return self.role == 'field_staff'

    def has_permission(self, permission):
        """Check if user has specific permission based on role"""
        permissions = {
            'superadmin': ['all'],
            'admin': ['view_dashboard', 'view_consumers', 'view_bills', 'view_readings',
                      'view_reports', 'view_payments'],
            'cashier': ['view_dashboard', 'view_consumers', 'view_bills', 'accept_payment',
                       'view_payments', 'view_readings', 'view_reports', 'print_receipt'],
            'field_staff': ['view_assigned_consumers', 'submit_reading', 'view_own_readings'],
        }

        role_perms = permissions.get(self.role, [])
        return 'all' in role_perms or permission in role_perms

# ----------------------------
# Choice Fields
# ----------------------------
GENDER_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other'),
]

CIVIL_STATUS_CHOICES = [
    ('Single', 'Single'),
    ('Married', 'Married'),
    ('Widowed', 'Widowed'),
    ('Divorced', 'Divorced'),
]

USAGE_TYPE_CHOICES = [
    ('Residential', 'Residential'),
    ('Commercial', 'Commercial'),
]

STATUS_CHOICES = [
    ('active', 'Connected'),
    ('disconnected', 'Disconnected'),
]

BILL_STATUS_CHOICES = [
    ('Pending', 'Pending'),
    ('Paid', 'Paid'),
    ('Overdue', 'Overdue'),
]

# ----------------------------
# Dynamic Reference Models
# ----------------------------
class Barangay(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Purok(models.Model):
    name = models.CharField(max_length=100)
    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE, related_name='puroks')

    def __str__(self):
        return f"{self.name} ({self.barangay.name})"


class MeterBrand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# consumers/models.py (Relevant part updated)
from django.db import models
# ... (your other imports) ...

# ----------------------------
# Main Consumer Model
# ----------------------------
class Consumer(models.Model):
    # Suffix choices for name
    SUFFIX_CHOICES = [
        ('', 'None'),
        ('Jr.', 'Jr.'),
        ('Sr.', 'Sr.'),
        ('II', 'II'),
        ('III', 'III'),
        ('IV', 'IV'),
        ('V', 'V'),
    ]

    # Personal Information
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    suffix = models.CharField(max_length=10, choices=SUFFIX_CHOICES, blank=True, default='')
    birth_date = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    phone_number = models.CharField(max_length=15)

    # Household Information
    civil_status = models.CharField(max_length=10, choices=CIVIL_STATUS_CHOICES)
    spouse_name = models.CharField(max_length=50, blank=True, null=True)
    barangay = models.ForeignKey(Barangay, on_delete=models.SET_NULL, null=True)
    purok = models.ForeignKey(Purok, on_delete=models.SET_NULL, null=True)
    household_number = models.CharField(max_length=20)

    # Water Meter Information
    usage_type = models.CharField(max_length=20, choices=USAGE_TYPE_CHOICES)
    meter_brand = models.ForeignKey(MeterBrand, on_delete=models.SET_NULL, null=True)
    serial_number = models.CharField(max_length=50)
    first_reading = models.IntegerField()
    registration_date = models.DateField()

    # 🔑 ID Number (Primary Identifier) - Format: YYYYMMXXXX (e.g., 2025120001)
    id_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    # Status & Disconnection
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Connected or Disconnected consumer"
    )
    disconnect_reason = models.CharField(max_length=200, blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ========================
    # Properties
    # ========================
    @property
    def is_senior_citizen(self):
        """Check if consumer is 60+ years old (senior citizen)."""
        from datetime import date
        today = date.today()
        age = today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
        return age >= 60

    @property
    def full_name(self):
        """Returns the full name with optional middle name and suffix."""
        middle = f" {self.middle_name}" if self.middle_name else ""
        suffix = f" {self.suffix}" if self.suffix else ""
        return f"{self.first_name}{middle} {self.last_name}{suffix}".strip()

    @property
    def is_delinquent(self):
        """Check if consumer has overdue unpaid bills."""
        from django.utils import timezone
        return self.bills.filter(
            status='Pending',
            due_date__lt=timezone.now().date()
        ).exists()

    @property
    def pending_bills_count(self):
        """Count of pending bills for this consumer."""
        return self.bills.filter(status='Pending').count()

    @property
    def overdue_bills_count(self):
        """Count of overdue unpaid bills."""
        from django.utils import timezone
        return self.bills.filter(
            status='Pending',
            due_date__lt=timezone.now().date()
        ).count()

    # ========================
    # Methods
    # ========================
    @classmethod
    def get_next_id_number(cls, prefix=None):
        """
        Calculate the next available ID number for a given prefix (YYYYMM).
        Optimized to use database indexing.
        """
        from datetime import datetime
        if not prefix:
            prefix = datetime.now().strftime('%Y%m')

        # Get the highest ID number for this prefix using the index
        last_consumer = cls.objects.filter(id_number__startswith=prefix).order_by('-id_number').first()

        if last_consumer and last_consumer.id_number:
            try:
                # Extract the last 4 digits
                last_seq = int(last_consumer.id_number[-4:])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1

        if new_seq > 9999:
            raise ValueError(f"ID number limit reached for prefix {prefix} (max 9999)")

        return f"{prefix}{new_seq:04d}"

    def save(self, *args, **kwargs):
        # Auto-generate ID Number if not set
        if not self.id_number:
            from django.db import transaction
            # Using select_for_update to handle concurrency during sequential saves
            with transaction.atomic():
                self.id_number = self.get_next_id_number()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id_number} - {self.full_name}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='consumer_status_idx'),
            models.Index(fields=['barangay', 'status'], name='consumer_brgy_status_idx'),
        ]
        permissions = [
            # Consumer Management Permissions
            ("view_consumer_data", "Can view consumer data (read-only)"),
            ("edit_consumer_data", "Can edit consumer information"),
            ("create_consumer_account", "Can create new consumers"),
            ("remove_consumer", "Can delete/remove consumers"),
            ("disconnect_consumer", "Can disconnect/reconnect consumers"),

            # Billing Permissions
            ("manage_billing", "Can manage billing (create bills, process payments)"),
            ("view_billing", "Can view billing records"),

            # Reports Permissions
            ("generate_reports", "Can generate and download reports"),
            ("view_reports", "Can view reports"),

            # User Management Permissions
            ("manage_users", "Can manage user accounts"),

            # System Settings Permissions
            ("manage_settings", "Can access system settings"),
        ]

# ----------------------------
# Meter Reading Model
# ----------------------------
class MeterReading(models.Model):
    """
    Stores meter readings from Smart Meter Reader app or office entry.

    FLOW:
    - App OCR Scan: source='app_scanned', is_confirmed=True (auto-confirm, OCR reads meter)
    - App Manual Entry: source='app_manual', is_confirmed=False (needs admin review, has proof photo)
    - Office Manual: source='manual', is_confirmed=True (trusted, web dashboard entry)
    """
    SOURCE_CHOICES = [
        ('app_scanned', 'App - OCR Scan'),
        ('app_manual', 'App - Manual Entry'),
        ('manual', 'Office Manual Entry'),
    ]

    consumer = models.ForeignKey(
        Consumer,
        on_delete=models.CASCADE,
        related_name='meter_readings'
    )
    reading_date = models.DateField()
    reading_value = models.IntegerField(help_text="Cumulative meter value")
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)

    # -------------------------
    # PROOF IMAGE (for manual readings)
    # -------------------------
    proof_image_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Cloudinary URL of meter photo proof"
    )

    # -------------------------
    # CONFIRMATION STATUS
    # -------------------------
    is_confirmed = models.BooleanField(default=False, help_text="Has admin confirmed this reading?")
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_readings',
        help_text="Admin who confirmed this reading"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    # -------------------------
    # REJECTION STATUS
    # -------------------------
    is_rejected = models.BooleanField(default=False, help_text="Was this reading rejected?")
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_readings',
        help_text="Admin who rejected this reading"
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for rejection (required when rejecting)"
    )

    # -------------------------
    # FIELD STAFF INFO
    # -------------------------
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_readings',
        help_text="Field staff who submitted this reading"
    )

    class Meta:
        ordering = ['-reading_date', '-created_at']
        indexes = [
            models.Index(fields=['consumer', 'is_confirmed'], name='reading_consumer_conf_idx'),
            models.Index(fields=['reading_date'], name='reading_date_idx'),
            models.Index(fields=['consumer', 'is_confirmed', '-reading_date'], name='reading_latest_idx'),
            models.Index(fields=['is_confirmed', 'is_rejected'], name='reading_status_idx'),
        ]

    def __str__(self):
        status = "✓" if self.is_confirmed else ("✗" if self.is_rejected else "?")
        return f"{self.consumer} - {self.reading_value} on {self.reading_date} [{status}]"

    @property
    def needs_confirmation(self):
        """Check if this reading needs admin confirmation"""
        return not self.is_confirmed and not self.is_rejected and self.source == 'manual_with_proof'

    @property
    def status_display(self):
        """Human-readable status"""
        if self.is_confirmed:
            return "Confirmed"
        elif self.is_rejected:
            return "Rejected"
        else:
            return "Pending Review"


# ----------------------------
# Bill Model (Final Version)
# ----------------------------
class Bill(models.Model):
    consumer = models.ForeignKey(
        Consumer,
        on_delete=models.CASCADE,
        related_name='bills'
    )

    previous_reading = models.ForeignKey(
        'MeterReading',
        on_delete=models.PROTECT,
        related_name='bills_as_previous',
        null=True,
        blank=True,
        help_text="The meter reading from the previous billing cycle"
    )

    current_reading = models.ForeignKey(
        'MeterReading',
        on_delete=models.PROTECT,
        related_name='bills_as_current',
        help_text="The latest meter reading used for this bill"
    )

    billing_period = models.DateField(help_text="First day of the billing month (e.g., 2025-10-01)")
    due_date = models.DateField()

    consumption = models.PositiveIntegerField(help_text="in cubic meters")

    # -------------------------
    # TIERED RATE BREAKDOWN
    # -------------------------
    # Tier 1: 1-5 m³ (minimum charge)
    tier1_consumption = models.PositiveIntegerField(default=0, help_text="Units in Tier 1 (1-5 m³)")
    tier1_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Minimum charge amount")

    # Tier 2: 6-10 m³
    tier2_consumption = models.PositiveIntegerField(default=0, help_text="Units in Tier 2 (6-10 m³)")
    tier2_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), help_text="Rate per m³ for Tier 2")
    tier2_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Tier 3: 11-20 m³
    tier3_consumption = models.PositiveIntegerField(default=0, help_text="Units in Tier 3 (11-20 m³)")
    tier3_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), help_text="Rate per m³ for Tier 3")
    tier3_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Tier 4: 21-50 m³
    tier4_consumption = models.PositiveIntegerField(default=0, help_text="Units in Tier 4 (21-50 m³)")
    tier4_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), help_text="Rate per m³ for Tier 4")
    tier4_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Tier 5: 51+ m³
    tier5_consumption = models.PositiveIntegerField(default=0, help_text="Units in Tier 5 (51+ m³)")
    tier5_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), help_text="Rate per m³ for Tier 5")
    tier5_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Legacy fields (kept for backward compatibility)
    rate_per_cubic = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), help_text="Average rate (for display only)")
    fixed_charge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text="Deprecated - use tier1_amount for minimum charge")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # -------------------------
    # PENALTY TRACKING FIELDS
    # -------------------------
    penalty_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated penalty amount for late payment"
    )
    penalty_applied_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when penalty was first applied"
    )
    penalty_waived = models.BooleanField(
        default=False,
        help_text="Whether the penalty has been waived by admin"
    )
    penalty_waived_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='waived_penalties',
        help_text="Admin who waived the penalty"
    )
    penalty_waived_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for waiving the penalty"
    )
    penalty_waived_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when penalty was waived"
    )
    days_overdue = models.IntegerField(
        default=0,
        help_text="Number of days the bill is/was overdue"
    )
    senior_citizen_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="5% discount on water bill for senior citizens with consumption ≤ 30 m³"
    )

    status = models.CharField(
        max_length=20,
        choices=BILL_STATUS_CHOICES,
        default='Pending'
    )

    queued_for_payment = models.BooleanField(
        default=False,
        help_text="True if Inquire office selected this for payment"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-billing_period']
        indexes = [
            models.Index(fields=['consumer', 'status'], name='bill_consumer_status_idx'),
            models.Index(fields=['due_date'], name='bill_due_date_idx'),
            models.Index(fields=['status', 'due_date'], name='bill_status_due_idx'),
        ]
        verbose_name = "Utility Bill"
        verbose_name_plural = "Utility Bills"

    @property
    def is_overdue(self):
        """Check if bill is overdue (past due date and not paid)"""
        if self.status == 'Paid':
            return False
        return timezone.now().date() > self.due_date

    @property
    def current_days_overdue(self):
        """Calculate current days overdue"""
        if self.status == 'Paid' or not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    @property
    def effective_penalty(self):
        """Return the effective penalty (0 if waived). SC discount does NOT apply to penalty."""
        if self.penalty_waived:
            return Decimal('0.00')
        return self.penalty_amount

    @property
    def total_amount_due(self):
        """Total amount due = (water bill - SC discount) + penalty"""
        discounted_bill = self.total_amount - self.senior_citizen_discount
        return discounted_bill + self.effective_penalty

    def __str__(self):
        penalty_str = f" + ₱{self.penalty_amount} penalty" if self.penalty_amount > 0 and not self.penalty_waived else ""
        return f"Bill for {self.consumer} | {self.billing_period.strftime('%B %Y')} | ₱{self.total_amount}{penalty_str} ({self.status})"


# ----------------------------
# consumers/models.py
from django.db import models
from decimal import Decimal # Import Decimal

# ... (other imports remain the same) ...

# ============================================================================
# SYSTEM SETTINGS MODEL (Singleton)
# ============================================================================
# Configures billing rates, reading schedule, and billing cycle.
#
# BILLING WORKFLOW:
# 1. Reading Period: Field staff submit readings (reading_start_day to reading_end_day)
# 2. Admin Confirmation: Admin reviews and confirms readings
# 3. Bill Generation: Bill created instantly when reading is confirmed
# 4. Payment Due: Consumer pays before due_day_of_month
#
# FOR TESTING: You can test the full flow anytime - bills are generated
# instantly when admin confirms a reading, regardless of schedule settings.
# ============================================================================
class SystemSetting(models.Model):
    """
    System-wide configuration for water rates, reading schedule, billing, and penalties.

    The schedule fields help organize the monthly billing cycle:
    - Reading period: When field staff should submit meter readings
    - Billing period: The billing cycle start date shown on bills
    - Due date: Payment deadline shown on bills
    - Penalty: Late payment charges applied after due date

    Bills are created INSTANTLY when admin confirms a reading.

    TIERED RATE STRUCTURE:
    - Tier 1 (1-5 m³): Minimum charge (flat rate)
    - Tier 2 (6-10 m³): Rate per cubic meter
    - Tier 3 (11-20 m³): Rate per cubic meter
    - Tier 4 (21-50 m³): Rate per cubic meter
    - Tier 5 (51+ m³): Rate per cubic meter
    """
    # -------------------------
    # RESIDENTIAL TIERED RATES
    # -------------------------
    # Tier 1: 1-5 cubic meters (minimum charge)
    residential_minimum_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('75.00'),
        help_text="Minimum charge for 1-5 m³ consumption (₱)"
    )
    # Tier 2: 6-10 cubic meters
    residential_tier2_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('15.00'),
        help_text="Rate for 6-10 m³ consumption (₱/m³)"
    )
    # Tier 3: 11-20 cubic meters
    residential_tier3_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('16.00'),
        help_text="Rate for 11-20 m³ consumption (₱/m³)"
    )
    # Tier 4: 21-50 cubic meters
    residential_tier4_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('17.00'),
        help_text="Rate for 21-50 m³ consumption (₱/m³)"
    )
    # Tier 5: 51+ cubic meters
    residential_tier5_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Rate for 51+ m³ consumption (₱/m³)"
    )

    # -------------------------
    # COMMERCIAL TIERED RATES
    # -------------------------
    # Tier 1: 1-5 cubic meters (minimum charge)
    commercial_minimum_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('100.00'),
        help_text="Minimum charge for 1-5 m³ consumption (₱)"
    )
    # Tier 2: 6-10 cubic meters
    commercial_tier2_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('18.00'),
        help_text="Rate for 6-10 m³ consumption (₱/m³)"
    )
    # Tier 3: 11-20 cubic meters
    commercial_tier3_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('20.00'),
        help_text="Rate for 11-20 m³ consumption (₱/m³)"
    )
    # Tier 4: 21-50 cubic meters
    commercial_tier4_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('22.00'),
        help_text="Rate for 21-50 m³ consumption (₱/m³)"
    )
    # Tier 5: 51+ cubic meters
    commercial_tier5_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('30.00'),
        help_text="Rate for 51+ m³ consumption (₱/m³)"
    )

    # Legacy fields (kept for backward compatibility, not used in new calculation)
    residential_rate_per_cubic = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('22.50'),
        help_text="[LEGACY] Rate for residential consumers (₱ / m³)"
    )
    commercial_rate_per_cubic = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('25.00'),
        help_text="[LEGACY] Rate for commercial consumers (₱ / m³)"
    )
    fixed_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="[LEGACY] Fixed charge - no longer used with tiered rates"
    )

    # -------------------------
    # READING SCHEDULE
    # -------------------------
    # Defines the window when field staff should submit meter readings
    reading_start_day = models.IntegerField(
        default=1,
        help_text="Day of month when reading period starts (1-28)"
    )
    reading_end_day = models.IntegerField(
        default=10,
        help_text="Day of month when reading period ends (1-28)"
    )

    # -------------------------
    # BILLING SCHEDULE
    # -------------------------
    # These affect the dates displayed on generated bills
    billing_day_of_month = models.IntegerField(
        default=1,
        help_text="Day shown as billing period start on bills (1-28)"
    )
    due_day_of_month = models.IntegerField(
        default=20,
        help_text="Day when payment is due (1-28)"
    )

    # -------------------------
    # PENALTY SETTINGS
    # -------------------------
    PENALTY_TYPE_CHOICES = [
        ('percentage', 'Percentage of Bill'),
        ('fixed', 'Fixed Amount'),
    ]

    penalty_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable late payment penalties"
    )
    penalty_type = models.CharField(
        max_length=20,
        choices=PENALTY_TYPE_CHOICES,
        default='percentage',
        help_text="Type of penalty calculation"
    )
    penalty_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('25.00'),
        help_text="Penalty rate in percentage (default: 25% of bill amount)"
    )
    fixed_penalty_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Fixed penalty amount in pesos (used if penalty_type is 'fixed')"
    )
    penalty_grace_period_days = models.IntegerField(
        default=0,
        help_text="Number of days after due date before penalty is applied (0 = immediate, penalty starts day after due date)"
    )
    max_penalty_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Maximum penalty cap (0 = no cap, penalty is full percentage of bill)"
    )

    # -------------------------
    # METADATA
    # -------------------------
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rates: Res ₱{self.residential_minimum_charge} min, Comm ₱{self.commercial_minimum_charge} min | Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else 'Never'}"

    # Optional: Override save to enforce singleton pattern (only one instance)
    def save(self, *args, **kwargs):
        # Ensure only one instance exists by deleting others before saving
        self.__class__.objects.exclude(id=self.id).delete()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"


# ============================================================================
# SYSTEM SETTINGS CHANGE LOG - Track all changes to system settings
# ============================================================================
class SystemSettingChangeLog(models.Model):
    """
    Tracks changes to system settings for audit purposes.
    Records who changed what and when, with before/after values.

    Changes take effect IMMEDIATELY:
    - Reading schedule: Affects mobile app display immediately
    - Billing schedule: Affects newly generated bills
    - Tiered rates: Affects newly generated bills
    - Penalty settings: Affects penalty calculations on existing and new bills
    """
    CHANGE_TYPES = [
        ('reading_schedule', 'Reading Schedule'),
        ('billing_schedule', 'Billing Schedule'),
        ('residential_rates', 'Residential Rates'),
        ('commercial_rates', 'Commercial Rates'),
        ('penalty_settings', 'Penalty Settings'),
        ('multiple', 'Multiple Settings'),
    ]

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settings_changes',
        help_text="User who made the change"
    )
    changed_at = models.DateTimeField(default=timezone.now, db_index=True)
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPES, default='multiple')

    # Summary of changes
    description = models.TextField(help_text="Human-readable description of changes")

    # Store the actual values that were changed (JSON format)
    previous_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Previous settings values (JSON)"
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="New settings values (JSON)"
    )

    # When changes take effect
    effective_immediately = models.BooleanField(
        default=True,
        help_text="All changes take effect immediately"
    )

    # IP address for security audit
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Settings Change Log"
        verbose_name_plural = "Settings Change Logs"
        indexes = [
            models.Index(fields=['-changed_at']),
            models.Index(fields=['change_type', '-changed_at']),
        ]

    def __str__(self):
        user_str = self.changed_by.username if self.changed_by else "System"
        return f"{self.get_change_type_display()} by {user_str} at {self.changed_at.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log_change(cls, user, change_type, description, previous_values, new_values, ip_address=None):
        """
        Create a new change log entry.

        Args:
            user: User who made the change
            change_type: Type of change (from CHANGE_TYPES)
            description: Human-readable description
            previous_values: Dict of previous settings
            new_values: Dict of new settings
            ip_address: IP address of user
        """
        return cls.objects.create(
            changed_by=user,
            change_type=change_type,
            description=description,
            previous_values=previous_values,
            new_values=new_values,
            ip_address=ip_address,
            effective_immediately=True
        )


# ... (rest of your models like Consumer, Barangay, etc.) ...
    
    
class Payment(models.Model):
    bill = models.ForeignKey(
        'Bill',
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="The bill being paid"
    )
    # -------------------------
    # ORIGINAL BILL AMOUNT
    # -------------------------
    original_bill_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Original bill amount before penalty"
    )
    # -------------------------
    # PENALTY INFORMATION
    # -------------------------
    penalty_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Penalty amount included in this payment"
    )
    penalty_waived = models.BooleanField(
        default=False,
        help_text="Whether penalty was waived for this payment"
    )
    days_overdue_at_payment = models.IntegerField(
        default=0,
        help_text="Number of days overdue at the time of payment"
    )
    senior_citizen_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Senior citizen discount applied on penalty"
    )
    # -------------------------
    # PAYMENT AMOUNTS
    # -------------------------
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount paid (bill + penalty)"
    )
    received_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Cash amount received from the consumer"
    )
    change = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Change to return to the consumer"
    )
    or_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Official Receipt number (auto-generated)"
    )
    payment_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time of payment"
    )
    # -------------------------
    # PAYMENT PROCESSING INFO
    # -------------------------
    processed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payments',
        help_text="Staff who processed the payment"
    )
    remarks = models.TextField(
        blank=True,
        help_text="Additional notes or remarks about the payment"
    )

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['payment_date'], name='payment_date_idx'),
            models.Index(fields=['bill'], name='payment_bill_idx'),
        ]

    def clean(self):
        """Validate business logic before saving."""
        if self.received_amount < self.amount_paid:
            raise ValidationError("Received amount cannot be less than the amount due.")

    def save(self, *args, **kwargs):
        # Auto-compute change
        self.change = self.received_amount - self.amount_paid

        # Auto-generate OR number if not set (e.g., during initial save)
        if not self.or_number:
            date_str = timezone.now().strftime('%Y%m%d')
            unique_suffix = uuid.uuid4().hex[:6].upper()
            self.or_number = f"OR-{date_str}-{unique_suffix}"

        # Run full validation
        self.full_clean()

        super().save(*args, **kwargs)

    @property
    def total_with_penalty(self):
        """Total amount including any penalty"""
        return self.original_bill_amount + self.penalty_amount

    @property
    def amount_in_words(self):
        """Convert amount_paid to words (e.g., 'ONE HUNDRED TWENTY PESOS AND 50/100')."""
        try:
            amount = self.amount_paid
            pesos = int(amount)
            centavos = round((amount - pesos) * 100)

            ones = ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE',
                    'TEN', 'ELEVEN', 'TWELVE', 'THIRTEEN', 'FOURTEEN', 'FIFTEEN', 'SIXTEEN',
                    'SEVENTEEN', 'EIGHTEEN', 'NINETEEN']
            tens = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY']

            def say(n):
                if n == 0:
                    return ''
                elif n < 20:
                    return ones[n]
                elif n < 100:
                    return tens[n // 10] + (f' {ones[n % 10]}' if n % 10 else '')
                elif n < 1000:
                    rest = say(n % 100)
                    return ones[n // 100] + ' HUNDRED' + (f' AND {rest}' if rest else '')
                elif n < 1000000:
                    rest = say(n % 1000)
                    return say(n // 1000) + ' THOUSAND' + (f' {rest}' if rest else '')
                else:
                    rest = say(n % 1000000)
                    return say(n // 1000000) + ' MILLION' + (f' {rest}' if rest else '')

            peso_words = say(pesos) or 'ZERO'
            return f"{peso_words} PESOS AND {centavos:02d}/100"
        except Exception:
            return ''

    def __str__(self):
        penalty_info = f" (incl. ₱{self.penalty_amount} penalty)" if self.penalty_amount > 0 else ""
        return f"OR#{self.or_number} - {self.bill.consumer.id_number}{penalty_info}"


# ============================================================================
# NOTIFICATION MODEL - For real-time notifications in header dropdown
# ============================================================================
class Notification(models.Model):
    """
    Stores system notifications for admin/superuser users.
    Used for meter reading alerts, payment notifications, etc.
    """
    NOTIFICATION_TYPES = [
        ('meter_reading', 'Meter Reading Submitted'),
        ('reading_pending_confirmation', 'Reading Pending Confirmation'),
        ('payment', 'Payment Processed'),
        ('bill_generated', 'Bill Generated'),
        ('consumer_registered', 'New Consumer Registered'),
        ('system_alert', 'System Alert'),
    ]

    # Who should see this notification (null = all admins/superusers)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                           help_text="Specific user to notify (null = all admins)")

    # Notification details
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES,
                                       help_text="Type of notification")
    title = models.CharField(max_length=200, help_text="Short notification title")
    message = models.TextField(help_text="Notification message")

    # Related object (for redirects)
    related_object_id = models.IntegerField(null=True, blank=True,
                                          help_text="ID of related object (e.g., MeterReading ID)")
    redirect_url = models.CharField(max_length=500, blank=True,
                                   help_text="URL to redirect when clicked")

    # Status
    is_read = models.BooleanField(default=False, help_text="Has the user read this notification?")
    is_archived = models.BooleanField(default=False, help_text="Archived after 30 days")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, help_text="When was it marked as read")
    archived_at = models.DateTimeField(null=True, blank=True, help_text="When was it archived")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['is_archived', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        user_str = self.user.username if self.user else "All Admins"
        return f"{self.title} - {user_str} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def mark_as_read(self):
        """Mark this notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()

    def archive(self):
        """Archive this notification"""
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = timezone.now()
            self.save()

    @property
    def is_older_than_30_days(self):
        """Check if notification is older than 30 days"""
        from datetime import timedelta
        return timezone.now() - self.created_at > timedelta(days=30)

    @property
    def time_ago(self):
        """Human-readable time ago string"""
        from django.utils.timesince import timesince
        return timesince(self.created_at)

    @classmethod
    def archive_old_notifications(cls):
        """Archive all notifications older than 30 days"""
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=30)
        old_notifications = cls.objects.filter(
            created_at__lt=cutoff_date,
            is_archived=False
        )
        count = old_notifications.update(is_archived=True, archived_at=timezone.now())
        return count

    @classmethod
    def get_active_notifications(cls, user=None):
        """Get non-archived notifications for display"""
        queryset = cls.objects.filter(is_archived=False)
        if user:
            queryset = queryset.filter(models.Q(user=user) | models.Q(user__isnull=True))
        return queryset.order_by('-created_at')
