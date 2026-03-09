# Balilihan Waterworks Management System
## User's Guide & Deployment Manual

This guide provides detailed steps to setup, deploy, and maintain the Balilihan Waterworks Management System, developed using Python programming language, Django framework, and PostgreSQL database.

**Live Production System**: [https://waterworksbalilihan.onrender.com](https://waterworksbalilihan.onrender.com)

---

## 1. Prerequisites

Before proceeding, ensure you have the following:

- **Source Code**: The complete project files for the Balilihan Waterworks Management System.
- **Technical Knowledge**: Basic familiarity with Python, command-line interfaces (CMD/Terminal), and Django is recommended.
- **Internet Connection**: Required to download Python packages and dependencies.
- **Database Access**: PostgreSQL database (Neon hosted or local PostgreSQL server).
- **Email Account**: Gmail account for password reset functionality.
- **Cloudinary Account** (Optional): For cloud-based proof image storage.

---

## 2. System Requirements

### 2.1 Hardware Requirements

- **Processor**: Intel Core i3 / AMD Ryzen 3 or higher
- **RAM**: 4GB or more (8GB recommended)
- **Storage**: 120GB HDD / SSD or larger (SSD recommended for faster performance)

### 2.2 Software Requirements

- **Operating System**: Windows 10/11, MacOS, or Linux
- **Language Runtime**: Python Version 3.8 or higher (3.11+ recommended)
- **Package Manager**: pip (usually installed automatically with Python)
- **Web Browser**: Google Chrome, Mozilla Firefox, or Microsoft Edge
- **Database**: PostgreSQL 12 or higher (Neon PostgreSQL for cloud hosting)

---

## 3. Setting Up the Environment

### 3.1 Install Python

1. Download the latest version of Python from the official website:
   [https://www.python.org/downloads/](https://www.python.org/downloads/)

2. Run the installer. **Important**: Ensure you check the box that says **"Add Python to PATH"** before clicking "Install Now."

3. Verify installation by opening a command prompt (CMD) and typing:
   ```bash
   python --version
   ```
   You should see output like: `Python 3.11.x`

### 3.2 Install Virtual Environment Tool (Recommended)

It is best practice to run Django projects inside a virtual environment to isolate dependencies.

1. Open your command prompt or terminal.

2. Install the virtual environment package:
   ```bash
   pip install virtualenv
   ```

---

## 4. Deploying the Application

### 4.1 Extract the Source Code

1. Download the source code (ZIP file) or clone it from the repository:
   ```bash
   git clone https://github.com/balilihanwaterworks/waterworksbalilihan.git
   ```

2. Extract the folder to your desired location (e.g., `C:\Users\YourName\Documents\waterworks`).

### 4.2 Setup Virtual Environment & Install Dependencies

1. Open a terminal or command prompt.

2. Navigate to the project directory:
   ```bash
   cd path/to/waterworks
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

4. Activate the virtual environment:
   - **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - **Mac/Linux**:
     ```bash
     source venv/bin/activate
     ```

5. Install the required dependencies listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

### 4.3 Setup the Environment File

1. Duplicate the `.env.example` file and rename it to `.env`:
   ```bash
   copy .env.example .env    # Windows
   cp .env.example .env      # Mac/Linux
   ```

2. Open the `.env` file in a text editor and configure the following:

   **Django Settings:**
   ```
   SECRET_KEY=your-secret-key-here-generate-new-one
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```

   **Database Configuration (Neon PostgreSQL):**
   ```
   DATABASE_URL=postgresql://user:password@host:port/database
   ```
   Example:
   ```
   DATABASE_URL=postgresql://balilihan_user:securePassword123@ep-cool-name-123456.us-east-2.aws.neon.tech/balilihan_waterworks
   ```

   **Email Configuration (Gmail SMTP):**
   ```
   EMAIL_HOST_USER=balilihanwaterworks@gmail.com
   EMAIL_HOST_PASSWORD=your-16-character-app-password
   DEFAULT_FROM_EMAIL=Balilihan Waterworks <noreply@balilihan-waterworks.com>
   ```

   **CORS & CSRF (for Mobile App API):**

   For local development:
   ```
   CORS_ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
   CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
   ```

   For production deployment:
   ```
   CORS_ALLOWED_ORIGINS=https://waterworksbalilihan.onrender.com
   CSRF_TRUSTED_ORIGINS=https://waterworksbalilihan.onrender.com
   ```

   **Cloudinary (Optional - for cloud image storage):**
   ```
   CLOUDINARY_CLOUD_NAME=your-cloud-name
   CLOUDINARY_API_KEY=your-api-key
   CLOUDINARY_API_SECRET=your-api-secret
   ```

---

## 5. Configuring the Database

### 5.1 Database Setup Options

#### Option A: Using Neon PostgreSQL (Recommended for Production)

1. Create a free account at [https://neon.tech/](https://neon.tech/)
2. Create a new project named "Balilihan Waterworks"
3. Copy the connection string provided
4. Paste it into your `.env` file as `DATABASE_URL`

#### Option B: Using Local PostgreSQL

1. Download and install PostgreSQL from [https://www.postgresql.org/download/](https://www.postgresql.org/download/)
2. During installation, remember the superuser password
3. Open pgAdmin and create a new database named `balilihan_waterworks`
4. Update your `.env` file with local connection details

### 5.2 Run Migrations

With your virtual environment active, run the following command to create all database tables:

```bash
python manage.py migrate
```

You should see output indicating successful migrations.

### 5.3 Create an Administrator Account

To access the admin panel, you need a superuser account:

1. Run the command:
   ```bash
   python manage.py createsuperuser
   ```

2. Enter the following when prompted:
   - **Username**: admin (or your preferred username)
   - **Email address**: admin@balilihan-waterworks.com
   - **Password**: Create a strong password
   - **Password (again)**: Confirm your password

### 5.4 Load Initial Data (Optional)

If sample data fixtures are provided, load them with:

```bash
python manage.py loaddata initial_barangays.json
python manage.py loaddata sample_consumers.json
```

---

## 6. Running the Application

### 6.1 Start the Development Server

1. Ensure you are in the project directory with your virtual environment activated.

2. Run the Django development server:
   ```bash
   python manage.py runserver
   ```

3. You should see output like:
   ```
   Starting development server at http://127.0.0.1:8000/
   Quit the server with CTRL-BREAK.
   ```

### 6.2 Access the System

**Main System (Web Application):**
- URL: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Login with the superuser account you created

**Admin Panel:**
- URL: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- Full administrative access to database records

**System Modules:**
- Dashboard: `http://127.0.0.1:8000/consumers/dashboard/`
- Consumer Management: `http://127.0.0.1:8000/consumers/consumers/`
- Meter Readings: `http://127.0.0.1:8000/consumers/meter-readings/`
- Billing Management: `http://127.0.0.1:8000/consumers/bills/`
- Payment Records: `http://127.0.0.1:8000/consumers/payments/`
- Reports: `http://127.0.0.1:8000/consumers/reports/`

---

## 7. Setting Up Gmail for Email Notifications

The system sends password reset emails and notifications. Follow these steps to configure Gmail SMTP:

### 7.1 Create a Gmail App Password

1. Go to your Google Account: [https://myaccount.google.com/](https://myaccount.google.com/)
2. Navigate to **Security** → **2-Step Verification** (enable if not already enabled)
3. Go back to **Security** → **App passwords**
4. Select app: **Mail**, Select device: **Other (Custom name)**
5. Enter "Balilihan Waterworks" as the app name
6. Click **Generate**
7. Copy the 16-character app password (no spaces)
8. Paste it into your `.env` file as `EMAIL_HOST_PASSWORD`

### 7.2 Configure Email Settings

Update your `.env` file:

```env
EMAIL_HOST_USER=balilihanwaterworks@gmail.com
EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop  # Remove spaces: abcdefghijklmnop
DEFAULT_FROM_EMAIL=Balilihan Waterworks <noreply@balilihan-waterworks.com>
```

**Important**: Do NOT use your regular Gmail password - it won't work! Use the 16-character app password generated in the previous step.

---

## 8. Setting Up the Mobile App (Field Staff)

The system includes a React Native mobile app for field staff to capture meter readings on-site.

### 8.1 Mobile App Setup Requirements

- **Node.js**: Version 16 or higher
- **Expo CLI**: For running the React Native app
- **Android Studio** or **Xcode**: For running on emulators

### 8.2 Running the Mobile App

1. Navigate to the mobile app directory (if separate repository).
2. Install dependencies:
   ```bash
   npm install
   ```
3. Update the API base URL to point to your Django server:
   ```javascript
   // config.js or similar
   API_BASE_URL: 'http://192.168.1.100:8000/api/'
   ```
4. Start the Expo development server:
   ```bash
   npx expo start
   ```
5. Scan the QR code with the Expo Go app on your mobile device.

---

## 9. Troubleshooting

### 9.1 Common Issues

**Issue**: `Python is not recognized as an internal or external command`

**Solution**:
- You likely forgot to check "Add Python to PATH" during installation.
- Reinstall Python and ensure that box is checked, or manually add Python to your system variables.

---

**Issue**: `ModuleNotFoundError: No module named 'django'`

**Solution**:
- The dependencies are not installed. Ensure your virtual environment is activated (you should see `(venv)` in your terminal prompt) and run:
  ```bash
  pip install -r requirements.txt
  ```

---

**Issue**: `django.db.utils.OperationalError: no such table`

**Solution**:
- The database migrations have not been applied. Run:
  ```bash
  python manage.py migrate
  ```

---

**Issue**: `Port 8000 already in use`

**Solution**:
- Another instance of the server is running. Close other terminal windows or run the server on a different port:
  ```bash
  python manage.py runserver 8081
  ```

---

**Issue**: `connection to server failed: FATAL: password authentication failed`

**Solution**:
- Your database credentials in the `.env` file are incorrect.
- Double-check your `DATABASE_URL` string.
- For Neon PostgreSQL, copy the connection string exactly as provided by Neon.

---

**Issue**: `SMTPAuthenticationError: Username and Password not accepted`

**Solution**:
- You are using your regular Gmail password instead of an App Password.
- Follow the Gmail setup instructions in Section 7 to generate a 16-character App Password.

---

**Issue**: `Cloudinary package not installed. Proof image uploads will not work.`

**Solution**:
- This is a warning, not an error. The system will still work but images won't be stored in the cloud.
- To enable cloud storage, install Cloudinary:
  ```bash
  pip install cloudinary
  ```
- Configure Cloudinary credentials in your `.env` file.

---

## 10. User Roles and Access Levels

The system has four distinct user roles:

### 10.1 Administrator
- **Access**: Full system access
- **Capabilities**:
  - User management
  - Consumer management (add, edit, delete)
  - Billing and payment management
  - System reports and analytics
  - System configuration

### 10.2 Office Staff
- **Access**: Office operations
- **Capabilities**:
  - View and manage consumers
  - Create and manage bills
  - Process payments
  - Generate reports
  - Confirm meter readings

### 10.3 Field Staff
- **Access**: Mobile app only (no web access)
- **Capabilities**:
  - Capture meter readings via mobile app
  - Upload proof photos
  - View assigned routes
  - Submit readings for approval

### 10.4 Treasurer
- **Access**: Financial management
- **Capabilities**:
  - View payment records
  - Generate financial reports
  - Export revenue reports
  - Monitor collections

---

## 11. System Features Overview

### 11.1 Dashboard
- Real-time statistics and KPIs
- Recent activities
- Pending approvals
- Revenue overview

### 11.2 Consumer Management
- Add/edit/archive consumer records
- Assign ID numbers
- Track consumer status
- View consumption history

### 11.3 Meter Reading System
- Mobile app integration for field staff
- OCR scanning support
- Manual entry backup
- Photo proof requirement
- Approval workflow

### 11.4 Billing Management
- Automated bill generation
- Consumption-based pricing
- Due date tracking
- Bill status monitoring
- Penalty calculation

### 11.5 Payment Processing
- Record payments with OR numbers
- Multiple payment methods
- Receipt generation
- Payment history tracking

### 11.6 Reporting System
- Revenue reports (detailed and by barangay)
- Payment summaries
- Delinquent accounts
- Excel export functionality
- Print-friendly formats

---

## 12. Production Deployment (Render)

For deploying to a production environment on Render:

### 12.1 Prepare for Deployment

1. Update `.env` file:
   ```env
   DEBUG=False
   ALLOWED_HOSTS=waterworksbalilihan.onrender.com
   CORS_ALLOWED_ORIGINS=https://waterworksbalilihan.onrender.com
   CSRF_TRUSTED_ORIGINS=https://waterworksbalilihan.onrender.com
   ```

2. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

### 12.2 Deploy to Render

1. Create a Render account at [https://render.com](https://render.com)
2. Create a new **Web Service**
3. Connect your GitHub repository
4. Configure build settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn waterworks.wsgi:application`
5. Add environment variables from your `.env` file
6. Deploy!

### 12.3 Post-Deployment Tasks

1. Run migrations on production:
   ```bash
   python manage.py migrate
   ```

2. Create production superuser:
   ```bash
   python manage.py createsuperuser
   ```

---

## 13. Maintenance and Updates

### 13.1 Regular Backups

**Database Backup (Neon):**
- Neon provides automatic backups
- Manual backup: Use pgAdmin to export database

**Local Backup:**
```bash
python manage.py dumpdata > backup_$(date +%Y%m%d).json
```

### 13.2 Updating the System

1. Pull latest changes from repository:
   ```bash
   git pull origin main
   ```

2. Activate virtual environment and update dependencies:
   ```bash
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt --upgrade
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

4. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

5. Restart the server

---

## 14. Support and Contact

For further assistance, technical support, or bug reports, please contact:

**Email**: balilihanwaterworks6342@gmail.com
**GitHub Repository**: [https://github.com/balilihanwaterworks/waterworksbalilihan](https://github.com/balilihanwaterworks/waterworksbalilihan)

**Framework Documentation:**
- Django Official Guide: [https://docs.djangoproject.com/en/5.2/](https://docs.djangoproject.com/en/5.2/)
- Python Documentation: [https://docs.python.org/3/](https://docs.python.org/3/)
- Neon PostgreSQL: [https://neon.tech/docs/introduction](https://neon.tech/docs/introduction)

---

## 15. Appendix

### 15.1 Generate Secret Key

To generate a new Django secret key:

```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 15.2 System File Structure

```
waterworks/
├── consumers/              # Main application module
│   ├── models.py          # Database models
│   ├── views.py           # Business logic
│   ├── urls.py            # URL routing
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JS, images
│   └── migrations/        # Database migrations
├── waterworks/            # Project settings
│   ├── settings.py        # Django configuration
│   ├── urls.py            # Main URL routing
│   └── wsgi.py            # WSGI entry point
├── requirements.txt       # Python dependencies
├── manage.py              # Django management script
├── .env                   # Environment variables
├── .env.example           # Environment template
└── USER_GUIDE.md          # This guide
```

### 15.3 Database Schema Overview

**Core Models:**
- `Barangay` - Geographic locations
- `Consumer` - Water service subscribers
- `MeterReading` - Recorded meter values
- `Bill` - Generated billing statements
- `Payment` - Payment transactions
- `User` - System users (staff, admin)

---

**Document Version**: 1.0
**Last Updated**: January 19, 2026
**System Version**: Django 5.2.7

---

*This guide is provided as-is for the Balilihan Waterworks Management System. For the latest updates and documentation, please refer to the official repository.*
