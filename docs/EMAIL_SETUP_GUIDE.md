# EMAIL CONFIGURATION GUIDE
## Gmail SMTP Setup for Password Reset Functionality

**Balilihan Waterworks Management System**
**Date:** November 25, 2025
**Feature:** Secure Password Reset via Email

---

## TABLE OF CONTENTS

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Gmail App Password Setup](#gmail-app-password-setup)
4. [Environment Configuration](#environment-configuration)
5. [Testing Email Functionality](#testing-email-functionality)
6. [Troubleshooting](#troubleshooting)
7. [Security Best Practices](#security-best-practices)

---

## OVERVIEW

The Balilihan Waterworks system uses Gmail's SMTP server to send password reset tokens securely to users' registered email addresses. This ensures that only the account owner can reset their password.

### **Why Gmail App Passwords?**

- 🔒 **More Secure:** App passwords are 16-character codes separate from your Google account password
- ⚡ **Modern Authentication:** Works with Google's 2-Step Verification
- 🛡️ **Revocable:** Can be revoked anytime without changing your main password
- ✅ **Recommended by Google:** Official method for third-party app access

### **How It Works**

```
User requests password reset
         ↓
System generates secure token
         ↓
Email sent via Gmail SMTP
         ↓
User receives email with reset link
         ↓
User clicks link (valid 24 hours)
         ↓
User creates new password
```

---

## PREREQUISITES

Before setting up email functionality, ensure you have:

- ✅ A Gmail account (create a dedicated one for the system)
- ✅ 2-Step Verification enabled on the Gmail account
- ✅ Access to the server's .env file
- ✅ Basic understanding of environment variables

**Recommended:** Create a dedicated Gmail account like `balilihanwaterworks@gmail.com` instead of using a personal account.

---

## GMAIL APP PASSWORD SETUP

### **Step 1: Enable 2-Step Verification**

1. Go to your Google Account: https://myaccount.google.com/
2. Click **Security** in the left sidebar
3. Under "Signing in to Google," click **2-Step Verification**
4. Follow the prompts to enable 2-Step Verification
5. Choose your preferred method (phone, authenticator app, etc.)

**Screenshot Guidance:**
```
Google Account → Security → 2-Step Verification → Turn On
```

### **Step 2: Generate App Password**

1. After enabling 2-Step Verification, go back to **Security**
2. Scroll to "Signing in to Google"
3. Click **App passwords** (appears only after 2-Step Verification is enabled)
4. You may need to re-enter your Google password

**If you don't see "App passwords":**
- Ensure 2-Step Verification is enabled
- Wait a few minutes and refresh the page
- Make sure you're signed in with the correct account

### **Step 3: Create the App Password**

1. On the App passwords page:
   - **Select app:** Choose "Mail"
   - **Select device:** Choose "Other (Custom name)"

2. Enter a custom name: `Balilihan Waterworks`

3. Click **Generate**

4. Google will display a 16-character password like this:
   ```
   abcd efgh ijkl mnop
   ```

5. **IMPORTANT:** Copy this password immediately
   - Remove all spaces: `abcdefghijklmnop`
   - You won't be able to see it again
   - Store it securely

6. Click **Done**

### **Visual Guide**

```
┌─────────────────────────────────────────────────────────────┐
│  App passwords                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Select app:  [Mail ▼]                                     │
│                                                             │
│  Select device: [Other (Custom name) ▼]                    │
│                                                             │
│  Enter name: [Balilihan Waterworks        ]                │
│                                                             │
│              [ GENERATE ]                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

After clicking Generate:

┌─────────────────────────────────────────────────────────────┐
│  Your app password for Balilihan Waterworks                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    abcd efgh ijkl mnop                                     │
│                                                             │
│  This password lets Balilihan Waterworks access your       │
│  Google Account. Don't share it with anyone.               │
│                                                             │
│              [ DONE ]                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ENVIRONMENT CONFIGURATION

### **Step 4: Update Environment Variables**

#### **For Local Development (.env file)**

1. Navigate to your project directory:
   ```bash
   cd D:\balilihan_waterworks\waterworks
   ```

2. Create or edit the `.env` file:
   ```bash
   notepad .env
   ```

3. Add the following lines (replace with your actual values):
   ```env
   # Email Configuration
   EMAIL_HOST_USER=your-gmail-address@gmail.com
   EMAIL_HOST_PASSWORD=abcdefghijklmnop
   DEFAULT_FROM_EMAIL=Balilihan Waterworks <noreply@balilihan-waterworks.com>
   ```

4. Save and close the file

**Example:**
```env
# Email Configuration
EMAIL_HOST_USER=balilihanwaterworks@gmail.com
EMAIL_HOST_PASSWORD=xkcd1234abcd5678
DEFAULT_FROM_EMAIL=Balilihan Waterworks <noreply@balilihan-waterworks.com>
```

#### **For Production (Render)**

1. Go to your Render dashboard: https://dashboard.render.com
2. Click on your web service
3. Navigate to **Environment** tab
4. Click **Add Environment Variable**
5. Add the following variables one by one:

| Variable Name | Example Value |
|---------------|---------------|
| `EMAIL_HOST_USER` | `balilihanwaterworks@gmail.com` |
| `EMAIL_HOST_PASSWORD` | `abcdefghijklmnop` |
| `DEFAULT_FROM_EMAIL` | `Balilihan Waterworks <noreply@balilihan-waterworks.com>` |

6. Click **Save Changes**
7. Render will automatically redeploy with the new configuration

**Screenshot Guidance:**
```
Render Dashboard → Your Service → Environment → Add Environment Variable
```

### **Step 5: Verify Configuration**

Check that your `.env` file or Railway variables contain:
```
✓ EMAIL_HOST_USER (valid Gmail address)
✓ EMAIL_HOST_PASSWORD (16-character app password, no spaces)
✓ DEFAULT_FROM_EMAIL (sender name and email)
```

---

## TESTING EMAIL FUNCTIONALITY

### **Method 1: Django Shell Test**

1. Open Django shell:
   ```bash
   python manage.py shell
   ```

2. Run this test:
   ```python
   from django.core.mail import send_mail
   from django.conf import settings

   send_mail(
       subject='Test Email from Balilihan Waterworks',
       message='This is a test email to verify SMTP configuration.',
       from_email=settings.DEFAULT_FROM_EMAIL,
       recipient_list=['your-test-email@gmail.com'],
       fail_silently=False,
   )
   ```

3. Expected output:
   ```
   1
   ```
   (Indicates 1 email sent successfully)

4. Check your test email inbox for the message

### **Method 2: Forgot Password Test**

1. Ensure you have a user account with an email address:
   ```bash
   python manage.py shell
   ```
   ```python
   from django.contrib.auth.models import User

   # Get your superuser
   user = User.objects.get(username='your_username')

   # Set email if not already set
   user.email = 'your-email@gmail.com'
   user.save()

   print(f"Email set to: {user.email}")
   ```

2. Start the development server:
   ```bash
   python manage.py runserver
   ```

3. Navigate to: http://localhost:8000/login/

4. Click "Forgot Password?"

5. Enter your username

6. Click "Send Reset Link"

7. Check your email inbox for the password reset email

**Expected Email:**
- **Subject:** 🔐 Password Reset Request - Balilihan Waterworks
- **From:** Balilihan Waterworks
- **Contains:** Reset password button and security information

### **Method 3: Check Logs**

If email fails, check the console output for errors:

```bash
python manage.py runserver
```

Look for error messages like:
- `SMTPAuthenticationError` → Wrong app password
- `SMTPConnectError` → Network/firewall issue
- `SMTPException` → General SMTP problem

---

## TROUBLESHOOTING

### **Problem 1: "SMTPAuthenticationError: Username and Password not accepted"**

**Cause:** Incorrect app password or trying to use regular Gmail password

**Solution:**
1. Verify you're using the 16-character **app password**, not your regular password
2. Check for spaces in the app password (remove them)
3. Generate a new app password if needed
4. Ensure 2-Step Verification is enabled

**Command to test:**
```bash
python manage.py shell
```
```python
from django.conf import settings
print(f"Email User: {settings.EMAIL_HOST_USER}")
print(f"Password Length: {len(settings.EMAIL_HOST_PASSWORD)}")
print(f"Expected: 16 characters")
```

### **Problem 2: "No module named 'decouple'"**

**Cause:** Missing python-decouple package

**Solution:**
```bash
pip install python-decouple
```

### **Problem 3: Email sends but doesn't arrive**

**Causes & Solutions:**

1. **Check Spam Folder**
   - Gmail may mark automated emails as spam initially
   - Mark as "Not Spam" to train the filter

2. **Verify Recipient Email**
   ```python
   user = User.objects.get(username='your_username')
   print(user.email)  # Make sure this is correct
   ```

3. **Check Gmail Sent Folder**
   - Log into the sender Gmail account
   - Go to Sent folder
   - Verify the email was sent

4. **Gmail Sending Limits**
   - Free Gmail: 500 emails/day
   - Google Workspace: 2,000 emails/day

### **Problem 4: "No email address found for this account"**

**Cause:** User account doesn't have an email set

**Solution:**
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User

# Set email for user
user = User.objects.get(username='username')
user.email = 'user@example.com'
user.save()
```

### **Problem 5: "App passwords" not showing in Google Account**

**Causes:**
- 2-Step Verification not enabled
- Using a work/school Google account (admin may have disabled it)
- Using Google Workspace (different settings)

**Solutions:**
1. Enable 2-Step Verification first
2. Wait 5-10 minutes after enabling 2-Step Verification
3. Try a different browser or incognito mode
4. For work accounts, contact your admin

---

## SECURITY BEST PRACTICES

### **1. Use a Dedicated Gmail Account**

✅ **Recommended:**
```
Email: balilihanwaterworks@gmail.com
Purpose: System emails only
Access: IT administrator only
```

❌ **Not Recommended:**
```
Email: your-personal-email@gmail.com
Purpose: Mixed use (personal + system)
```

### **2. Protect Your App Password**

- 🔐 **Store in .env file** (never commit to Git)
- 🚫 **Never hardcode** in source code
- 🔄 **Rotate regularly** (every 6 months)
- 📋 **Use secrets manager** in production (Render Environment Variables)

### **3. Add .env to .gitignore**

Ensure your `.gitignore` contains:
```
.env
*.env
.env.local
.env.*.local
```

### **4. Monitor Email Activity**

Check Gmail account regularly for:
- Unusual sending patterns
- Failed login attempts
- Unauthorized access

### **5. Revoke Compromised App Passwords**

If app password is exposed:
1. Go to https://myaccount.google.com/apppasswords
2. Find "Balilihan Waterworks"
3. Click **Remove**
4. Generate a new app password
5. Update .env file

### **6. Use HTTPS in Production**

Ensure your production site uses HTTPS to encrypt:
- Password reset tokens in URLs
- Email content in transit
- User credentials during login

---

## ADDITIONAL INFORMATION

### **Email Template Customization**

Email templates are located at:
```
consumers/templates/consumers/emails/
├── password_reset_email.html  (HTML version)
└── password_reset_email.txt   (Plain text version)
```

To customize:
1. Edit the HTML/text files
2. Maintain the template variables:
   - `{{ username }}`
   - `{{ reset_url }}`
   - `{{ request_time }}`
   - `{{ expiration_time }}`
   - `{{ ip_address }}`

### **Token Security Features**

- ✅ **24-hour expiration** (configurable)
- ✅ **One-time use** (marked as used after reset)
- ✅ **IP tracking** (logged for security)
- ✅ **Secure random generation** (UUID4)
- ✅ **Database-backed** (persistent across restarts)

### **Email Logging**

All password reset requests are logged in:
- **UserActivity** model (database)
- **Console logs** (development)
- **Render logs** (production)

View logs:
```bash
# Local development
python manage.py runserver

# Production (Render)
Render Dashboard → Your Service → Logs
```

---

## SUPPORT

### **For Issues:**

1. **Check Logs:**
   ```bash
   python manage.py runserver --verbosity 3
   ```

2. **Test Email Settings:**
   ```python
   from django.core.mail import send_test_mail
   send_test_mail(['recipient@example.com'])
   ```

3. **Contact:**
   - System Administrator: [admin@balilihan-waterworks.com]
   - IT Support: [support@balilihan-waterworks.com]

### **Useful Links:**

- [Gmail App Passwords Help](https://support.google.com/accounts/answer/185833)
- [Django Email Documentation](https://docs.djangoproject.com/en/5.0/topics/email/)
- [Render Environment Variables](https://render.com/docs/environment-variables)

---

## CONCLUSION

You have successfully configured Gmail SMTP for secure password reset functionality. Users can now receive password reset tokens via email, ensuring secure account recovery.

**Next Steps:**
1. Test the functionality thoroughly
2. Add user email addresses to existing accounts
3. Inform users about the password reset feature
4. Monitor email activity regularly

---

**End of Guide**
