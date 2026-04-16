# Balilihan Waterworks Management System - Complete Documentation

## Project Overview

**Project Name**: Balilihan Waterworks Management System
**Framework**: Django 5.2.7
**Frontend**: Tailwind CSS, Bootstrap Icons, Chart.js 4.4.0
**Database**: PostgreSQL (Production) / SQLite (Development)
**Deployment**: Render
**Production URL**: https://waterworks-rose.onrender.com/

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Recent Updates & Accomplishments](#recent-updates--accomplishments)
3. [Database Schema](#database-schema)
4. [Features & Functionality](#features--functionality)
5. [URL Routes](#url-routes)
6. [User Roles & Permissions](#user-roles--permissions)
7. [API Integration](#api-integration)
8. [Deployment & Configuration](#deployment--configuration)
9. [File Structure](#file-structure)
10. [Event List & Workflows](#event-list--workflows)

---

## System Architecture

### High-Level Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Browser]
        MOBILE[Android App]
    end

    subgraph "Application Layer"
        DJANGO[Django 5.2.7]
        VIEWS[Views & Business Logic]
        TEMPLATES[Tailwind CSS Templates]
    end

    subgraph "Data Layer"
        POSTGRES[(PostgreSQL Database)]
        MEDIA[Media Storage]
    end

    subgraph "External Services"
        RENDER[Render Deployment]
        GITHUB[GitHub Repository]
    end

    WEB --> DJANGO
    MOBILE --> DJANGO
    DJANGO --> VIEWS
    VIEWS --> TEMPLATES
    VIEWS --> POSTGRES
    VIEWS --> MEDIA
    DJANGO --> RENDER
    RENDER --> GITHUB
```

### Technology Stack

```mermaid
graph LR
    subgraph "Frontend"
        A[Tailwind CSS]
        B[Bootstrap Icons]
        C[Chart.js 4.4.0]
        D[JavaScript ES6+]
    end

    subgraph "Backend"
        E[Django 5.2.7]
        F[Python 3.x]
        G[Django REST Framework]
    end

    subgraph "Database"
        H[PostgreSQL]
        I[SQLite Dev]
    end

    subgraph "Deployment"
        J[Render]
        K[Gunicorn]
        L[WhiteNoise]
    end
```

---

## Recent Updates & Accomplishments

### Phase 1: Professional UI Redesign (Tailwind CSS Migration)

#### 1. Connected Consumers Page Redesign
- **File**: `consumers/templates/consumers/consumer_list_filtered.html`
- **Commit**: `456bc48`
- **Changes**:
  - Migrated from Bootstrap to Tailwind CSS
  - Added professional stats summary cards
  - Enhanced table layout with modern styling
  - Improved badges and status indicators
  - Added hover effects and transitions
  - Responsive grid layout (md:grid-cols-2, lg:grid-cols-4)

#### 2. User Profile Dropdown Fix
- **File**: `consumers/templates/consumers/base.html`
- **Commit**: `4571825`
- **Issue**: Dropdown menu not functioning due to JavaScript event propagation
- **Solution**:
  - Added `event.stopPropagation()` to prevent immediate closure
  - Implemented setTimeout delay to prevent race condition
  - Added escape key support for better UX
  - Auto-close other dropdowns when opening new one

#### 3. Dashboard Redesign with Charts
- **File**: `consumers/templates/consumers/home.html`
- **Commit**: `3870855`
- **Features Added**:
  - 4 gradient stat cards with animations
  - Revenue Bar Chart (Chart.js)
  - Water Consumption Bar Chart
  - Payment Status Doughnut Chart
  - Revenue summary table
  - Enhanced report generation card

#### 4. Bill Inquiry & Payment Professional Redesign
- **File**: `consumers/templates/consumers/inquire.html`
- **Commit**: `ae11938`
- **Improvements**:
  - Removed step progress indicators for cleaner look
  - Enhanced all sections with gradient headers
  - Professional consumer cards design
  - Improved payment form layout
  - Better bill details presentation

#### 5. Minimal Dashboard Redesign
- **File**: `consumers/templates/consumers/home.html`
- **Commit**: `11b64ce`
- **Design Philosophy**: Thin, minimal, organized
- **Key Changes**:
  - Replaced gradient cards with white cards + thin borders
  - Reduced padding (p-3 instead of p-5)
  - Smaller icons (w-8 h-8 vs w-12 h-12)
  - Compact fonts (text-xl vs text-3xl)
  - 3-column grid layout
  - Reduced chart heights (200px vs 280px)
  - Minimal shadows and clean backgrounds

#### 6. Minimal Bill Inquiry Redesign
- **File**: `consumers/templates/consumers/inquire.html`
- **Commit**: `6828b8f`
- **Specifications**:
  - White backgrounds throughout
  - 1px borders (`border-light-300`)
  - Subtle box-shadow: `0 1px 3px rgba(0,0,0,0.05)`
  - Reduced padding (px-5 py-3 for headers)
  - Smaller consumer cards (p-3, w-10 h-10 icons)
  - Compact bill details (p-4, text-3xl amount)
  - Simplified payment form

#### 7. Meter Reading Overview Fix
- **File**: `consumers/templates/consumers/meter_reading_overview.html`
- **Commit**: `e56098a`
- **Issue**: Internal server error due to non-existent template filters
- **Fix**: Replaced custom filters with proper context variables
  - `{{ barangay_data|sum_total_consumers }}` → `{{ total_consumers_sum }}`
  - `{{ barangay_data|sum_ready }}` → `{{ total_ready_sum }}`
  - `{{ barangay_data|sum_pending }}` → `{{ total_pending_sum }}`

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    Consumer ||--o{ MeterReading : has
    Consumer ||--o{ Bill : receives
    Consumer }o--|| Barangay : "belongs to"
    Consumer }o--|| Purok : "belongs to"
    Bill ||--o{ Payment : has
    MeterReading ||--o| Bill : generates
    Consumer }o--|| ConsumerStatus : has

    Consumer {
        int id PK
        string account_number UK
        string first_name
        string last_name
        string email
        string phone_number
        int barangay_id FK
        int purok_id FK
        string meter_number
        date installation_date
        int status_id FK
        datetime created_at
        datetime updated_at
    }

    Barangay {
        int id PK
        string name
        string code
        text description
    }

    Purok {
        int id PK
        string name
        int barangay_id FK
        text description
    }

    ConsumerStatus {
        int id PK
        string name
        string description
    }

    MeterReading {
        int id PK
        int consumer_id FK
        decimal previous_reading
        decimal reading_value
        date reading_date
        string source
        boolean is_confirmed
        int confirmed_by_id FK
        datetime confirmed_at
        text notes
        datetime created_at
    }

    Bill {
        int id PK
        int consumer_id FK
        int meter_reading_id FK
        decimal consumption
        decimal amount
        decimal service_charge
        decimal total_amount
        date billing_period_start
        date billing_period_end
        date due_date
        string status
        datetime created_at
        datetime updated_at
    }

    Payment {
        int id PK
        int bill_id FK
        decimal amount_paid
        date payment_date
        string payment_method
        string reference_number
        string received_by
        text notes
        datetime created_at
    }
```

### Database Tables Overview

| Table | Records | Purpose |
|-------|---------|---------|
| `consumers_consumer` | 1000+ | Main consumer information |
| `consumers_barangay` | 15 | Barangay locations |
| `consumers_purok` | 100+ | Purok subdivisions |
| `consumers_meterreading` | 5000+ | Water meter readings |
| `consumers_bill` | 4000+ | Generated bills |
| `consumers_payment` | 3000+ | Payment records |
| `consumers_consumerstatus` | 3 | Status types (Active, Disconnected, Suspended) |
| `auth_user` | 50+ | Staff user accounts |

### Key Model Relationships

```python
# Consumer Model
class Consumer(models.Model):
    account_number = models.CharField(max_length=20, unique=True)
    barangay = models.ForeignKey(Barangay, on_delete=models.SET_NULL)
    purok = models.ForeignKey(Purok, on_delete=models.SET_NULL)
    status = models.ForeignKey(ConsumerStatus, on_delete=models.SET_NULL)

# MeterReading Model
class MeterReading(models.Model):
    consumer = models.ForeignKey(Consumer, on_delete=models.CASCADE)
    SOURCE_CHOICES = [
        ('mobile_app', 'Mobile App'),
        ('manual', 'Manual Entry'),
        ('smart_meter', 'Smart Meter')
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    is_confirmed = models.BooleanField(default=False)

# Bill Model
class Bill(models.Model):
    consumer = models.ForeignKey(Consumer, on_delete=models.CASCADE)
    meter_reading = models.ForeignKey(MeterReading, on_delete=models.SET_NULL)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled')
    ]
```

---

## Features & Functionality

### 1. Consumer Management

#### Features:
- **Consumer Registration**: Add new water service consumers
- **Profile Management**: Update consumer information
- **Status Tracking**: Active, Disconnected, Suspended
- **Location Mapping**: Barangay and Purok assignment
- **Meter Information**: Track meter numbers and installation dates

#### Pages:
- Consumer List (`/consumers/`)
- Consumer Detail (`/consumer/<id>/`)
- Add Consumer (`/add/`)
- Edit Consumer (`/edit/<id>/`)
- Connected Consumers (`/connected-consumers/`)

### 2. Meter Reading System

#### Features:
- **Mobile App Integration**: Android app for field meter reading
- **Manual Entry**: Web-based reading input
- **Reading Confirmation**: Two-step verification process
- **Consumption Calculation**: Automatic usage computation
- **Source Tracking**: Mobile app vs manual entry

#### Workflow:
```mermaid
sequenceDiagram
    participant Reader as Meter Reader
    participant App as Android App
    participant Server as Django Backend
    participant Admin as Admin/Staff

    Reader->>App: Open meter reading interface
    Reader->>App: Enter meter reading value
    App->>Server: POST /api/meter-readings/
    Server->>Server: Validate reading
    Server->>Server: Save as unconfirmed
    Server-->>App: Success response
    Admin->>Server: View unconfirmed readings
    Admin->>Server: Confirm reading
    Server->>Server: Generate bill
    Server-->>Admin: Bill created
```

#### Pages:
- Meter Readings List (`/meter-readings/`)
- Meter Reading Overview (`/meter-reading-overview/`)
- Barangay Meter Readings (`/barangay-meter-readings/<id>/`)
- Confirm Reading (`/confirm-reading/<id>/`)

### 3. Billing System

#### Features:
- **Automatic Bill Generation**: Created upon reading confirmation
- **Tiered Pricing**: Multiple rate tiers based on consumption
- **Service Charges**: Fixed monthly fees
- **Due Date Management**: Automatic calculation
- **Status Tracking**: Pending, Paid, Overdue, Cancelled

#### Billing Rates:
```python
# Example rate structure
RATES = {
    'tier_1': {'max': 10, 'rate': 150.00},   # 0-10 m³
    'tier_2': {'max': 20, 'rate': 200.00},   # 11-20 m³
    'tier_3': {'max': 30, 'rate': 250.00},   # 21-30 m³
    'tier_4': {'rate': 300.00}               # 31+ m³
}
SERVICE_CHARGE = 50.00
```

#### Pages:
- Bills List (`/bills/`)
- Bill Detail (`/bill/<id>/`)
- Generate Bill (`/generate-bill/`)
- Bill Inquiry (`/inquire/`)

### 4. Payment Processing

#### Features:
- **Multiple Payment Methods**: Cash, Bank Transfer, GCash, etc.
- **Partial Payments**: Support for installment payments
- **Receipt Generation**: Automatic receipt creation
- **Payment History**: Complete transaction log
- **Reference Tracking**: Unique reference numbers

#### Payment Workflow:
```mermaid
graph TD
    A[Consumer Views Bill] --> B{Payment Method?}
    B -->|Cash| C[Visit Office]
    B -->|Online| D[Online Payment]
    C --> E[Staff Records Payment]
    D --> E
    E --> F[Update Bill Status]
    F --> G[Generate Receipt]
    G --> H[Send Notification]
```

#### Pages:
- Payments List (`/payments/`)
- Record Payment (`/record-payment/<bill_id>/`)
- Payment History (`/payment-history/<consumer_id>/`)

### 5. Reporting & Analytics

#### Dashboard Metrics:
- Total Consumers
- Connected Consumers
- Active Consumers
- Disconnected Consumers
- Monthly Revenue
- Water Consumption Trends
- Payment Status Distribution
- Overdue Bills Count

#### Charts & Visualizations:
1. **Revenue Bar Chart**: Monthly revenue trends
2. **Consumption Bar Chart**: Water usage by barangay
3. **Payment Doughnut Chart**: Paid vs Pending vs Overdue

#### Reports:
- Monthly Revenue Report (`/monthly-revenue-report/`)
- Consumer Report (`/consumer-report/`)
- Payment Report (`/payment-report/`)
- Consumption Report (`/consumption-report/`)

### 6. User Management & Authentication

#### User Roles:
- **Admin**: Full system access
- **Staff**: Limited access (no delete permissions)
- **Meter Reader**: Mobile app access only

#### Authentication Features:
- Login/Logout
- Password Reset
- Role-based Access Control
- Profile Photo Upload
- Session Management

#### Pages:
- Staff Login (`/staff-login/`)
- Reset Password (`/reset-password/<user_id>/`)
- Profile Management (in header dropdown)

---

## URL Routes

### Complete URL Configuration (42 Routes)

```python
# consumers/urls.py
urlpatterns = [
    # Authentication
    path('staff-login/', staff_login, name='staff_login'),
    path('logout/', user_logout, name='logout'),
    path('reset-password/<int:user_id>/', reset_password, name='reset_password'),

    # Dashboard
    path('', home, name='home'),

    # Consumer Management
    path('consumers/', consumer_list, name='consumer_list'),
    path('add/', add_consumer, name='add_consumer'),
    path('consumer/<int:pk>/', consumer_detail, name='consumer_detail'),
    path('edit/<int:pk>/', edit_consumer, name='edit_consumer'),
    path('delete/<int:pk>/', delete_consumer, name='delete_consumer'),
    path('connected-consumers/', consumer_list_filtered, name='connected_consumers'),

    # Meter Readings
    path('meter-readings/', meter_readings, name='meter_readings'),
    path('meter-reading-overview/', meter_reading_overview, name='meter_reading_overview'),
    path('barangay-meter-readings/<int:barangay_id>/', barangay_meter_readings, name='barangay_meter_readings'),
    path('confirm-reading/<int:reading_id>/', confirm_reading, name='confirm_reading'),

    # Billing
    path('bills/', bill_list, name='bill_list'),
    path('bill/<int:pk>/', bill_detail, name='bill_detail'),
    path('generate-bill/', generate_bill, name='generate_bill'),
    path('inquire/', inquire, name='inquire'),

    # Payments
    path('payments/', payment_list, name='payment_list'),
    path('record-payment/<int:bill_id>/', record_payment, name='record_payment'),

    # Reports
    path('monthly-revenue-report/', monthly_revenue_report, name='monthly_revenue_report'),
    path('consumer-report/', consumer_report, name='consumer_report'),

    # AJAX APIs
    path('get-puroks/', get_puroks, name='get_puroks'),
    path('get-consumers/', get_consumers, name='get_consumers'),
    path('get-consumer-bills/<int:consumer_id>/', get_consumer_bills, name='get_consumer_bills'),

    # Mobile App API
    path('api/login/', api_login, name='api_login'),
    path('api/meter-readings/', api_meter_readings, name='api_meter_readings'),
    path('api/consumers/', api_consumer_list, name='api_consumer_list'),
]
```

### URL Grouping by Function

| Category | URL Pattern | View Function | Description |
|----------|-------------|---------------|-------------|
| **Auth** | `/staff-login/` | `staff_login` | Staff login page |
| | `/logout/` | `user_logout` | Logout handler |
| | `/reset-password/<id>/` | `reset_password` | Password reset |
| **Dashboard** | `/` | `home` | Main dashboard |
| **Consumers** | `/consumers/` | `consumer_list` | All consumers |
| | `/add/` | `add_consumer` | Add new consumer |
| | `/consumer/<id>/` | `consumer_detail` | Consumer profile |
| | `/edit/<id>/` | `edit_consumer` | Edit consumer |
| | `/connected-consumers/` | `consumer_list_filtered` | Active consumers |
| **Readings** | `/meter-readings/` | `meter_readings` | All readings |
| | `/meter-reading-overview/` | `meter_reading_overview` | Overview by barangay |
| | `/confirm-reading/<id>/` | `confirm_reading` | Confirm & bill |
| **Billing** | `/bills/` | `bill_list` | All bills |
| | `/inquire/` | `inquire` | Public bill inquiry |
| **Payments** | `/payments/` | `payment_list` | All payments |
| | `/record-payment/<id>/` | `record_payment` | Record payment |
| **Reports** | `/monthly-revenue-report/` | `monthly_revenue_report` | Revenue report |
| **API** | `/api/login/` | `api_login` | Mobile app login |
| | `/api/meter-readings/` | `api_meter_readings` | Submit readings |
| | `/api/consumers/` | `api_consumer_list` | Get consumer list |

---

## User Roles & Permissions

### Role-Based Access Control

```mermaid
graph TD
    A[User Login] --> B{Check Role}
    B -->|Admin| C[Full Access]
    B -->|Staff| D[Limited Access]
    B -->|Meter Reader| E[Mobile App Only]

    C --> F[All CRUD Operations]
    C --> G[User Management]
    C --> H[System Settings]

    D --> I[View/Edit Records]
    D --> J[No Delete]
    D --> K[No User Management]

    E --> L[View Consumer List]
    E --> M[Submit Readings]
    E --> N[View Reading History]
```

### Permission Matrix

| Feature | Admin | Staff | Meter Reader |
|---------|-------|-------|--------------|
| View Dashboard | ✓ | ✓ | ✗ |
| Manage Consumers | ✓ | ✓ (No Delete) | ✗ |
| View Meter Readings | ✓ | ✓ | ✓ (Own only) |
| Submit Readings | ✓ | ✓ | ✓ |
| Confirm Readings | ✓ | ✓ | ✗ |
| Generate Bills | ✓ | ✓ | ✗ |
| Record Payments | ✓ | ✓ | ✗ |
| View Reports | ✓ | ✓ | ✗ |
| User Management | ✓ | ✗ | ✗ |
| System Settings | ✓ | ✗ | ✗ |

### User Account Features

```python
# Custom User Model Extension
class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[
        ('admin', 'Administrator'),
        ('staff', 'Staff'),
        ('meter_reader', 'Meter Reader')
    ])
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    barangay_assignment = models.ForeignKey(Barangay, null=True, blank=True)
```

---

## API Integration

### Mobile App API Endpoints

#### 1. Authentication
```http
POST /api/login/
Content-Type: application/json

{
    "username": "meter_reader",
    "password": "password123"
}

Response:
{
    "success": true,
    "user_id": 5,
    "username": "meter_reader",
    "role": "meter_reader",
    "token": "abc123..."
}
```

#### 2. Get Consumer List
```http
GET /api/consumers/?barangay=1&purok=5
Authorization: Token abc123...

Response:
{
    "success": true,
    "consumers": [
        {
            "id": 100,
            "account_number": "ACC-001",
            "name": "Juan Dela Cruz",
            "address": "Barangay 1, Purok 5",
            "meter_number": "MTR-001",
            "last_reading": 150.5,
            "last_reading_date": "2025-10-15"
        }
    ]
}
```

#### 3. Submit Meter Reading
```http
POST /api/meter-readings/
Content-Type: application/json
Authorization: Token abc123...

{
    "consumer_id": 100,
    "reading_value": 165.3,
    "reading_date": "2025-11-21",
    "source": "mobile_app",
    "notes": "Normal reading"
}

Response:
{
    "success": true,
    "reading_id": 5001,
    "message": "Reading submitted successfully",
    "consumption": 14.8,
    "status": "pending_confirmation"
}
```

### AJAX Endpoints (Web Interface)

#### 1. Get Puroks by Barangay
```javascript
// GET /get-puroks/?barangay_id=1
fetch('/get-puroks/?barangay_id=1')
    .then(response => response.json())
    .then(data => {
        // data.puroks = [{id: 1, name: 'Purok 1'}, ...]
    });
```

#### 2. Get Consumers by Location
```javascript
// GET /get-consumers/?barangay=1&purok=5
fetch('/get-consumers/?barangay=1&purok=5')
    .then(response => response.json())
    .then(data => {
        // data.consumers = [{id: 100, name: '...', ...}, ...]
    });
```

#### 3. Get Consumer Bills
```javascript
// GET /get-consumer-bills/100/
fetch('/get-consumer-bills/100/')
    .then(response => response.json())
    .then(data => {
        // data.bills = [{id: 500, amount: 350.00, status: 'pending'}, ...]
    });
```

---

## Deployment & Configuration

### Production Environment

**Platform**: Render
**URL**: https://waterworks-rose.onrender.com/
**Database**: PostgreSQL (Render-managed)
**Static Files**: WhiteNoise
**Media Files**: Render volumes

### Environment Variables

```bash
# .env (Production)
DEBUG=False
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:pass@host:5432/dbname
ALLOWED_HOSTS=waterworks-rose.onrender.com
CSRF_TRUSTED_ORIGINS=https://waterworks-rose.onrender.com
```

### Render Configuration

```toml
# render.toml
[build]
builder = "NIXPACKS"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn waterworks.wsgi:application"
healthcheckPath = "/staff-login/"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
```

### Requirements

```txt
# requirements.txt
Django==5.2.7
psycopg2-binary==2.9.9
gunicorn==21.2.0
whitenoise==6.6.0
Pillow==10.2.0
djangorestframework==3.14.0
django-cors-headers==4.3.1
```

### Static Files Configuration

```python
# settings.py
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

### Database Migration

```bash
# Initial setup
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load initial data (if fixtures exist)
python manage.py loaddata barangays.json
python manage.py loaddata consumer_statuses.json
```

---

## File Structure

```
waterworks/
├── consumers/
│   ├── migrations/
│   ├── templates/
│   │   └── consumers/
│   │       ├── base.html                    # Base template with navigation
│   │       ├── home.html                    # Dashboard (minimal design)
│   │       ├── consumer_list.html           # Consumer list
│   │       ├── consumer_list_filtered.html  # Connected consumers
│   │       ├── consumer_detail.html         # Consumer profile
│   │       ├── add_consumer.html            # Add consumer form
│   │       ├── edit_consumer.html           # Edit consumer form
│   │       ├── meter_readings.html          # Meter readings list
│   │       ├── meter_reading_overview.html  # Overview by barangay
│   │       ├── barangay_meter_readings.html # Barangay-specific readings
│   │       ├── bill_list.html               # Bills list
│   │       ├── bill_detail.html             # Bill details
│   │       ├── inquire.html                 # Bill inquiry (minimal)
│   │       ├── payment_list.html            # Payments list
│   │       ├── record_payment.html          # Payment form
│   │       ├── staff_login.html             # Login page
│   │       ├── reset_password.html          # Password reset
│   │       └── monthly_revenue_report.html  # Revenue report
│   ├── static/
│   │   └── consumers/
│   │       └── images/
│   │           ├── logo.png
│   │           └── background.jpg
│   ├── models.py                            # Database models
│   ├── views.py                             # View functions (70+ views)
│   ├── urls.py                              # URL configuration (42 routes)
│   ├── forms.py                             # Django forms
│   └── admin.py                             # Admin configuration
├── waterworks/
│   ├── settings.py                          # Django settings
│   ├── urls.py                              # Root URL config
│   └── wsgi.py                              # WSGI application
├── static/
│   └── css/
│       └── styles.css                       # Tailwind CSS build
├── media/
│   └── profile_photos/                      # User profile photos
├── manage.py
├── requirements.txt
├── render.toml
└── PROJECT_DOCUMENTATION.md                 # This file
```

---

## Event List & Workflows

### 1. Consumer Registration Workflow

```mermaid
sequenceDiagram
    participant Staff
    participant System
    participant Database

    Staff->>System: Access "Add Consumer" page
    System->>Staff: Display registration form
    Staff->>System: Submit consumer details
    System->>System: Validate input
    alt Valid Data
        System->>Database: Create consumer record
        System->>Database: Assign account number
        Database-->>System: Success
        System->>Staff: Show success message
        System->>Staff: Redirect to consumer list
    else Invalid Data
        System->>Staff: Show validation errors
    end
```

**Events**:
1. `GET /add/` - Load registration form
2. `POST /add/` - Submit consumer data
3. `validate_consumer_data()` - Data validation
4. `generate_account_number()` - Auto-generate account
5. `Consumer.objects.create()` - Database insert
6. `redirect('consumer_list')` - Success redirect

### 2. Meter Reading Submission (Mobile App)

```mermaid
sequenceDiagram
    participant Reader as Meter Reader
    participant App as Android App
    participant API as Django API
    participant DB as Database

    Reader->>App: Login with credentials
    App->>API: POST /api/login/
    API->>DB: Verify credentials
    DB-->>API: User data
    API-->>App: Auth token

    Reader->>App: Select barangay/purok
    App->>API: GET /api/consumers/?barangay=1&purok=5
    API->>DB: Query consumers
    DB-->>API: Consumer list
    API-->>App: Consumer data

    Reader->>App: Select consumer
    Reader->>App: Enter meter reading
    App->>API: POST /api/meter-readings/
    API->>API: Validate reading
    API->>DB: Save as unconfirmed
    DB-->>API: Reading ID
    API-->>App: Success + consumption
    App->>Reader: Show confirmation
```

**Events**:
1. `api_login` - Authentication
2. `api_consumer_list` - Get consumers for route
3. `api_meter_readings` - Submit reading
4. `calculate_consumption()` - Compute usage
5. `MeterReading.objects.create()` - Save reading
6. `send_notification()` - Notify admin

### 3. Reading Confirmation & Bill Generation

```mermaid
sequenceDiagram
    participant Admin
    participant System
    participant DB as Database

    Admin->>System: View meter reading overview
    System->>DB: Get unconfirmed readings
    DB-->>System: Reading list
    System->>Admin: Display readings

    Admin->>System: Click "Confirm & Bill"
    System->>System: Confirm reading dialog
    Admin->>System: Confirm action

    System->>DB: Update reading.is_confirmed = True
    System->>DB: Set confirmed_by & confirmed_at

    System->>System: Calculate consumption
    System->>System: Apply rate tiers
    System->>System: Add service charge

    System->>DB: Create bill record
    System->>DB: Set bill due date
    DB-->>System: Bill ID

    System->>Admin: Show success message
    System->>Admin: Redirect to bills
```

**Events**:
1. `GET /meter-reading-overview/` - View unconfirmed
2. `GET /confirm-reading/<id>/` - Confirm reading
3. `update_reading_status()` - Mark confirmed
4. `calculate_bill_amount()` - Apply rates
5. `Bill.objects.create()` - Generate bill
6. `set_due_date()` - Calculate due date

### 4. Bill Inquiry & Payment

```mermaid
sequenceDiagram
    participant Consumer
    participant System
    participant DB as Database

    Consumer->>System: Access /inquire/
    System->>Consumer: Show location selector

    Consumer->>System: Select barangay & purok
    System->>DB: Query consumers
    DB-->>System: Consumer list
    System->>Consumer: Display consumer cards

    Consumer->>System: Click on consumer card
    System->>DB: Get consumer bills
    DB-->>System: Bill list
    System->>Consumer: Display bills

    Consumer->>System: Select bill to pay
    System->>Consumer: Show bill details
    System->>Consumer: Display payment form

    Consumer->>System: Submit payment info
    System->>System: Validate payment
    System->>DB: Create payment record
    System->>DB: Update bill status
    DB-->>System: Success

    System->>Consumer: Show receipt
```

**Events**:
1. `GET /inquire/` - Load inquiry page
2. `get_puroks()` - AJAX get puroks
3. `get_consumers()` - AJAX get consumers
4. `get_consumer_bills()` - AJAX get bills
5. `POST /record-payment/<id>/` - Submit payment
6. `update_bill_status()` - Mark as paid
7. `generate_receipt()` - Create receipt

### 5. Monthly Report Generation

```mermaid
graph TD
    A[Staff Access Report Page] --> B[Select Date Range]
    B --> C[System Query Database]
    C --> D[Aggregate Revenue Data]
    D --> E[Calculate Metrics]
    E --> F[Generate Charts]
    F --> G[Display Report]
    G --> H{Export?}
    H -->|PDF| I[Generate PDF]
    H -->|Excel| J[Generate Excel]
    H -->|No| K[End]
```

**Events**:
1. `GET /monthly-revenue-report/` - Load report page
2. `filter_by_date_range()` - Apply filters
3. `aggregate_revenue()` - Sum payments
4. `calculate_collections()` - Group by method
5. `generate_chart_data()` - Prepare visualization
6. `export_to_pdf()` - PDF generation (optional)

### 6. User Authentication Flow

```mermaid
stateDiagram-v2
    [*] --> Login: Access /staff-login/
    Login --> Authenticate: Submit Credentials
    Authenticate --> ValidUser: Correct
    Authenticate --> Login: Incorrect
    ValidUser --> CheckFirstLogin: Check Password
    CheckFirstLogin --> ResetPassword: First Login
    CheckFirstLogin --> Dashboard: Regular Login
    ResetPassword --> Dashboard: Password Changed
    Dashboard --> [*]: Logout
```

**Events**:
1. `GET /staff-login/` - Display login form
2. `POST /staff-login/` - Submit credentials
3. `authenticate()` - Verify user
4. `check_first_login()` - Check password status
5. `redirect('reset_password')` - Force reset
6. `login()` - Create session
7. `redirect('home')` - Go to dashboard

### 7. Disconnection Workflow

```mermaid
sequenceDiagram
    participant Staff
    participant System
    participant DB
    participant Consumer

    Staff->>System: View consumer profile
    System->>DB: Get consumer data
    DB-->>System: Consumer + bills
    System->>Staff: Display profile

    Staff->>System: Click "Disconnect"
    System->>System: Check unpaid bills

    alt Has Unpaid Bills
        System->>Staff: Show warning
        Staff->>System: Confirm disconnection
    end

    System->>DB: Update status = Disconnected
    System->>DB: Log disconnection date
    DB-->>System: Success

    System->>Consumer: Send notification (optional)
    System->>Staff: Show success message
```

**Events**:
1. `GET /consumer/<id>/` - View profile
2. `check_outstanding_bills()` - Verify payments
3. `POST /disconnect/<id>/` - Disconnect action
4. `update_consumer_status()` - Change status
5. `log_disconnection()` - Record event
6. `send_notification()` - Notify consumer

### 8. Dashboard Data Loading

```mermaid
graph LR
    A[Page Load] --> B[Query Active Consumers]
    A --> C[Query Connected Consumers]
    A --> D[Query Monthly Revenue]
    A --> E[Query Disconnected Count]

    B --> F[Calculate Metrics]
    C --> F
    D --> F
    E --> F

    F --> G[Prepare Chart Data]
    G --> H[Revenue Bar Chart]
    G --> I[Consumption Bar Chart]
    G --> J[Payment Doughnut Chart]

    H --> K[Render Dashboard]
    I --> K
    J --> K
```

**Events**:
1. `GET /` - Load dashboard
2. `count_active_consumers()` - Active count
3. `count_connected_consumers()` - Connected count
4. `calculate_monthly_revenue()` - Revenue sum
5. `get_revenue_trend()` - Chart data
6. `get_consumption_by_barangay()` - Chart data
7. `get_payment_distribution()` - Chart data
8. `render('home.html', context)` - Display

---

## Design System

### Color Palette (Tailwind CSS)

```css
/* Primary Colors */
--primary-50: #eff6ff;
--primary-600: #2563eb;
--primary-700: #1d4ed8;

/* Success Colors */
--success-100: #d1fae5;
--success-600: #059669;

/* Warning Colors */
--warning-100: #fef3c7;
--warning-600: #d97706;

/* Danger Colors */
--danger-50: #fef2f2;
--danger-600: #dc2626;

/* Light/Gray Colors */
--light-200: #e5e7eb;
--light-300: #d1d5db;
--dark-700: #374151;
--dark-900: #111827;
```

### Typography

```css
/* Headings */
h1 { @apply text-2xl font-bold text-gray-800; }
h2 { @apply text-xl font-semibold text-gray-800; }
h3 { @apply text-sm font-bold text-dark-900; }

/* Body Text */
p { @apply text-sm text-gray-700; }
.text-muted { @apply text-xs text-gray-500; }

/* Labels */
label { @apply text-xs font-medium text-dark-700; }
```

### Component Patterns

#### Minimal Card
```html
<div class="bg-white border border-light-300 rounded-lg p-3 hover:shadow-md transition-all">
    <!-- Content -->
</div>
```

#### Stat Card
```html
<div class="bg-white border border-light-300 rounded-lg p-3">
    <div class="flex items-center gap-2">
        <div class="w-8 h-8 bg-success-100 rounded-lg flex items-center justify-center">
            <i class="bi bi-check-circle-fill text-success-600 text-sm"></i>
        </div>
        <div>
            <div class="text-xs text-dark-500 font-medium">Label</div>
            <div class="text-xl font-bold text-dark-900">{{ value }}</div>
        </div>
    </div>
</div>
```

#### Professional Table
```html
<div class="bg-white rounded-lg shadow-md overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-100 border-b border-gray-200">
            <tr>
                <th class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase">
                    Column
                </th>
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
            <tr class="hover:bg-gray-50 transition-colors">
                <td class="px-4 py-3 text-sm text-gray-700">Data</td>
            </tr>
        </tbody>
    </table>
</div>
```

---

## Testing Checklist

### Functional Testing

- [ ] User login/logout
- [ ] Password reset flow
- [ ] Consumer CRUD operations
- [ ] Meter reading submission (web)
- [ ] Meter reading submission (mobile app)
- [ ] Reading confirmation
- [ ] Bill generation
- [ ] Payment recording
- [ ] Bill inquiry
- [ ] Report generation
- [ ] Search and filters
- [ ] AJAX endpoints

### UI/UX Testing

- [ ] Responsive design (mobile, tablet, desktop)
- [ ] Navigation functionality
- [ ] Dropdown menus
- [ ] Form validation
- [ ] Error messages
- [ ] Success messages
- [ ] Chart rendering
- [ ] Table sorting
- [ ] Modal dialogs
- [ ] Loading states

### Security Testing

- [ ] Authentication required
- [ ] Role-based access control
- [ ] CSRF protection
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] Secure password storage
- [ ] Session management
- [ ] API authentication

---

## Maintenance & Support

### Regular Tasks

#### Daily
- Monitor system uptime
- Check error logs
- Verify meter reading submissions

#### Weekly
- Review unconfirmed readings
- Check overdue bills
- Generate weekly reports

#### Monthly
- Database backup
- Generate monthly reports
- Review user accounts
- Clear old sessions

### Backup Strategy

```bash
# Database backup
pg_dump -h localhost -U postgres waterworks > backup_$(date +%Y%m%d).sql

# Media files backup
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/

# Transfer to remote storage
scp backup_*.sql user@backup-server:/backups/
```

### Troubleshooting Guide

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Login fails | Incorrect credentials | Reset password |
| Dropdown not working | JavaScript error | Clear browser cache |
| Charts not loading | Chart.js not loaded | Check CDN connection |
| Bill not generating | Reading not confirmed | Confirm reading first |
| Payment not recorded | Form validation error | Check required fields |
| Internal server error | Template/view error | Check error logs |

---

## Future Enhancements

### Planned Features

1. **SMS Notifications**
   - Bill reminders
   - Payment confirmations
   - Disconnection notices

2. **Online Payment Gateway**
   - GCash integration
   - PayMaya integration
   - Bank transfer API

3. **Advanced Analytics**
   - Consumption forecasting
   - Revenue projections
   - Water loss detection

4. **Mobile App Enhancements**
   - Offline mode
   - Photo attachments
   - GPS location tracking

5. **Customer Portal**
   - Online bill viewing
   - Payment history
   - Consumption graphs
   - Service requests

6. **Automated Reminders**
   - Email notifications
   - SMS alerts
   - Due date reminders

---

## Contact & Support

**Project Repository**: https://github.com/balilihanwaterworks/waterworksbalilihan
**Production URL**: https://waterworks-rose.onrender.com/
**Deployment Platform**: Render

### Development Team

- **Backend Development**: Django 5.2.7
- **Frontend Design**: Tailwind CSS + Bootstrap Icons
- **Database**: PostgreSQL
- **Deployment**: Render

---

## Version History

| Version | Date | Description | Commit |
|---------|------|-------------|--------|
| 1.0.0 | 2025-01 | Initial deployment | - |
| 1.1.0 | 2025-11-15 | Connected Consumers redesign | 456bc48 |
| 1.1.1 | 2025-11-16 | Fix dropdown functionality | 4571825 |
| 1.2.0 | 2025-11-17 | Dashboard with charts | 3870855 |
| 1.2.1 | 2025-11-18 | Bill Inquiry redesign | ae11938 |
| 1.3.0 | 2025-11-19 | Minimal dashboard redesign | 11b64ce |
| 1.3.1 | 2025-11-20 | Minimal Bill Inquiry | 6828b8f |
| 1.3.2 | 2025-11-21 | Fix meter reading overview | e56098a |

---

## Appendix

### A. Database Queries

#### Get Active Consumers
```sql
SELECT * FROM consumers_consumer
WHERE status_id = (SELECT id FROM consumers_consumerstatus WHERE name = 'Active');
```

#### Monthly Revenue
```sql
SELECT SUM(amount_paid) as total_revenue
FROM consumers_payment
WHERE EXTRACT(MONTH FROM payment_date) = EXTRACT(MONTH FROM CURRENT_DATE);
```

#### Unconfirmed Readings
```sql
SELECT * FROM consumers_meterreading
WHERE is_confirmed = FALSE
ORDER BY reading_date DESC;
```

### B. Useful Commands

```bash
# Run development server
python manage.py runserver

# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test

# Check deployment
python manage.py check --deploy

# Git commands
git add .
git commit -m "message"
git push origin main
```

### C. Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Esc` | Close dropdown menu |
| `Enter` | Submit form |
| `Tab` | Navigate fields |
| `Ctrl+S` | Save (in editors) |

---

**Document Version**: 1.0
**Last Updated**: 2025-11-21
**Status**: Complete

---

*This documentation covers the complete Balilihan Waterworks Management System including all recent updates, database schema, features, workflows, and deployment configuration.*
