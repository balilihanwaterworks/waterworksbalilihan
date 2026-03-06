from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from consumers.models import SystemSetting, Consumer, Bill
from consumers.utils import calculate_tiered_water_bill, calculate_penalty

class BillingLogicTests(TestCase):
    def setUp(self):
        # Create a mock system setting
        self.settings = SystemSetting.objects.create(
            # Residential rates
            residential_minimum_charge=Decimal('75.00'),
            residential_tier2_rate=Decimal('15.00'),
            residential_tier3_rate=Decimal('16.00'),
            residential_tier4_rate=Decimal('17.00'),
            residential_tier5_rate=Decimal('18.00'),
            
            # Commercial rates
            commercial_minimum_charge=Decimal('100.00'),
            commercial_tier2_rate=Decimal('18.00'),
            commercial_tier3_rate=Decimal('20.00'),
            commercial_tier4_rate=Decimal('22.00'),
            commercial_tier5_rate=Decimal('24.00'),

            # Penalties
            penalty_enabled=True,
            penalty_type='percentage',
            penalty_rate=Decimal('10.00'),
            penalty_grace_period_days=5,
            fixed_penalty_amount=Decimal('50.00'),
            max_penalty_amount=Decimal('500.00'),
        )

    def test_tiered_water_bill_residential_minimum(self):
        # Tier 1 (1-5 m³): Minimum charge = ₱75
        total, avg_rate, breakdown = calculate_tiered_water_bill(3, 'Residential', self.settings)
        self.assertEqual(total, Decimal('75.00'))
        self.assertEqual(breakdown['tier1_units'], 3)
        self.assertEqual(breakdown['tier2_units'], 0)

    def test_tiered_water_bill_residential_tier4(self):
        # Example: 25 m³ consumption
        # Tier 1 (1-5): Minimum charge = ₱75
        # Tier 2 (6-10): 5 units × ₱15 = ₱75
        # Tier 3 (11-20): 10 units × ₱16 = ₱160
        # Tier 4 (21-25): 5 units × ₱17 = ₱85
        # Total = ₱395
        total, avg_rate, breakdown = calculate_tiered_water_bill(25, 'Residential', self.settings)
        self.assertEqual(total, Decimal('395.00'))
        self.assertEqual(breakdown['tier1_units'], 5)
        self.assertEqual(breakdown['tier2_units'], 5)
        self.assertEqual(breakdown['tier3_units'], 10)
        self.assertEqual(breakdown['tier4_units'], 5)
        self.assertEqual(breakdown['tier5_units'], 0)

    def test_tiered_water_bill_commercial(self):
        # Example: 15 m³ commercial
        # Tier 1 (1-5): Minimum charge = ₱100
        # Tier 2 (6-10): 5 units × ₱18 = ₱90
        # Tier 3 (11-15): 5 units × ₱20 = ₱100
        # Total = ₱290
        total, avg_rate, breakdown = calculate_tiered_water_bill(15, 'Commercial', self.settings)
        self.assertEqual(total, Decimal('290.00'))


class PenaltyCalculationTests(TestCase):
    def setUp(self):
        self.settings = SystemSetting.objects.create(
            penalty_enabled=True,
            penalty_type='percentage',
            penalty_rate=Decimal('10.00'),
            penalty_grace_period_days=5,
            max_penalty_amount=Decimal('500.00'),
        )
        self.today = timezone.now().date()
        # Create a mock consumer with all required fields
        self.consumer = Consumer.objects.create(
            first_name="Test",
            last_name="Consumer",
            birth_date="1980-01-01",
            gender="Male",
            phone_number="09123456789",
            civil_status="Single",
            household_number="HH-001",
            usage_type="Residential",
            first_reading=0,
            registration_date=self.today,
        )
        
        # We need another mock for Bill to avoid full DB overhead if possible,
        # but Django TestCase handles DB tests well.
        
        # Using a model instance that won't require saving foreign keys deeply, or just mock it.
        class MockBill:
            pass
            
        self.mock_bill = MockBill()
        self.mock_bill.status = 'Pending'
        self.mock_bill.penalty_waived = False
        self.mock_bill.total_amount = Decimal('1000.00')

    def test_penalty_not_due_yet(self):
        self.mock_bill.due_date = self.today + timedelta(days=2)
        penalty, days, _ = calculate_penalty(self.mock_bill, self.settings)
        self.assertEqual(penalty, Decimal('0.00'))
        self.assertEqual(days, 0)
        
    def test_penalty_grace_period(self):
        # Due yesterday (1 day overdue) -> Still in 5 day grace period
        self.mock_bill.due_date = self.today - timedelta(days=1)
        penalty, days, _ = calculate_penalty(self.mock_bill, self.settings)
        self.assertEqual(penalty, Decimal('0.00'))
        self.assertEqual(days, 1)

    def test_penalty_after_grace_period(self):
        # Due 10 days ago (past 5 day grace period)
        self.mock_bill.due_date = self.today - timedelta(days=10)
        penalty, days, _ = calculate_penalty(self.mock_bill, self.settings)
        # 10% of 1000 = 100
        self.assertEqual(penalty, Decimal('100.00'))
        self.assertEqual(days, 10)

    def test_penalty_capped(self):
        # Bill is 10,000, 10% penalty would be 1,000. Capped at 500.
        self.mock_bill.total_amount = Decimal('10000.00')
        self.mock_bill.due_date = self.today - timedelta(days=10)
        penalty, days, _ = calculate_penalty(self.mock_bill, self.settings)
        self.assertEqual(penalty, Decimal('500.00'))
