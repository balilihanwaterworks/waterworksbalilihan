# Balilihan Waterworks Management System - System Architecture

**Version:** 2.0
**Last Updated:** November 24, 2025
**Project:** Django-based Water Utility Billing & Management System

> **v2.0 Updates:** Added Late Payment Penalty System, Payment History, Enhanced Audit Trail

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Diagrams](#component-diagrams)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Database Schema](#database-schema)
6. [Technology Stack](#technology-stack)
7. [Deployment Architecture](#deployment-architecture)

---

## System Overview

The Balilihan Waterworks Management System is a comprehensive web-based platform designed to manage water utility operations for the Balilihan municipality in the Philippines. The system handles the complete lifecycle from consumer registration through payment collection, with integrated mobile and IoT support.

### Key Capabilities
- **Consumer Management:** Registration, tracking, and status management
- **Meter Reading:** Multi-source data collection (manual, mobile, IoT)
- **Automated Billing:** Consumption-based billing with configurable rates
- **Late Payment Penalties:** Configurable penalty system with grace periods (NEW v2.0)
- **Payment Processing:** Transaction handling with official receipt generation
- **Penalty Waiver:** Admin ability to waive penalties with audit trail (NEW v2.0)
- **Payment History:** Complete payment tracking with penalty details (NEW v2.0)
- **Reporting & Analytics:** Revenue reports, delinquency tracking, exports
- **Mobile Integration:** RESTful API for Android field staff app
- **Role-Based Access:** Admin and field staff with barangay-level permissions

---

## Architecture Diagram

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BALILIHAN WATERWORKS MANAGEMENT SYSTEM                    │
│                         Three-Tier Architecture                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            PRESENTATION LAYER                                │
├────────────────────┬────────────────────┬────────────────────────────────────┤
│                    │                    │                                    │
│  ┌──────────────┐  │  ┌──────────────┐  │  ┌──────────────────────────────┐ │
│  │  Web Browser │  │  │ Android App  │  │  │  Smart Meter / IoT Device   │ │
│  │              │  │  │              │  │  │                              │ │
│  │  • Admin     │  │  │  • Field     │  │  │  • Automated Readings       │ │
│  │  • Staff     │  │  │    Staff     │  │  │  • Webhook Integration      │ │
│  │  • Dashboard │  │  │  • Reading   │  │  │  • Real-time Data           │ │
│  │  • Reports   │  │  │    Entry     │  │  │                              │ │
│  └──────┬───────┘  │  └──────┬───────┘  │  └──────────┬───────────────────┘ │
│         │          │         │          │             │                     │
│         │ HTTPS    │         │ REST API │             │ Webhook (POST)      │
│         │          │         │ (JSON)   │             │                     │
└─────────┼──────────┴─────────┼──────────┴─────────────┼─────────────────────┘
          │                    │                        │
          └────────────────────┼────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────────┐
│                         APPLICATION LAYER (Django)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        URL Router (urls.py)                             │ │
│  │  Dispatches requests to appropriate views based on URL patterns         │ │
│  └──────────────────────────────┬─────────────────────────────────────────┘ │
│                                 │                                            │
│  ┌──────────────────────────────▼─────────────────────────────────────────┐ │
│  │                      View Layer (views.py - 1,511 lines)                │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │ Auth Views   │  │ Consumer     │  │ Meter        │  │ Payment    │ │ │
│  │  │              │  │ Management   │  │ Reading      │  │ Processing │ │ │
│  │  │ • Login      │  │              │  │              │  │            │ │ │
│  │  │ • Logout     │  │ • Add/Edit   │  │ • Submit     │  │ • Inquire  │ │ │
│  │  │ • Session    │  │ • Search     │  │ • Confirm    │  │ • Receipt  │ │ │
│  │  └──────────────┘  │ • Filter     │  │ • Export     │  └────────────┘ │ │
│  │                    └──────────────┘  └──────────────┘                  │ │
│  │                                                                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │ Billing      │  │ Reports &    │  │ System       │  │ API        │ │ │
│  │  │              │  │ Dashboard    │  │ Config       │  │ Endpoints  │ │ │
│  │  │ • Auto-gen   │  │              │  │              │  │            │ │ │
│  │  │   Bills      │  │ • Revenue    │  │ • Water Rate │  │ • Mobile   │ │ │
│  │  │ • View Bills │  │ • Delinquent │  │ • Settings   │  │   Login    │ │ │
│  │  └──────────────┘  │ • Export     │  └──────────────┘  │ • Readings │ │ │
│  │                    └──────────────┘                     │ • Consumers│ │ │
│  │                                                          └────────────┘ │ │
│  └──────────────────────────────┬─────────────────────────────────────────┘ │
│                                 │                                            │
│  ┌──────────────────────────────▼─────────────────────────────────────────┐ │
│  │                    Business Logic & Forms Layer                         │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │  • Form Validation (forms.py)                                           │ │
│  │  • Business Rules (embedded in views & models)                          │ │
│  │  • Authentication & Authorization (Django Auth + StaffProfile)          │ │
│  │  • Template Tags (custom filters)                                       │ │
│  └──────────────────────────────┬─────────────────────────────────────────┘ │
│                                 │                                            │
│  ┌──────────────────────────────▼─────────────────────────────────────────┐ │
│  │                    Model Layer (models.py - 293 lines)                  │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │                          Django ORM Models                               │ │
│  │                                                                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │ │
│  │  │  Consumer   │  │MeterReading │  │    Bill     │  │   Payment    │  │ │
│  │  │             │  │             │  │             │  │              │  │ │
│  │  │ • Personal  │  │ • Value     │  │ • Amount    │  │ • OR Number  │  │ │
│  │  │ • Location  │  │ • Date      │  │ • Period    │  │ • Change     │  │ │
│  │  │ • Meter     │  │ • Confirmed │  │ • Status    │  │ • Timestamp  │  │ │
│  │  │ • Account # │  │ • Source    │  │ • Readings  │  │              │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘  │ │
│  │                                                                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │ │
│  │  │  Barangay   │  │   Purok     │  │ MeterBrand  │  │SystemSetting │  │ │
│  │  │             │  │             │  │             │  │              │  │ │
│  │  │ • Name      │  │ • Name      │  │ • Name      │  │ • Water Rate │  │ │
│  │  │             │  │ • Barangay  │  │             │  │ • Updated    │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘  │ │
│  │                                                                          │ │
│  │  ┌─────────────────────────┐                                            │ │
│  │  │    StaffProfile         │                                            │ │
│  │  │                         │                                            │ │
│  │  │  • User (OneToOne)      │                                            │ │
│  │  │  • Assigned Barangay    │                                            │ │
│  │  │  • Role                 │                                            │ │
│  │  └─────────────────────────┘                                            │ │
│  │                                                                          │ │
│  │  Model Features:                                                        │ │
│  │  • Auto-generation (Account #, OR #)                                    │ │
│  │  • Validation hooks (clean(), save())                                   │ │
│  │  • Relationships (ForeignKey, OneToOne)                                 │ │
│  │  • Timestamps (auto_now, auto_now_add)                                  │ │
│  └──────────────────────────────┬─────────────────────────────────────────┘ │
│                                 │                                            │
└─────────────────────────────────┼─────────────────────────────────────────┬┘
                                  │                                          │
                                  │        Django ORM (Database Abstraction)│
                                  │                                          │
┌─────────────────────────────────▼──────────────────────────────────────────▼┐
│                              DATA LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    PostgreSQL Database (Production)                     │ │
│  │                      SQLite3 Database (Development)                     │ │
│  ├─────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                          │ │
│  │  Tables:                                                                 │ │
│  │  • consumers_consumer          • consumers_bill                         │ │
│  │  • consumers_meterreading      • consumers_payment                      │ │
│  │  • consumers_barangay          • consumers_purok                        │ │
│  │  • consumers_meterbrand        • consumers_systemsetting                │ │
│  │  • consumers_staffprofile      • auth_user (Django)                     │ │
│  │                                                                          │ │
│  │  Features:                                                               │ │
│  │  • ACID Transactions                                                     │ │
│  │  • Foreign Key Constraints                                               │ │
│  │  • Unique Constraints                                                    │ │
│  │  • Indexes on frequently queried fields                                 │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            STATIC FILE LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  • CSS (Bootstrap 5.3.2 + Custom styles)                                    │
│  • JavaScript (Dark mode toggle, AJAX)                                      │
│  • Images (Logo, backgrounds, icons)                                        │
│  • Collected via Django's collectstatic                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Diagrams

### 1. Consumer Management Component

```
┌───────────────────────────────────────────────────────────┐
│            CONSUMER MANAGEMENT COMPONENT                  │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │             Web Interface (Templates)                │ │
│  │                                                      │ │
│  │  • consumer_management.html ─┐                      │ │
│  │  • add_consumer.html         │                      │ │
│  │  • edit_consumer.html        ├─► Bootstrap Forms   │ │
│  │  • consumer_detail.html      │   AJAX Dropdowns    │ │
│  │  • consumer_list.html        │                      │ │
│  └──────────────┬───────────────────────────────────────┘ │
│                 │                                          │
│                 ▼                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Views (Business Logic)                  │ │
│  │                                                      │ │
│  │  consumer_management(request)                       │ │
│  │    ├─► Search/Filter consumers                      │ │
│  │    ├─► Paginate results (10 per page)               │ │
│  │    └─► Render consumer list                         │ │
│  │                                                      │ │
│  │  add_consumer(request)                              │ │
│  │    ├─► Validate form data                           │ │
│  │    ├─► Auto-generate account number                 │ │
│  │    └─► Save to database                             │ │
│  │                                                      │ │
│  │  edit_consumer(request, consumer_id)                │ │
│  │    ├─► Load existing consumer                       │ │
│  │    ├─► Update fields                                │ │
│  │    └─► Save changes                                 │ │
│  │                                                      │ │
│  │  consumer_detail(request, consumer_id)              │ │
│  │    ├─► Fetch consumer info                          │ │
│  │    ├─► Get latest 3 pending bills                   │ │
│  │    └─► Display details                              │ │
│  └──────────────┬───────────────────────────────────────┘ │
│                 │                                          │
│                 ▼                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                 Forms (Validation)                   │ │
│  │                                                      │ │
│  │  ConsumerForm(ModelForm)                            │ │
│  │    ├─► Field validation                             │ │
│  │    ├─► Widget customization                         │ │
│  │    └─► Error handling                               │ │
│  └──────────────┬───────────────────────────────────────┘ │
│                 │                                          │
│                 ▼                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                 Models (Data)                        │ │
│  │                                                      │ │
│  │  Consumer                                            │ │
│  │    ├─► personal_info (name, DOB, gender, phone)     │ │
│  │    ├─► household_info (civil status, location)      │ │
│  │    ├─► meter_info (brand, serial, first reading)    │ │
│  │    ├─► account_number (auto-generated)              │ │
│  │    └─► status (active/disconnected)                 │ │
│  │                                                      │ │
│  │  Barangay ◄──── Consumer.barangay (ForeignKey)      │ │
│  │  Purok ◄──────── Consumer.purok (ForeignKey)        │ │
│  │  MeterBrand ◄─── Consumer.meter_brand (ForeignKey)  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### 2. Meter Reading & Billing Component

```
┌──────────────────────────────────────────────────────────────────────┐
│          METER READING & BILLING COMPONENT                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              INPUT SOURCES (Multi-channel)                      │ │
│  │                                                                 │ │
│  │  ┌────────────┐   ┌────────────┐   ┌───────────────────────┐  │ │
│  │  │   Manual   │   │ Mobile App │   │  Smart Meter Webhook  │  │ │
│  │  │  Web Form  │   │   (API)    │   │      (IoT Device)     │  │ │
│  │  └─────┬──────┘   └──────┬─────┘   └───────────┬───────────┘  │ │
│  │        │                  │                     │              │ │
│  │        │ POST             │ POST                │ POST         │ │
│  │        │ /meter-readings  │ /api/meter-readings │ /webhook     │ │
│  │        │                  │                     │              │ │
│  └────────┼──────────────────┼─────────────────────┼──────────────┘ │
│           │                  │                     │                │
│           └──────────────────┼─────────────────────┘                │
│                              │                                      │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │            READING PROCESSING (views.py)                        │ │
│  │                                                                 │ │
│  │  meter_readings(request) │ api_submit_reading(request)         │ │
│  │                          │                                      │ │
│  │  1. Validate Input                                             │ │
│  │     ├─► Date validation (not in future)                        │ │
│  │     ├─► Value validation (non-negative integer)                │ │
│  │     └─► Consumer exists check                                  │ │
│  │                                                                 │ │
│  │  2. Check Existing Reading                                     │ │
│  │     ├─► Query: consumer + date                                 │ │
│  │     ├─► If exists & confirmed → Reject                         │ │
│  │     ├─► If exists & unconfirmed → Update                       │ │
│  │     └─► If not exists → Create                                 │ │
│  │                                                                 │ │
│  │  3. Save MeterReading                                          │ │
│  │     ├─► Set source (manual/mobile_app/smart_meter)             │ │
│  │     ├─► Set is_confirmed = False                               │ │
│  │     └─► Store reading_date & reading_value                     │ │
│  └────────────────────────────┬───────────────────────────────────┘ │
│                                │                                    │
│                                ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │            READING CONFIRMATION (views.py)                      │ │
│  │                                                                 │ │
│  │  confirm_reading(request, reading_id)                          │ │
│  │                                                                 │ │
│  │  1. Validation Checks                                          │ │
│  │     ├─► Not already confirmed                                  │ │
│  │     ├─► Date not in future                                     │ │
│  │     ├─► No duplicate on same date                              │ │
│  │     └─► current_value >= previous_value                        │ │
│  │                                                                 │ │
│  │  2. Retrieve Previous Reading                                  │ │
│  │     ├─► Query last confirmed reading for consumer              │ │
│  │     ├─► Filter: reading_date < current_date                    │ │
│  │     └─► Order by: -reading_date                                │ │
│  │                                                                 │ │
│  │  3. Calculate Consumption                                      │ │
│  │     consumption = current_value - previous_value               │ │
│  │                                                                 │ │
│  │  4. Fetch System Rate                                          │ │
│  │     rate = SystemSetting.rate_per_cubic (default: ₱22.50)      │ │
│  │     fixed_charge = ₱50.00                                      │ │
│  │                                                                 │ │
│  │  5. Calculate Bill Amount                                      │ │
│  │     total = (consumption × rate) + fixed_charge                │ │
│  │                                                                 │ │
│  │  6. Create Bill                                                │ │
│  │     ├─► Set consumer                                           │ │
│  │     ├─► Link previous_reading & current_reading                │ │
│  │     ├─► Set billing_period (1st of month)                      │ │
│  │     ├─► Set due_date (20th of month)                           │ │
│  │     ├─► Set consumption, rate, total                           │ │
│  │     └─► Set status = 'Pending'                                 │ │
│  │                                                                 │ │
│  │  7. Mark Reading as Confirmed                                  │ │
│  │     reading.is_confirmed = True                                │ │
│  │     reading.save()                                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    DATA MODELS                                  │ │
│  │                                                                 │ │
│  │  MeterReading                        Bill                      │ │
│  │  ├─► consumer (FK)                   ├─► consumer (FK)         │ │
│  │  ├─► reading_date                    ├─► previous_reading (FK) │ │
│  │  ├─► reading_value                   ├─► current_reading (FK)  │ │
│  │  ├─► source                          ├─► billing_period        │ │
│  │  ├─► is_confirmed (Boolean)          ├─► due_date              │ │
│  │  └─► created_at                      ├─► consumption           │ │
│  │                                      ├─► rate_per_cubic        │ │
│  │                                      ├─► fixed_charge          │ │
│  │                                      ├─► total_amount          │ │
│  │                                      └─► status (Pending/Paid) │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3. Payment Processing Component

```
┌──────────────────────────────────────────────────────────────────────┐
│               PAYMENT PROCESSING COMPONENT                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │         STEP 1: PAYMENT INQUIRY (views.py:1396)                 │ │
│  │                                                                 │ │
│  │  User Flow:                                                     │ │
│  │  1. Staff selects Barangay ──► AJAX loads Puroks               │ │
│  │  2. Staff selects Purok (optional) ──► Filter consumers        │ │
│  │  3. System displays consumer list with pending bills           │ │
│  │  4. Staff selects specific consumer                            │ │
│  │  5. System shows latest pending bill details                   │ │
│  │                                                                 │ │
│  │  Data Retrieved:                                                │ │
│  │  • Consumer: Name, Account #, Location                         │ │
│  │  • Bill: Period, Consumption, Amount Due, Due Date             │ │
│  └────────────────────────────┬───────────────────────────────────┘ │
│                                │                                    │
│                                ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │         STEP 2: PAYMENT ENTRY (POST /payment/)                  │ │
│  │                                                                 │ │
│  │  Input:                                                         │ │
│  │  • bill_id (from selected bill)                                │ │
│  │  • received_amount (cash from consumer)                        │ │
│  │                                                                 │ │
│  │  Validation:                                                    │ │
│  │  ├─► Bill exists and status = 'Pending'                        │ │
│  │  ├─► received_amount >= bill.total_amount                      │ │
│  │  └─► Valid decimal number                                      │ │
│  └────────────────────────────┬───────────────────────────────────┘ │
│                                │                                    │
│                                ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │         STEP 3: PAYMENT CREATION (models.py:276)                │ │
│  │                                                                 │ │
│  │  Payment.save() Hook:                                          │ │
│  │                                                                 │ │
│  │  1. Calculate Change                                           │ │
│  │     change = received_amount - amount_paid                     │ │
│  │                                                                 │ │
│  │  2. Generate OR Number                                         │ │
│  │     format: OR-YYYYMMDD-XXXXXX                                 │ │
│  │     example: OR-20250115-A3F2B9                                │ │
│  │     components:                                                 │ │
│  │       ├─► OR: Prefix                                           │ │
│  │       ├─► YYYYMMDD: Current date                               │ │
│  │       └─► XXXXXX: UUID hex (6 chars, uppercase)                │ │
│  │                                                                 │ │
│  │  3. Validation (full_clean)                                    │ │
│  │     ├─► received_amount >= amount_paid                         │ │
│  │     └─► amount_paid == bill.total_amount                       │ │
│  │                                                                 │ │
│  │  4. Save Payment Record                                        │ │
│  │     ├─► bill (FK to Bill)                                      │ │
│  │     ├─► amount_paid                                            │ │
│  │     ├─► received_amount                                        │ │
│  │     ├─► change (auto-calculated)                               │ │
│  │     ├─► or_number (auto-generated, unique)                     │ │
│  │     └─► payment_date (auto_now_add)                            │ │
│  └────────────────────────────┬───────────────────────────────────┘ │
│                                │                                    │
│                                ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │         STEP 4: UPDATE BILL STATUS                              │ │
│  │                                                                 │ │
│  │  bill.status = 'Paid'                                          │ │
│  │  bill.save()                                                    │ │
│  └────────────────────────────┬───────────────────────────────────┘ │
│                                │                                    │
│                                ▼                                    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │         STEP 5: GENERATE RECEIPT (views.py:1482)                │ │
│  │                                                                 │ │
│  │  payment_receipt(request, payment_id)                          │ │
│  │                                                                 │ │
│  │  Display Data:                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │       OFFICIAL RECEIPT                                    │  │ │
│  │  │       OR Number: OR-20250115-A3F2B9                       │  │ │
│  │  │       Date: January 15, 2025 10:30 AM                     │  │ │
│  │  │                                                           │  │ │
│  │  │       Consumer: Juan Dela Cruz (BW-00001)                │  │ │
│  │  │       Location: Poblacion, Purok 1                       │  │ │
│  │  │                                                           │  │ │
│  │  │       Billing Period: January 2025                       │  │ │
│  │  │       Consumption: 15 m³                                  │  │ │
│  │  │       Rate: ₱22.50/m³                                     │  │ │
│  │  │       Fixed Charge: ₱50.00                                │  │ │
│  │  │       Total Amount: ₱387.50                               │  │ │
│  │  │                                                           │  │ │
│  │  │       Amount Received: ₱400.00                            │  │ │
│  │  │       Change: ₱12.50                                      │  │ │
│  │  │                                                           │  │ │
│  │  │       [Print Button]                                      │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                 │ │
│  │  Features:                                                      │ │
│  │  • Print-optimized CSS                                         │ │
│  │  • Consumer & bill details                                     │ │
│  │  • OR number prominently displayed                             │ │
│  │  • Timestamp of payment                                        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    DATA MODELS                                  │ │
│  │                                                                 │ │
│  │  Payment                                                        │ │
│  │  ├─► bill (ForeignKey to Bill)                                 │ │
│  │  ├─► amount_paid (Decimal - bill total)                        │ │
│  │  ├─► received_amount (Decimal - cash received)                 │ │
│  │  ├─► change (Decimal - auto-calculated)                        │ │
│  │  ├─► or_number (CharField - unique, auto-generated)            │ │
│  │  └─► payment_date (DateTimeField - auto_now_add)               │ │
│  │                                                                 │ │
│  │  Methods:                                                       │ │
│  │  ├─► clean() - Validation logic                                │ │
│  │  └─► save() - Auto-generation logic                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### 1. Complete Transaction Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│              COMPLETE TRANSACTION LIFECYCLE                              │
└─────────────────────────────────────────────────────────────────────────┘

[Consumer Registration]
        │
        │  Staff enters consumer info
        │  System auto-generates account # (BW-XXXXX)
        ▼
┌──────────────────┐
│  Consumer Record │ ────► Status: Active
│   BW-00001       │       First Reading: 100 m³
└────────┬─────────┘
         │
         │  Time passes, water consumed
         │
         ▼
[Meter Reading Submission] ◄─── Multiple Sources:
         │                      • Field staff (mobile app)
         │                      • Office staff (web)
         │                      • Smart meter (webhook)
         │
         │  Reading: 115 m³
         │  Date: 2025-01-15
         │  Source: mobile_app
         ▼
┌──────────────────┐
│  MeterReading    │
│  Value: 115      │ ────► Status: Unconfirmed
│  Confirmed: No   │
└────────┬─────────┘
         │
         │  Staff reviews in web interface
         │  Views by barangay
         │
         ▼
[Reading Confirmation]
         │
         │  Validation:
         │  • 115 >= 100 ✓
         │  • Date valid ✓
         │  • No duplicates ✓
         │
         │  Calculation:
         │  • Consumption = 115 - 100 = 15 m³
         │  • Rate = ₱22.50/m³
         │  • Amount = (15 × 22.50) + 50 = ₱387.50
         │
         ▼
┌──────────────────┐         ┌──────────────────┐
│  MeterReading    │         │      Bill        │
│  Value: 115      │         │  Period: Jan 2025│
│  Confirmed: Yes  │ ◄───────│  Amount: ₱387.50 │ ────► Auto-created
└──────────────────┘         │  Status: Pending │
                             └────────┬─────────┘
                                      │
                                      │  Consumer visits office
                                      │  or receives bill
                                      │
                                      ▼
[Payment Inquiry]
         │
         │  Staff searches consumer
         │  by barangay/purok/name
         │
         │  System displays:
         │  • Consumer: BW-00001
         │  • Bill: ₱387.50 (Pending)
         │  • Due: Jan 20, 2025
         ▼
[Payment Entry]
         │
         │  Consumer pays: ₱400.00
         │  Staff enters amount
         │
         │  Validation:
         │  • ₱400 >= ₱387.50 ✓
         │
         │  Calculation:
         │  • Change = 400 - 387.50 = ₱12.50
         │
         │  Generation:
         │  • OR# = OR-20250115-A3F2B9
         │
         ▼
┌──────────────────┐         ┌──────────────────┐
│      Bill        │         │    Payment       │
│  Period: Jan 2025│         │  OR: OR-2025...  │
│  Amount: ₱387.50 │         │  Paid: ₱387.50   │
│  Status: Paid    │ ◄───────│  Received: ₱400  │ ────► Auto-created
└──────────────────┘         │  Change: ₱12.50  │
                             └────────┬─────────┘
                                      │
                                      │  Receipt generated
                                      │
                                      ▼
[Official Receipt Display]
         │
         │  Printable receipt with:
         │  • OR number
         │  • Consumer & bill details
         │  • Payment breakdown
         │
         └──► Staff prints and gives to consumer


[Next Month Cycle Begins]
         │
         └──► New meter reading submitted...
```

### 2. Mobile App Integration Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│              MOBILE APP INTEGRATION DATA FLOW                            │
└─────────────────────────────────────────────────────────────────────────┘

[Field Staff Opens App]
         │
         ▼
POST /api/login/
{
  "username": "field_staff_1",
  "password": "********"
}
         │
         │  Django authenticates
         │  Retrieves StaffProfile
         │
         ▼
Response:
{
  "status": "success",
  "token": "session_key_abc123",
  "barangay": "Poblacion"
}
         │
         │  App stores token
         │
         ▼
GET /api/rate/
Authorization: session_key_abc123
         │
         ▼
Response:
{
  "status": "success",
  "rate_per_cubic": 22.50,
  "updated_at": "2025-01-01T00:00:00Z"
}
         │
         │  App displays current rate
         │
         ▼
GET /api/consumers/
Authorization: session_key_abc123
         │
         │  System filters by assigned barangay
         │
         ▼
Response:
[
  {
    "id": 1,
    "account_number": "BW-00001",
    "name": "Juan Dela Cruz",
    "serial_number": "MTR-12345"
  },
  {
    "id": 2,
    "account_number": "BW-00002",
    "name": "Maria Santos",
    "serial_number": "MTR-12346"
  }
]
         │
         │  App displays consumer list
         │  Field staff visits each house
         │
         ▼
[Staff Reads Meter at Consumer's House]
         │
         │  Meter shows: 125 m³
         │  Staff enters in app
         │
         ▼
POST /api/meter-readings/
{
  "consumer_id": 1,
  "reading": 125,
  "reading_date": "2025-01-15"
}
         │
         │  API Validation:
         │  • Consumer exists ✓
         │  • Reading value valid ✓
         │  • Date format valid ✓
         │
         │  Check existing reading:
         │  • Query: consumer_id=1, date=2025-01-15
         │  • Found: Yes (value: 120, unconfirmed)
         │  • Action: Update existing record
         │
         ▼
Response:
{
  "status": "success",
  "message": "Meter reading updated successfully",
  "reading_id": 456,
  "consumer_name": "Juan Dela Cruz",
  "account_number": "BW-00001",
  "reading_value": 125,
  "reading_date": "2025-01-15"
}
         │
         │  App shows success
         │  Staff moves to next house
         │
         ▼
[Repeat for all consumers in barangay]
         │
         │  All readings submitted to server
         │  Stored as unconfirmed
         │
         ▼
[Back at Office]
         │
         │  Staff logs into web interface
         │  Reviews readings by barangay
         │
         ▼
Web Interface:
/meter-readings/barangay/1/
         │
         │  Shows all latest readings:
         │  • Submitted from mobile app
         │  • Status: Unconfirmed
         │  • Preview of consumption
         │
         ▼
[Staff Confirms Selected Readings]
         │
         │  Triggers bill generation
         │  (See Complete Transaction Flow)
         │
         └──► Cycle complete
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────┐
│        auth_user        │
│ (Django Built-in)       │
│─────────────────────────│
│ PK│id                   │
│   │username             │
│   │password             │
│   │is_staff             │
│   │email                │
│   │...                  │
└────────┬────────────────┘
         │
         │ 1:1
         │
         ▼
┌─────────────────────────┐
│     StaffProfile        │
│─────────────────────────│
│ PK│id                   │
│ FK│user_id              │
│ FK│assigned_barangay_id │
│   │role                 │
└─────────────────────────┘
         │
         │
         │ N:1
         │
         ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│       Barangay          │           │         Purok           │
│─────────────────────────│           │─────────────────────────│
│ PK│id                   │◄──────────│ PK│id                   │
│   │name (unique)        │    1:N    │ FK│barangay_id          │
└────────┬────────────────┘           │   │name                 │
         │                            └─────────────────────────┘
         │ 1:N                                 │
         │                                     │ 1:N
         │                                     │
         ▼                                     ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│       Consumer          │           │      MeterBrand         │
│─────────────────────────│           │─────────────────────────│
│ PK│id                   │           │ PK│id                   │
│   │account_number(uniq) │◄──────────│   │name (unique)        │
│   │first_name           │    1:N    └─────────────────────────┘
│   │middle_name          │
│   │last_name            │
│   │birth_date           │
│   │gender               │
│   │phone_number         │
│   │civil_status         │
│   │spouse_name          │
│ FK│barangay_id          │
│ FK│purok_id             │
│   │household_number     │
│   │usage_type           │
│ FK│meter_brand_id       │
│   │serial_number        │
│   │first_reading        │
│   │registration_date    │
│   │status               │
│   │created_at           │
│   │updated_at           │
└────────┬────────────────┘
         │
         │ 1:N
         │
         ▼
┌─────────────────────────┐
│     MeterReading        │
│─────────────────────────│
│ PK│id                   │
│ FK│consumer_id          │
│   │reading_date         │◄─── UNIQUE (consumer_id, reading_date)
│   │reading_value        │
│   │source               │
│   │is_confirmed         │
│   │created_at           │
└────────┬────────────────┘
         │
         │ N:1 (as current_reading)
         │ N:1 (as previous_reading)
         │
         ▼
┌─────────────────────────┐
│          Bill           │
│─────────────────────────│
│ PK│id                   │
│ FK│consumer_id          │
│ FK│previous_reading_id  │
│ FK│current_reading_id   │
│   │billing_period       │
│   │due_date             │
│   │consumption          │
│   │rate_per_cubic       │
│   │fixed_charge         │
│   │total_amount         │
│   │status               │
│   │created_at           │
└────────┬────────────────┘
         │
         │ 1:N
         │
         ▼
┌─────────────────────────┐
│        Payment          │
│─────────────────────────│
│ PK│id                   │
│ FK│bill_id              │
│   │amount_paid          │
│   │received_amount      │
│   │change               │
│   │or_number (unique)   │
│   │payment_date         │
└─────────────────────────┘


┌─────────────────────────┐
│    SystemSetting        │
│─────────────────────────│
│ PK│id                   │
│   │rate_per_cubic       │
│   │updated_at           │
└─────────────────────────┘
```

### Key Relationships

1. **User ↔ StaffProfile** (1:1)
   - Each user has one staff profile
   - Profile links user to assigned barangay

2. **Barangay ↔ Purok** (1:N)
   - Each barangay contains multiple puroks
   - Puroks belong to one barangay

3. **Barangay ↔ Consumer** (1:N)
   - Consumers are grouped by barangay
   - Used for field staff assignment

4. **Consumer ↔ MeterReading** (1:N)
   - Each consumer has multiple readings over time
   - Unique constraint on (consumer, date)

5. **MeterReading ↔ Bill** (2:1)
   - Each bill links to TWO readings:
     - Previous reading (baseline)
     - Current reading (for billing period)

6. **Bill ↔ Payment** (1:N)
   - Each bill can have multiple payments (partial payments)
   - Typically 1:1 in current implementation

---

## Technology Stack

### Backend Technologies
- **Framework:** Django 5.2.7
- **Language:** Python 3.x
- **ORM:** Django ORM
- **Authentication:** Django Auth + Custom StaffProfile
- **API:** Function-based views with @csrf_exempt
- **Session Management:** Django sessions

### Frontend Technologies
- **UI Framework:** Bootstrap 5.3.2
- **Icons:** Bootstrap Icons 1.11.0
- **Template Engine:** Django Templates
- **JavaScript:** Vanilla JS (AJAX, dark mode)
- **CSS:** Custom styles + Bootstrap

### Database
- **Production:** PostgreSQL
- **Development:** SQLite3
- **Migration Tool:** Django migrations

### Data Export
- **Excel:** openpyxl 3.1.5
- **CSV:** Python csv module

### Deployment
- **WSGI Server:** Gunicorn (configured)
- **Platform:** Railway (ready)
- **Static Files:** Django collectstatic
- **Environment:** Python virtual environment

### Development Tools
- **Package Manager:** pip
- **Requirements:** requirements.txt
- **Version Control:** Git
- **Admin Interface:** Django Admin

---

## Deployment Architecture

### Production Deployment (Railway)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERNET / PUBLIC                             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 │ HTTPS
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RAILWAY PLATFORM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │               Load Balancer / Reverse Proxy                     │ │
│  │               (Railway Infrastructure)                          │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
│                             │                                        │
│                             ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Gunicorn WSGI Server                         │ │
│  │                    (Python Process)                             │ │
│  │                                                                 │ │
│  │  • Workers: Multiple                                            │ │
│  │  • Port: $PORT (environment variable)                           │ │
│  │  • Binding: 0.0.0.0:$PORT                                       │ │
│  │  • Timeout: 120s                                                │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
│                             │                                        │
│                             ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │               Django Application                                │ │
│  │               (waterworks project)                              │ │
│  │                                                                 │ │
│  │  • Settings: Production config                                  │ │
│  │  • Static Files: Served via WhiteNoise                         │ │
│  │  • Database: PostgreSQL connection                             │ │
│  │  • Middleware: Security, Session, Auth                         │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
│                             │                                        │
│                             ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                 PostgreSQL Database                             │ │
│  │                 (Railway Managed)                               │ │
│  │                                                                 │ │
│  │  • Host: railway.app (internal)                                │ │
│  │  • Credentials: Environment variables                           │ │
│  │  • Backups: Automatic                                           │ │
│  │  • Connection Pooling: Enabled                                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Environment Variables:                                              │
│  • DATABASE_URL                                                      │
│  • SECRET_KEY                                                        │
│  • DEBUG=False                                                       │
│  • ALLOWED_HOSTS                                                     │
│  • PORT                                                              │
│                                                                      │
│  Health Checks:                                                      │
│  • Endpoint: /health                                                 │
│  • Interval: 30s                                                     │
│  • Timeout: 10s                                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Local Development Setup

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DEVELOPER MACHINE                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                 Django Development Server                       │ │
│  │                 python manage.py runserver                      │ │
│  │                                                                 │ │
│  │  • Host: 127.0.0.1:8000 or 0.0.0.0:8000                        │ │
│  │  • Debug: True                                                  │ │
│  │  • Auto-reload: Enabled                                         │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
│                             │                                        │
│                             ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                   SQLite3 Database                              │ │
│  │                   db.sqlite3                                    │ │
│  │                                                                 │ │
│  │  • Location: Project root                                       │ │
│  │  • Size: ~278 KB                                                │ │
│  │  • Version controlled: No (.gitignore)                          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Access Methods:                                                     │
│  • Web: http://localhost:8000                                       │
│  • Admin: http://localhost:8000/admin                               │
│  • API: http://localhost:8000/api/*                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## System Integration Points

### 1. Mobile App Integration
- **Protocol:** REST API over HTTPS
- **Authentication:** Django session-based
- **Data Format:** JSON
- **Endpoints:** `/api/login/`, `/api/consumers/`, `/api/meter-readings/`, `/api/rate/`

### 2. Smart Meter Integration
- **Protocol:** Webhook (HTTP POST)
- **Authentication:** @csrf_exempt (alternative auth recommended)
- **Data Format:** JSON
- **Endpoint:** `/smart-meter-webhook/`

### 3. Export Integrations
- **Excel:** openpyxl library, .xlsx format
- **CSV:** Python csv module, RFC 4180 compliant
- **Use Cases:** Meter readings, delinquent reports

### 4. Admin Interface
- **Framework:** Django Admin
- **Access:** `/admin/`
- **Customization:** Custom admin.py (245 lines)
- **Features:** Model management, inline editing

---

## Security Architecture

### Authentication Flow
1. User submits credentials
2. Django authenticate() validates
3. Session created (HttpOnly cookie)
4. StaffProfile retrieved
5. Access granted based on role

### Authorization Levels
- **Public:** Login pages
- **Authenticated:** @login_required decorator
- **Role-Based:** StaffProfile.role (admin, field_staff)
- **Data-Level:** Barangay assignment filtering

### Data Protection
- **Passwords:** Django PBKDF2 hashing
- **CSRF:** Token-based protection (web forms)
- **SQL Injection:** Django ORM parameterization
- **XSS:** Django template auto-escaping

### API Security
- **Authentication:** Session-based for mobile
- **CSRF:** Exempt on API endpoints (alternative needed)
- **Input Validation:** Type checking, range validation
- **Rate Limiting:** (Recommended for production)

---

**Document End**

For detailed event workflows, see EVENT_LIST.md
