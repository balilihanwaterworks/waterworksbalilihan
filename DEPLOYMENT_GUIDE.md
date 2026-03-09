# APPENDIX D
# User's Guide

This guide provides detailed steps to setup and deploy the Balilihan Waterworks Management System, developed using Python programming language, Django framework, and PostgreSQL database.

**Live Production System**: https://waterworksbalilihan.onrender.com

---

## 1. Prerequisites

Before proceeding, ensure you have the following:

- **Source Code**: The complete project files for the Balilihan Waterworks Management System.
- **Technical Knowledge**: Basic familiarity with Python, command-line interfaces (CMD/Terminal), and Django is recommended.
- **Internet Connection**: Required to download Python packages and dependencies.

---

## 2. System Requirements

### 2.1 Hardware Requirements

- **Processor**: Intel Core i3 / AMD Ryzen 3 or higher.
- **RAM**: 4GB or more (8GB recommended).
- **Storage**: 120GB HDD / SSD or larger (SSD recommended for faster performance).

### 2.2 Software Requirements

- **Operating System**: Windows 10/11, MacOS, or Linux.
- **Language Runtime**: Python Version 3.8 or higher.
- **Package Manager**: pip (usually installed automatically with Python).
- **Web Browser**: Google Chrome, Mozilla Firefox, or Microsoft Edge.
- **Database**: SQLite3 (Default) or PostgreSQL (Production).

---

## 3. Setting Up the Environment

### 3.1 Install Python

1. Download the latest version of Python from the official website:
   https://www.python.org/downloads/

2. Run the installer. **Important**: Ensure you check the box that says "Add Python to PATH" before clicking "Install Now."

3. Verify installation by opening a command prompt (CMD) and typing:
   ```
   python --version
   ```

### 3.2 Install Virtual Environment Tool (Optional but Recommended)

It is best practice to run Django projects inside a virtual environment to isolate dependencies.

1. Open your command prompt or terminal.

2. Install the virtual environment package:
   ```
   pip install virtualenv
   ```

---

## 4. Deploying the Application

### 4.1 Extract the Source Code

1. Download the source code (ZIP file) or clone it from the repository:
   ```
   git clone https://github.com/balilihanwaterworks/waterworksbalilihan.git
   ```

2. Extract the folder to your desired location (e.g., C:\Users\YourName\Documents\waterworks).

### 4.2 Setup Virtual Environment & Install Dependencies

1. Open a terminal or command prompt.

2. Navigate to the project directory:
   ```
   cd path/to/waterworks
   ```

3. Create a virtual environment:
   ```
   python -m venv venv
   ```

4. Activate the virtual environment:
   - **Windows**: `venv\Scripts\activate`
   - **Mac/Linux**: `source venv/bin/activate`

5. Install the required dependencies listed in requirements.txt:
   ```
   pip install -r requirements.txt
   ```

### 4.3 Setup the Environment File

1. Duplicate the `.env.example` file and rename it to `.env`

2. If no example exists, create a new file named `.env` and add your secret configurations:
   ```
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   DATABASE_URL=postgresql://user:password@host:port/database
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-app-password
   ```

---

## 5. Configuring the Database

### 5.1 Run Migrations

Since the system uses PostgreSQL for production, ensure your database connection is configured in the `.env` file.

1. In your terminal (with the virtual environment active), run the following command to set up the database tables:
   ```
   python manage.py migrate
   ```

### 5.2 Create an Administrator Account

To access the admin panel, you need a superuser account.

1. Run the command:
   ```
   python manage.py createsuperuser
   ```

2. Enter a username, email, and password when prompted.

---

## 6. Running the Application

### 6.1 Start the Development Server

1. Ensure you are still in the project directory with your virtual environment activated.

2. Run the Django development server:
   ```
   python manage.py runserver
   ```

### 6.2 Access the System

1. Open your web browser.

2. Navigate to the following URL:
   ```
   http://127.0.0.1:8000/
   ```

3. To access the admin panel, navigate to:
   ```
   http://127.0.0.1:8000/admin/
   ```

---

## 7. Troubleshooting

### 7.1 Common Issues

**• Python is not recognized as an internal or external command**

**Solution:**
- You likely forgot to check "Add Python to PATH" during installation. Reinstall Python and ensure that box is checked, or manually add Python to your system variables.

**• ModuleNotFoundError: No module named 'django'**

**Solution:**
- The dependencies are not installed. Ensure your virtual environment is activated (you should see (venv) in your terminal prompt) and run `pip install -r requirements.txt` again.

**• OperationalError: no such table**

**Solution:**
- The database migrations have not been applied. Run `python manage.py migrate` to fix this.

**• Port already in use**

**Solution:**
- Another instance of the server is running. Close other terminal windows or run the server on a different port using:
  ```
  python manage.py runserver 8081
  ```

**• SMTPAuthenticationError: Username and Password not accepted**

**Solution:**
- You are using your regular Gmail password instead of an App Password. Generate a 16-character App Password from your Google Account Security settings.

