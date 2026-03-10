# consumers/utils.py
"""
Utility functions for the Balilihan Waterworks Management System.
Contains penalty calculations, bill processing helpers, tiered rate calculations, and other utilities.
"""

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from typing import Tuple, Optional, Dict


def calculate_tiered_water_bill(consumption: int, usage_type: str, settings=None) -> Tuple[Decimal, Decimal, Dict]:
    """
    Calculate water bill using tiered rate structure.

    TIERED RATE STRUCTURE:
    - Tier 1 (1-5 m³): Minimum charge (flat rate)
    - Tier 2 (6-10 m³): Rate per cubic meter for units 6-10
    - Tier 3 (11-20 m³): Rate per cubic meter for units 11-20
    - Tier 4 (21-50 m³): Rate per cubic meter for units 21-50
    - Tier 5 (51+ m³): Rate per cubic meter for units 51+

    The billing is CUMULATIVE - each tier adds to the total.
    Example: 25 m³ consumption
    - Tier 1 (1-5): Minimum charge = ₱75 (Residential)
    - Tier 2 (6-10): 5 units × ₱15 = ₱75
    - Tier 3 (11-20): 10 units × ₱16 = ₱160
    - Tier 4 (21-25): 5 units × ₱17 = ₱85
    - Total = ₱395

    Args:
        consumption: Water consumption in cubic meters
        usage_type: 'Residential' or 'Commercial'
        settings: Optional SystemSetting instance (will fetch if not provided)

    Returns:
        Tuple of (total_amount, average_rate, breakdown_dict)
        - total_amount: Total bill amount
        - average_rate: Effective average rate per cubic meter
        - breakdown_dict: Detailed breakdown of calculation
    """
    from .models import SystemSetting

    # Get system settings if not provided
    if settings is None:
        settings = SystemSetting.objects.first()

    # Set default rates based on usage type
    if usage_type == 'Commercial':
        if settings:
            minimum_charge = settings.commercial_minimum_charge
            tier2_rate = settings.commercial_tier2_rate
            tier3_rate = settings.commercial_tier3_rate
            tier4_rate = settings.commercial_tier4_rate
            tier5_rate = settings.commercial_tier5_rate
        else:
            # Default commercial rates
            minimum_charge = Decimal('100.00')
            tier2_rate = Decimal('18.00')
            tier3_rate = Decimal('20.00')
            tier4_rate = Decimal('22.00')
            tier5_rate = Decimal('24.00')
    else:  # Residential
        if settings:
            minimum_charge = settings.residential_minimum_charge
            tier2_rate = settings.residential_tier2_rate
            tier3_rate = settings.residential_tier3_rate
            tier4_rate = settings.residential_tier4_rate
            tier5_rate = settings.residential_tier5_rate
        else:
            # Default residential rates
            minimum_charge = Decimal('75.00')
            tier2_rate = Decimal('15.00')
            tier3_rate = Decimal('16.00')
            tier4_rate = Decimal('17.00')
            tier5_rate = Decimal('18.00')

    # Initialize breakdown
    breakdown = {
        'consumption': consumption,
        'usage_type': usage_type,
        'tier1_units': 0,
        'tier1_amount': Decimal('0.00'),
        'tier2_units': 0,
        'tier2_rate': tier2_rate,
        'tier2_amount': Decimal('0.00'),
        'tier3_units': 0,
        'tier3_rate': tier3_rate,
        'tier3_amount': Decimal('0.00'),
        'tier4_units': 0,
        'tier4_rate': tier4_rate,
        'tier4_amount': Decimal('0.00'),
        'tier5_units': 0,
        'tier5_rate': tier5_rate,
        'tier5_amount': Decimal('0.00'),
        'minimum_charge': minimum_charge,
    }

    total_amount = Decimal('0.00')

    if consumption <= 0:
        # Zero consumption - still charge minimum
        breakdown['tier1_units'] = 0
        breakdown['tier1_amount'] = minimum_charge
        total_amount = minimum_charge
    elif consumption <= 5:
        # Tier 1: 1-5 m³ (minimum charge only)
        breakdown['tier1_units'] = consumption
        breakdown['tier1_amount'] = minimum_charge
        total_amount = minimum_charge
    else:
        # Start with minimum charge for first 5 units
        breakdown['tier1_units'] = 5
        breakdown['tier1_amount'] = minimum_charge
        total_amount = minimum_charge

        remaining = consumption - 5

        # Tier 2: 6-10 m³ (up to 5 units at tier2_rate)
        if remaining > 0:
            tier2_units = min(remaining, 5)
            tier2_amount = Decimal(tier2_units) * tier2_rate
            breakdown['tier2_units'] = tier2_units
            breakdown['tier2_amount'] = tier2_amount
            total_amount += tier2_amount
            remaining -= tier2_units

        # Tier 3: 11-20 m³ (up to 10 units at tier3_rate)
        if remaining > 0:
            tier3_units = min(remaining, 10)
            tier3_amount = Decimal(tier3_units) * tier3_rate
            breakdown['tier3_units'] = tier3_units
            breakdown['tier3_amount'] = tier3_amount
            total_amount += tier3_amount
            remaining -= tier3_units

        # Tier 4: 21-50 m³ (up to 30 units at tier4_rate)
        if remaining > 0:
            tier4_units = min(remaining, 30)
            tier4_amount = Decimal(tier4_units) * tier4_rate
            breakdown['tier4_units'] = tier4_units
            breakdown['tier4_amount'] = tier4_amount
            total_amount += tier4_amount
            remaining -= tier4_units

        # Tier 5: 51+ m³ (all remaining at tier5_rate)
        if remaining > 0:
            tier5_units = remaining
            tier5_amount = Decimal(tier5_units) * tier5_rate
            breakdown['tier5_units'] = tier5_units
            breakdown['tier5_amount'] = tier5_amount
            total_amount += tier5_amount

    # Calculate average rate per cubic meter
    if consumption > 0:
        average_rate = (total_amount / Decimal(consumption)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    else:
        average_rate = Decimal('0.00')

    breakdown['total_amount'] = total_amount
    breakdown['average_rate'] = average_rate

    return (total_amount, average_rate, breakdown)


def calculate_penalty(bill, settings=None) -> Tuple[Decimal, int, str]:
    """
    Calculate the penalty amount for an overdue bill.

    This function implements a defensible penalty calculation that:
    1. Respects grace periods
    2. Applies caps to prevent excessive penalties
    3. Supports both percentage and fixed penalty types
    4. Returns detailed information for audit trails

    Args:
        bill: The Bill instance to calculate penalty for
        settings: Optional SystemSetting instance (will fetch if not provided)

    Returns:
        Tuple of (penalty_amount, days_overdue, calculation_details)
        - penalty_amount: Decimal amount of penalty
        - days_overdue: Integer number of days past due
        - calculation_details: String describing how penalty was calculated

    Example:
        >>> penalty, days, details = calculate_penalty(bill)
        >>> print(f"Penalty: ₱{penalty} ({days} days late)")
        >>> print(details)
    """
    from .models import SystemSetting

    # Get system settings if not provided
    if settings is None:
        settings = SystemSetting.objects.first()

    # Default return values
    zero_penalty = (Decimal('0.00'), 0, "No penalty applied")

    # Check if bill exists and is valid
    if not bill:
        return zero_penalty

    # Check if bill is already paid
    if bill.status == 'Paid':
        return (Decimal('0.00'), 0, "Bill is already paid - no penalty")

    # Check if penalty is enabled
    if settings and not settings.penalty_enabled:
        return (Decimal('0.00'), 0, "Penalties are disabled in system settings")

    # Check if penalty was waived
    if bill.penalty_waived:
        return (Decimal('0.00'), 0, f"Penalty waived: {bill.penalty_waived_reason or 'No reason provided'}")

    # Get current date
    today = timezone.now().date()

    # Check if bill is overdue
    if today <= bill.due_date:
        return (Decimal('0.00'), 0, f"Bill not yet due (due date: {bill.due_date})")

    # Calculate days overdue
    days_overdue = (today - bill.due_date).days

    # Check grace period
    grace_period = settings.penalty_grace_period_days if settings else 0
    if days_overdue <= grace_period:
        return (Decimal('0.00'), days_overdue,
                f"Within grace period ({days_overdue} of {grace_period} days)")

    # Calculate penalty based on type
    if settings:
        penalty_type = settings.penalty_type
        penalty_rate = settings.penalty_rate
        fixed_amount = settings.fixed_penalty_amount
        max_penalty = settings.max_penalty_amount
    else:
        # Default values if no settings
        penalty_type = 'percentage'
        penalty_rate = Decimal('10.00')
        fixed_amount = Decimal('50.00')
        max_penalty = Decimal('500.00')

    # Calculate penalty amount
    if penalty_type == 'percentage':
        # Percentage-based penalty
        penalty_amount = (bill.total_amount * penalty_rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        calculation_details = (
            f"Percentage penalty: {penalty_rate}% of ₱{bill.total_amount} = ₱{penalty_amount} "
            f"({days_overdue} days overdue, grace period: {grace_period} days)"
        )
    else:
        # Fixed amount penalty
        penalty_amount = fixed_amount
        calculation_details = (
            f"Fixed penalty: ₱{fixed_amount} "
            f"({days_overdue} days overdue, grace period: {grace_period} days)"
        )

    # Apply maximum cap if set (0 means no cap)
    if max_penalty > 0 and penalty_amount > max_penalty:
        original_penalty = penalty_amount
        penalty_amount = max_penalty
        calculation_details += f" | Capped from ₱{original_penalty} to ₱{max_penalty}"

    return (penalty_amount, days_overdue, calculation_details)


def update_bill_penalty(bill, settings=None, save=True) -> Tuple[bool, str]:
    """
    Update the penalty fields on a bill based on current date and settings.

    This function should be called:
    1. When viewing a bill (to show current penalty)
    2. Before processing payment (to lock in the penalty amount)
    3. Via a scheduled task to update all overdue bills

    Args:
        bill: The Bill instance to update
        settings: Optional SystemSetting instance
        save: Whether to save the bill after updating

    Returns:
        Tuple of (changed, message)
        - changed: Boolean indicating if penalty was changed
        - message: String describing what happened
    """
    from .models import SystemSetting

    if settings is None:
        settings = SystemSetting.objects.first()

    # Don't update paid bills
    if bill.status == 'Paid':
        return (False, "Bill is already paid")

    # Don't update waived penalties
    if bill.penalty_waived:
        return (False, "Penalty has been waived")

    # Calculate current penalty
    penalty_amount, days_overdue, details = calculate_penalty(bill, settings)

    # Check if anything changed
    if bill.penalty_amount == penalty_amount and bill.days_overdue == days_overdue:
        return (False, "No changes to penalty")

    # Update bill fields
    old_penalty = bill.penalty_amount
    bill.penalty_amount = penalty_amount
    bill.days_overdue = days_overdue

    # Set penalty applied date if this is the first time penalty is applied
    if penalty_amount > 0 and not bill.penalty_applied_date:
        bill.penalty_applied_date = timezone.now().date()

    if save:
        bill.save(update_fields=[
            'penalty_amount', 'days_overdue', 'penalty_applied_date',
            'senior_citizen_discount'
        ])

    if penalty_amount > old_penalty:
        return (True, f"Penalty increased from ₱{old_penalty} to ₱{penalty_amount}")
    elif penalty_amount < old_penalty:
        return (True, f"Penalty decreased from ₱{old_penalty} to ₱{penalty_amount}")
    else:
        return (True, f"Days overdue updated to {days_overdue}")


def waive_penalty(bill, user, reason: str = "") -> Tuple[bool, str]:
    """
    Waive the penalty for a bill. Requires admin privileges.

    Args:
        bill: The Bill instance
        user: The User who is waiving the penalty
        reason: The reason for waiving the penalty

    Returns:
        Tuple of (success, message)
    """
    if bill.status == 'Paid':
        return (False, "Cannot waive penalty on a paid bill")

    if bill.penalty_waived:
        return (False, "Penalty has already been waived")

    if bill.penalty_amount <= 0:
        return (False, "No penalty to waive")

    # Store the original penalty for audit
    original_penalty = bill.penalty_amount

    # Update bill
    bill.penalty_waived = True
    bill.penalty_waived_by = user
    bill.penalty_waived_reason = reason
    bill.penalty_waived_date = timezone.now()
    bill.save()

    return (True, f"Penalty of ₱{original_penalty} has been waived")


def get_penalty_summary(consumer) -> dict:
    """
    Get a summary of penalties for a consumer.

    Args:
        consumer: The Consumer instance

    Returns:
        Dictionary with penalty statistics
    """
    from .models import Bill, Payment
    from django.db.models import Sum, Count

    # Get all bills for this consumer
    bills = consumer.bills.all()

    # Calculate statistics
    total_penalties_charged = bills.aggregate(
        total=Sum('penalty_amount')
    )['total'] or Decimal('0.00')

    waived_penalties = bills.filter(penalty_waived=True).aggregate(
        total=Sum('penalty_amount')
    )['total'] or Decimal('0.00')

    # Get paid penalties from Payment records
    paid_penalties = Payment.objects.filter(
        bill__consumer=consumer
    ).aggregate(
        total=Sum('penalty_amount')
    )['total'] or Decimal('0.00')

    # Count overdue bills
    overdue_count = bills.filter(
        status='Pending',
        due_date__lt=timezone.now().date()
    ).count()

    return {
        'total_penalties_charged': total_penalties_charged,
        'waived_penalties': waived_penalties,
        'paid_penalties': paid_penalties,
        'outstanding_penalties': total_penalties_charged - waived_penalties - paid_penalties,
        'overdue_bills_count': overdue_count,
    }


def format_currency(amount: Decimal) -> str:
    """Format a decimal amount as Philippine Peso currency."""
    if amount is None:
        return "₱0.00"
    return f"₱{amount:,.2f}"


def get_payment_breakdown(bill, settings=None) -> dict:
    """
    Get a detailed breakdown of what needs to be paid for a bill.

    This is used in the payment inquiry page to show consumers
    exactly what they owe and why.

    Args:
        bill: The Bill instance
        settings: Optional SystemSetting instance

    Returns:
        Dictionary with payment breakdown details
    """
    from .models import SystemSetting

    if settings is None:
        settings = SystemSetting.objects.first()

    # Update penalty calculation first
    update_bill_penalty(bill, settings, save=True)

    # Build breakdown
    breakdown = {
        'bill_id': bill.id,
        'consumer_name': bill.consumer.full_name,
        'id_number': bill.consumer.id_number,
        'billing_period': bill.billing_period,
        'due_date': bill.due_date,

        # Bill components
        'consumption': bill.consumption,
        'rate_per_cubic': bill.rate_per_cubic,
        'consumption_charge': bill.consumption * bill.rate_per_cubic,
        'fixed_charge': bill.fixed_charge,
        'subtotal': bill.total_amount,

        # Penalty info
        'is_overdue': bill.is_overdue,
        'days_overdue': bill.days_overdue,
        'penalty_amount': bill.effective_penalty,
        'penalty_waived': bill.penalty_waived,
        'penalty_rate': settings.penalty_rate if settings else Decimal('10.00'),
        'penalty_type': settings.penalty_type if settings else 'percentage',

        # Senior citizen discount
        'is_senior_citizen': bill.consumer.is_senior_citizen,
        'senior_citizen_discount': bill.senior_citizen_discount,

        # Totals
        'total_amount_due': bill.total_amount_due,

        # Status
        'status': bill.status,
    }

    # Add penalty calculation details
    if bill.is_overdue and not bill.penalty_waived:
        _, _, details = calculate_penalty(bill, settings)
        breakdown['penalty_details'] = details
    else:
        breakdown['penalty_details'] = None

    return breakdown


def bulk_update_penalties(queryset=None) -> Tuple[int, int]:
    """
    Bulk update penalties for all pending overdue bills.

    This can be called from a management command or scheduled task
    to keep penalties up to date.

    Args:
        queryset: Optional queryset of bills to update. If None, updates all pending bills.

    Returns:
        Tuple of (updated_count, total_count)
    """
    from .models import Bill, SystemSetting

    settings = SystemSetting.objects.first()

    if queryset is None:
        queryset = Bill.objects.filter(status='Pending')

    updated = 0
    total = queryset.count()

    for bill in queryset:
        changed, _ = update_bill_penalty(bill, settings, save=True)
        if changed:
            updated += 1

    return (updated, total)


# ============================================================================
# SMS NOTIFICATION UTILITIES
# ============================================================================
def send_sms_notification(phone_number: str, message: str) -> bool:
    """
    Send an SMS using the Semaphore API.
    Runs asynchronously if possible to avoid blocking the web request.
    """
    import threading
    from django.conf import settings
    import requests
    import logging
    
    logger = logging.getLogger('sms_notifications')
    
    if not getattr(settings, 'SMS_NOTIFICATIONS_ENABLED', False):
        logger.info(f"SMS disabled. Would have sent to {phone_number}: {message}")
        return False
        
    api_key = getattr(settings, 'SEMAPHORE_API_KEY', '')
    if not api_key:
        logger.warning("SMS enabled but SEMAPHORE_API_KEY is missing.")
        return False
        
    # Format phone number to numbers only
    formatted_number = ''.join(filter(str.isdigit, str(phone_number)))
    if not formatted_number:
        return False
        
    def _send():
        try:
            sender_name = getattr(settings, 'SEMAPHORE_SENDER_NAME', 'SEMAPHORE')
            payload = {
                'apikey': api_key,
                'number': formatted_number,
                'message': message,
                'sendername': sender_name
            }
            # Timeout set to 10 seconds for API call
            response = requests.post('https://api.semaphore.co/api/v4/messages', data=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"SMS sent successfully to {formatted_number}")
            else:
                logger.error(f"Failed to send SMS to {formatted_number}. Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            logger.error(f"Exception sending SMS to {formatted_number}: {str(e)}")
            
    # Run in a background thread to prevent blocking the HTTP response
    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()
    
    return True

def send_bill_sms(bill) -> bool:
    """
    Helper to send an SMS when a bill is generated.
    """
    if not bill or not bill.consumer or not bill.consumer.phone_number:
        return False
        
    phone_number = bill.consumer.phone_number
    amount = format_currency(bill.total_amount)
    due_date = bill.due_date.strftime('%b %d, %Y')
    billing_month = bill.billing_period.strftime('%B %Y')
    
    message = f"Balilihan Waterworks: Your bill for {billing_month} is {amount}. Due on {due_date}. Please pay promptly to avoid penalties."
    
    return send_sms_notification(phone_number, message)
