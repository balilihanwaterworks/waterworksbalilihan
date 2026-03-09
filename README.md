# Balilihan Waterworks Management System

A comprehensive water utility management system with web portal, mobile app integration, and enterprise-grade security features.

[![Django](https://img.shields.io/badge/Django-5.2.7-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Deployed on Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black.svg)](https://vercel.com/)
[![Database](https://img.shields.io/badge/Database-Neon%20PostgreSQL-green.svg)](https://neon.tech/)

---

## Project Overview

**Type:** Water Utility Management System
**Technology Stack:** Django (Backend) + Neon PostgreSQL (Database) + Android (Mobile)
**Deployment:** Vercel (PaaS) + Neon (Serverless PostgreSQL)
**Security Level:** Enterprise-Grade
**Live URL:** https://waterworks-rose.vercel.app

---

## Features

### Core Functionality
- **Consumer Management** - CRUD operations for water consumers
- **Meter Reading** - Web and mobile meter reading submission
- **Automated Billing** - Generate bills from confirmed readings
- **Payment Processing** - Track payments with OR generation
- **Late Payment Penalty System** - Configurable penalties with grace period and waiver
- **Reports & Analytics** - Revenue, delinquency, and summary reports

### Late Payment Penalty System (v2.0)
- **Flexible Penalty Types** - Percentage-based or fixed amount penalties
- **Grace Period** - Configurable grace period before penalties apply
- **Maximum Cap** - Set maximum penalty amount to protect consumers
- **Admin Waiver** - Authorized staff can waive penalties with audit trail
- **Payment History** - Track all payments with penalty status
- **Real-time Calculation** - Automatic penalty calculation on payment inquiry

### Security Features
- **Enhanced Login Tracking** - IP address, device, and session tracking
- **Admin Verification** - Two-step authentication for sensitive operations
- **Role-Based Access Control** - Superuser, Admin, Field Staff roles
- **Password Strength Validation** - Enforce strong password policies
- **Login History Dashboard** - Monitor all access attempts
- **Audit Trail** - Complete activity logging

### Mobile Integration
- **Android App API** - RESTful API for mobile app
- **CORS Enabled** - Cross-origin support for mobile
- **Session Management** - Secure mobile authentication
- **Real-time Sync** - Data sync between web and mobile

---

## Quick Start

### Local Development

1. **Clone Repository**
   ```bash
   git clone https://github.com/balilihanwaterworks/waterworksbalilihan.git
   cd waterworks
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create Superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

8. **Access Application**
   - Web: http://localhost:8000
   - Admin: http://localhost:8000/admin/

---

## Vercel + Neon Deployment

### Prerequisites
- GitHub account
- Vercel account (sign up for free at https://vercel.com)
- Neon account (sign up for free at https://neon.tech)
- Your project code ready

### Deployment Steps

See **[VERCEL_DEPLOYMENT_GUIDE.md](VERCEL_DEPLOYMENT_GUIDE.md)** for complete step-by-step instructions.

**Quick Overview:**
1. Create Neon PostgreSQL database
2. Push code to GitHub
3. Import project to Vercel from GitHub repo
4. Set environment variables in Vercel dashboard
5. Deploy automatically
6. Run migrations via Vercel CLI or locally
7. Test and verify

### Environment Variables (Vercel Dashboard)

```bash
# Security
SECRET_KEY=your-secret-key-here
DEBUG=False

# Hosts
ALLOWED_HOSTS=.vercel.app,waterworks-rose.vercel.app

# Database (from Neon dashboard)
DATABASE_URL=postgresql://user:password@host/database?sslmode=require

# CORS (for Android app)
CORS_ALLOWED_ORIGINS=https://waterworks-rose.vercel.app
CSRF_TRUSTED_ORIGINS=https://waterworks-rose.vercel.app

# Email (for password reset)
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

---

## Project Structure

```
waterworks/
├── consumers/              # Main Django app
│   ├── models.py          # Database models
│   ├── views.py           # Business logic (3200+ lines)
│   ├── utils.py           # Utility functions (penalty calculation)
│   ├── decorators.py      # Security decorators
│   ├── urls.py            # URL routing
│   ├── forms.py           # Django forms
│   ├── templates/         # HTML templates
│   └── static/            # CSS, JS, images
├── waterworks/            # Django project settings
│   ├── settings.py        # Configuration
│   ├── urls.py            # Main URL config
│   └── wsgi.py            # WSGI config
├── requirements.txt       # Python dependencies
├── vercel.json           # Vercel configuration
├── build_files.sh        # Vercel build script
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

---

## Database Models

- **Consumer** - Water consumer information
- **Bill** - Monthly water bills
- **Payment** - Payment records with OR
- **MeterReading** - Meter readings (web + mobile)
- **UserLoginEvent** - Login tracking with security info
- **Barangay** - Area management
- **Purok** - Sub-area management
- **StaffProfile** - Staff assignments
- **SystemSetting** - Water rates and penalty configuration

---

## User Roles

| Role | Access Level | Capabilities |
|------|--------------|--------------|
| **Superuser** | Full System | User management, system settings, all features |
| **Admin** | Elevated | Reports, login history, consumer management |
| **Field Staff** | Standard | Meter readings for assigned barangay |
| **Regular User** | Basic | Login only |

---

## API Endpoints

### Authentication
- `POST /api/login/` - Mobile login with tracking

### Data Access
- `GET /api/consumers/` - Get consumers for assigned barangay
- `POST /api/meter-readings/` - Submit meter reading
- `GET /api/rates/` - Get current water rates

### Response Format
```json
{
  "status": "success",
  "token": "session-key",
  "barangay": "Centro",
  "user": {
    "username": "fieldstaff1",
    "full_name": "Juan Dela Cruz"
  }
}
```

---

## Android App Integration

1. Update base URL in your Android app:
   ```java
   String BASE_URL = "https://waterworks-rose.vercel.app";
   ```

2. Update all API endpoints to use HTTPS

3. **Note:** Vercel free tier has cold start delays (3-10 seconds on first request after inactivity)

4. Test connectivity:
   - Login API
   - Consumer list
   - Meter reading submission

See **[ANDROID_APP_VERCEL_SETUP.md](ANDROID_APP_VERCEL_SETUP.md)** for details.

---

## Testing

### Run Tests
```bash
python manage.py test consumers
```

### Manual Testing Checklist
- [ ] Login with different user roles
- [ ] Consumer CRUD operations
- [ ] Meter reading submission
- [ ] Bill generation
- [ ] Payment processing
- [ ] Late payment penalty calculation
- [ ] Penalty waiver (admin only)
- [ ] Payment history with filters
- [ ] Report generation
- [ ] API endpoints
- [ ] Security features

---

## Reports

### Available Reports
1. **Revenue Report** - All payments for a period
2. **Delinquency Report** - Unpaid bills
3. **Payment Summary** - Consumer payment totals
4. **Payment History** - All payments with penalty tracking

### Export Formats
- Excel (.xlsx) with formatting
- CSV for data processing

---

## Security Features

### Authentication & Authorization
- Session-based authentication
- Role-based access control
- Admin verification for sensitive operations
- Password strength validation

### Tracking & Monitoring
- IP address logging
- Device/browser tracking
- Login method tracking (web/mobile)
- Failed login attempt monitoring
- Session duration tracking

### Data Protection
- HTTPS enforced in production
- Secure cookie settings
- CSRF protection
- XSS protection
- SQL injection prevention (Django ORM)

---

## Documentation

- **[docs/PROGRAM_HIERARCHY.md](docs/PROGRAM_HIERARCHY.md)** - Complete system hierarchy and architecture
- **[docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md)** - Technical architecture documentation
- **[docs/SYSTEM_FLOW.md](docs/SYSTEM_FLOW.md)** - Business process workflows
- **[DATABASE_DOCUMENTATION.md](DATABASE_DOCUMENTATION.md)** - Database schema and models
- **[VERCEL_DEPLOYMENT_GUIDE.md](VERCEL_DEPLOYMENT_GUIDE.md)** - Complete deployment guide
- **[DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)** - Changes and configuration summary
- **[FINAL_IMPLEMENTATION_SUMMARY.md](FINAL_IMPLEMENTATION_SUMMARY.md)** - Feature overview
- **[SECURITY_FEATURES_THESIS_DEFENSE.md](SECURITY_FEATURES_THESIS_DEFENSE.md)** - Security documentation
- **[ANDROID_APP_VERCEL_SETUP.md](ANDROID_APP_VERCEL_SETUP.md)** - Mobile app guide

---

## Maintenance

### View Logs (Vercel)
- Go to Vercel Dashboard → Your Project → Deployments → View Logs
- Or use Vercel CLI: `vercel logs`

### Database Access (Neon)
- Go to Neon Dashboard → Your Project → SQL Editor
- Or connect via psql with your connection string

### Update Application
```bash
git add .
git commit -m "Update: description"
git push  # Vercel auto-deploys from main branch
```

---

## Troubleshooting

### Common Issues

**Build Fails on Vercel**
- Check `requirements.txt` syntax
- View build logs in Vercel dashboard
- Ensure Python 3.11 compatibility

**Static Files Not Loading**
- Verify `build_files.sh` runs collectstatic
- Check WhiteNoise middleware configuration

**Database Connection Error**
- Verify `DATABASE_URL` in Vercel environment variables
- Ensure Neon database is active (check for sleep mode)
- Add `?sslmode=require` to connection string

**CORS Errors from Mobile**
- Add Vercel domain to `CORS_ALLOWED_ORIGINS`
- Check `corsheaders` in `INSTALLED_APPS`

**Cold Start Delays**
- Expected behavior on Vercel free tier (3-10 seconds)
- Consider upgrading for always-on performance

See **VERCEL_DEPLOYMENT_GUIDE.md** for more troubleshooting.

---

## Cost

### Vercel Free Tier (Hobby)
- **Unlimited deployments**
- **100 GB bandwidth/month**
- **Serverless function execution limits**
- Perfect for testing and demos

### Neon Free Tier
- **0.5 GB storage**
- **Branching and autoscaling**
- **Auto-suspend after 5 minutes of inactivity**
- Perfect for development and small projects

### Upgrade When Needed
- Vercel Pro: $20/month (team features, more resources)
- Neon Pro: Starting at $19/month (more storage, no auto-suspend)

---

## For Thesis Defense

### Demo Preparation
1. Ensure Vercel app is deployed and running
2. Test all features beforehand (account for cold starts)
3. Prepare live demo script
4. Have backup screenshots/video
5. Test from multiple devices

### Key Highlights
- Cloud-based deployment (Vercel + Neon)
- Enterprise-grade security
- Mobile integration
- Real-time data sync
- Scalable architecture

---

## Support

### Project Documentation
- See `/docs` folder for detailed guides
- Check `DEPLOYMENT_SUMMARY.md` for changes
- Read `SECURITY_FEATURES_THESIS_DEFENSE.md` for security details

### Platform Resources
- [Vercel Documentation](https://vercel.com/docs)
- [Neon Documentation](https://neon.tech/docs)
- [Django on Vercel Guide](https://vercel.com/templates/python/django-hello-world)

---

## License

This project is developed for educational purposes as part of a thesis/research project.

---

## Acknowledgments

- Django Framework
- Vercel Platform
- Neon PostgreSQL
- WhiteNoise (Static Files)
- OpenPyXL (Excel Export)

---

## Project Statistics

- **Total Code:** ~3,500 lines Python + templates
- **Database Models:** 11
- **Web Views:** 45+ functions
- **API Endpoints:** 4
- **Security Features:** 8 major implementations
- **Penalty System:** Complete with waiver audit trail
- **User Roles:** 4 levels
- **Templates:** 35+ HTML pages

---

## Status

**Development:** Complete
**Testing:** Verified
**Documentation:** Complete
**Deployment:** Production Ready
**Security:** Enterprise-Grade
**Thesis Defense:** Ready

---

**System Status:** PRODUCTION READY
**Platform:** Vercel + Neon PostgreSQL
**Live URL:** https://waterworks-rose.vercel.app
**Last Updated:** November 2025

---

*Developed for Balilihan Waterworks Management*
*Built with Django - Deployed on Vercel - Powered by Neon PostgreSQL*