---

## 8. Advanced Setup: Configuring PostgreSQL (Production)

While SQLite3 can be used for development, a production environment requires PostgreSQL. The system is pre-configured to use PostgreSQL via Neon (cloud hosting).

### 8.1 Using Neon PostgreSQL (Recommended)

1. Create a free account at https://neon.tech/

2. Create a new project named "Balilihan Waterworks"

3. Copy the connection string provided by Neon

4. Paste it into your `.env` file:
   ```
   DATABASE_URL=postgresql://user:password@host.neon.tech/balilihan_waterworks
   ```

### 8.2 Using Local PostgreSQL

1. Download and install PostgreSQL from https://www.postgresql.org/download/

2. During installation, remember the superuser password you set; you will need this later.

3. Install pgAdmin (usually included in the installer) to manage your database visually.

### 8.3 Install Python Database Adapter

Django requires a specific driver to communicate with PostgreSQL.

1. Open your terminal with the virtual environment activated.

2. Install the psycopg2 binary package:
   ```
   pip install psycopg2-binary
   ```

### 8.4 Create the Database

1. Open pgAdmin.

2. Right-click on Databases > Create > Database.

3. Name the database (e.g., `balilihan_waterworks`) and click Save.

### 8.5 Update Configuration

1. Open the `.env` file in your project directory.

2. Update the DATABASE_URL or specific database variables to match your PostgreSQL credentials:
   ```
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/balilihan_waterworks
   ```

   Or using individual variables:
   ```
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=balilihan_waterworks
   DB_USER=postgres
   DB_PASSWORD=your_password_here
   DB_HOST=localhost
   DB_PORT=5432
   ```

### 8.6 Apply Migrations to New Database

Since this is a fresh database, you must recreate the tables.

1. In the terminal, run:
   ```
   python manage.py migrate
   ```

2. Create a new superuser for this production database:
   ```
   python manage.py createsuperuser
   ```

---

## 9. Gmail Email Configuration (Password Reset)

The system sends password reset emails using Gmail SMTP.

### 9.1 Generate Gmail App Password

1. Go to your Google Account: https://myaccount.google.com/

2. Navigate to **Security** → **2-Step Verification** (enable if not already enabled)

3. Go back to **Security** → **App passwords**

4. Select app: **Mail**, Select device: **Other (Custom name)**

5. Enter "Balilihan Waterworks" and click Generate

6. Copy the 16-character app password (remove spaces)

### 9.2 Update .env File

```
EMAIL_HOST_USER=balilihanwaterworks@gmail.com
EMAIL_HOST_PASSWORD=abcdefghijklmnop
DEFAULT_FROM_EMAIL=Balilihan Waterworks <noreply@balilihan-waterworks.com>
```

**Important**: Do NOT use your regular Gmail password. Use the 16-character App Password generated above.

---

## 10. Production Deployment (Render)

The system is deployed on Render at: https://waterworksbalilihan.onrender.com

### 10.1 Prepare for Deployment

1. Update `.env` file:
   ```
   DEBUG=False
   ALLOWED_HOSTS=waterworksbalilihan.onrender.com
   CORS_ALLOWED_ORIGINS=https://waterworksbalilihan.onrender.com
   CSRF_TRUSTED_ORIGINS=https://waterworksbalilihan.onrender.com
   ```

2. Collect static files:
   ```
   python manage.py collectstatic --noinput
   ```

### 10.2 Deploy to Render

1. Create a Render account at https://render.com

2. Create a new **Web Service**

3. Connect your GitHub repository: https://github.com/balilihanwaterworks/waterworksbalilihan

4. Configure build settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn waterworks.wsgi:application`

5. Add environment variables from your `.env` file

6. Deploy the application

### 10.3 Post-Deployment Tasks

1. Run migrations on production via Render shell:
   ```
   python manage.py migrate
   ```

2. Create production superuser:
   ```
   python manage.py createsuperuser
   ```

---

## 11. System Features Overview

The Balilihan Waterworks Management System includes:

- **Consumer Management**: Register and manage water consumers
- **Meter Reading System**: Field staff mobile app with OCR scanning
- **Billing Management**: Automated bill generation based on consumption
- **Payment Processing**: Record payments with official receipt numbers
- **Reporting System**: Revenue reports, payment summaries, delinquent accounts
- **User Management**: Role-based access (Administrator, Office Staff, Field Staff, Treasurer)
- **Mobile App Integration**: React Native app for field meter reading

---

## 12. Support

For further assistance, technical support, or bug reports, please contact the development team:

**Email**: balilihanwaterworks6342@gmail.com

**GitHub Repository**: https://github.com/balilihanwaterworks/waterworksbalilihan

For framework-specific documentation, consult the Django official guide at:
https://docs.djangoproject.com/en/5.2/

---

**Document Version**: 1.0
**Last Updated**: January 19, 2026
**System Version**: Django 5.2.7
